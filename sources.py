"""Every job source. Each function returns a list of job dicts made with `job(...)`.

No-key sources run on every refresh. Key-based sources run only when their
key is set as a GitHub Actions secret (see README)."""

import hashlib
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from countries import COUNTRIES, country_code

UA = "JobboBot/1.0 (+https://github.com/jobbo; job aggregator)"


# ---------- helpers ----------

def get(url, headers=None, data=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_json(url, **kw):
    return json.loads(get(url, **kw))


def text(s, limit=800):
    """HTML (even escaped HTML) → plain text, trimmed."""
    if not s:
        return None
    s = html.unescape(html.unescape(str(s)))
    s = re.sub(r"(?i)<li[^>]*>", "\n• ", s)
    s = re.sub(r"(?i)<(br|/p|/div|/h[1-6]|/li|/ul|/ol)[^>]*>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s).strip()
    return (s[:limit].rsplit(" ", 1)[0] + "…") if len(s) > limit else (s or None)


def epoch(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value / 1000 if value > 1e11 else value)
    v = str(value).strip().replace(" UTC", "+00:00").replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d", "%d/%m/%Y"):
        try:
            d = datetime.fromisoformat(v) if fmt is None else datetime.strptime(v[:10], fmt)
            return int(d.timestamp())
        except ValueError:
            continue
    return None


def num(v):
    try:
        f = float(str(v).replace(",", ""))
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def job(source, id, title, company, location="", lat=None, lon=None, remote=False, country=None,
        remote_text="", pay_min=None, pay_max=None, period=None, currency=None, posted=None, url=None,
        logo=None, site=None, summary=None, tags=(), detail=None, nearby=False):
    lo, hi = num(pay_min), num(pay_max)
    if period is None and (lo or hi):
        period = "h" if (lo or hi) < 300 else "y"
    return {
        "id": f"{source.lower()}-{id}", "t": str(title or "").strip(), "c": str(company or "").strip() or "Unknown employer",
        "l": str(location or "").strip(), "la": lat, "lo": lon, "r": bool(remote), "cc": country,
        "rt": remote_text, "mn": lo, "mx": hi, "p": period if (lo or hi) else None,
        "cur": currency if (lo or hi) else None, "s": source, "d": posted, "u": url, "g": logo, "w": site,
        "x": summary, "tg": [t for t in dict.fromkeys(x.strip() for x in tags if x and str(x).strip()) if len(t) <= 32][:8],
        "da": detail, "nb": nearby,
    }


def boards(spec_list):
    """["stripe", "datadog=datadoghq.com"] → [(slug, website, display name)]"""
    out = []
    for s in spec_list:
        slug, _, site = s.partition("=")
        slug = slug.strip().lower()
        site = site.strip() or re.sub(r"[^a-z0-9]", "", slug) + ".com"
        out.append((slug, site, slug.replace("-", " ").title()))
    return out


def each(items, fn, workers=8):
    out = []
    with ThreadPoolExecutor(workers) as pool:
        for res in pool.map(lambda i: _safe(fn, i), items):
            out += res
    return out


def _safe(fn, item):
    try:
        return fn(item)
    except Exception:
        return []


def logo_for(site):
    return f"https://www.google.com/s2/favicons?domain={site}&sz=128" if site else None


# ---------- company careers boards (no key) ----------

def greenhouse(specs):
    def one(b):
        slug, site, name = b
        d = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?pay_transparency=true")
        out = []
        for r in d.get("jobs", []):
            loc = (r.get("location") or {}).get("name", "").strip()
            pay = (r.get("pay_input_ranges") or [None])[0] or {}
            out.append(job("Greenhouse", f"{slug}-{r['id']}", r.get("title"), r.get("company_name") or name, loc,
                           remote="remote" in loc.lower(), remote_text=loc,
                           pay_min=(pay.get("min_cents") or 0) / 100 or None, pay_max=(pay.get("max_cents") or 0) / 100 or None,
                           period="h" if "hour" in (pay.get("title") or "").lower() else None, currency=pay.get("currency_type"),
                           posted=epoch(r.get("first_published") or r.get("updated_at")), url=r.get("absolute_url"),
                           logo=logo_for(site), site=site,
                           tags=[x.get("name") for x in r.get("departments", [])],
                           detail=f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{r['id']}"))
        return out
    return each(boards(specs), one)


def lever(specs):
    def one(b):
        slug, site, name = b
        out = []
        for r in get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json"):
            cat = r.get("categories") or {}
            loc = cat.get("location") or ""
            remote = r.get("workplaceType") == "remote" or "remote" in loc.lower()
            sal = r.get("salaryRange") or {}
            body = "\n\n".join(filter(None, [r.get("descriptionPlain")] +
                                     [(l.get("text") or "") + "\n" + (text(l.get("content"), 2000) or "") for l in r.get("lists", [])]))
            out.append(job("Lever", f"{slug}-{r['id']}", r.get("text"), name, loc, remote=remote,
                           country=country_code(r.get("country")), remote_text=loc,
                           pay_min=sal.get("min"), pay_max=sal.get("max"),
                           period="h" if "hour" in str(sal.get("interval", "")) else None, currency=sal.get("currency"),
                           posted=epoch(r.get("createdAt")), url=r.get("hostedUrl"), logo=logo_for(site), site=site,
                           summary=text(body), tags=[cat.get("department"), cat.get("team"), cat.get("commitment")]))
        return out
    return each(boards(specs), one)


def ashby(specs):
    def one(b):
        slug, site, name = b
        d = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
        out = []
        for r in d.get("jobs", []):
            if r.get("isListed") is False:
                continue
            addr = ((r.get("address") or {}).get("postalAddress")) or {}
            loc = r.get("location") or ""
            remote = r.get("workplaceType") == "Remote" or "remote" in loc.lower()
            pay = next((c for c in ((r.get("compensation") or {}).get("summaryComponents") or [])
                        if c.get("compensationType") == "Salary"), {})
            place = ", ".join(filter(None, [addr.get("addressLocality"), addr.get("addressRegion")]))
            out.append(job("Ashby", f"{slug}-{r['id']}", (r.get("title") or "").strip(), name, place or loc,
                           remote=remote, country=country_code(addr.get("addressCountry")), remote_text=loc + " " + str(addr.get("addressCountry") or ""),
                           pay_min=pay.get("minValue"), pay_max=pay.get("maxValue"),
                           period="h" if "HOUR" in str(pay.get("interval", "")) else None, currency=pay.get("currencyCode"),
                           posted=epoch(r.get("publishedAt")), url=r.get("jobUrl"), logo=logo_for(site), site=site,
                           summary=text(r.get("descriptionPlain")),
                           tags=[r.get("department"), r.get("team"), r.get("employmentType"), r.get("workplaceType")]))
        return out
    return each(boards(specs), one)


def smartrecruiters(specs):
    def one(b):
        slug, site, name = b
        out, offset = [], 0
        while offset < 1000:
            d = get_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}")
            rows = d.get("content", [])
            for r in rows:
                loc = r.get("location") or {}
                cc = country_code(loc.get("country"))
                if not cc:
                    continue
                out.append(job("SmartRecruiters", f"{slug}-{r['id']}", r.get("name"), (r.get("company") or {}).get("name") or name,
                               ", ".join(filter(None, [loc.get("city"), loc.get("region")])),
                               lat=num(loc.get("latitude")), lon=num(loc.get("longitude")), remote=bool(loc.get("remote")),
                               country=cc, remote_text=COUNTRIES[cc]["name"], posted=epoch(r.get("releasedDate")),
                               url=f"https://jobs.smartrecruiters.com/{slug}/{r['id']}", logo=logo_for(site), site=site,
                               tags=[(r.get(k) or {}).get("label") for k in ("department", "function", "typeOfEmployment", "experienceLevel")],
                               detail=f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{r['id']}"))
            offset += 100
            if len(rows) < 100:
                break
        return out
    return each(boards(specs), one)


def workable(specs):
    def one(b):
        slug, site, name = b
        d = get_json(f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true")
        out = []
        for r in d.get("jobs", []):
            loc = ", ".join(filter(None, [r.get("city"), r.get("state")]))
            out.append(job("Workable", f"{slug}-{r['shortcode']}", r.get("title"), d.get("name") or name, loc,
                           remote=bool(r.get("telecommuting")), country=country_code(r.get("country")),
                           remote_text=f"{r.get('title')} {r.get('country') or ''}", posted=epoch(r.get("published_on")),
                           url=r.get("url"), logo=logo_for(site), site=site, summary=text(r.get("description")),
                           tags=[r.get("department"), r.get("employment_type"), r.get("function"), r.get("experience")]))
        return out
    return each(boards(specs), one)


def recruitee(specs):
    def one(b):
        slug, site, name = b
        out = []
        for r in get_json(f"https://{slug}.recruitee.com/api/offers/").get("offers", []):
            sal = r.get("salary") or {}
            mult = 12 if sal.get("period") == "month" else 1
            out.append(job("Recruitee", f"{slug}-{r['id']}", r.get("title"), r.get("company_name") or name,
                           ", ".join(filter(None, [r.get("city"), r.get("state_code")])), remote=bool(r.get("remote")),
                           country=country_code(r.get("country_code")), remote_text=r.get("location") or "",
                           pay_min=(num(sal.get("min")) or 0) * mult or None, pay_max=(num(sal.get("max")) or 0) * mult or None,
                           period="h" if sal.get("period") == "hour" else None, currency=sal.get("currency"),
                           posted=epoch(r.get("published_at")), url=r.get("careers_url"), logo=logo_for(site), site=site,
                           summary=text((r.get("description") or "") + (r.get("requirements") or "")),
                           tags=[r.get("department")] + (r.get("tags") or [])))
        return out
    return each(boards(specs), one)


def personio(specs):
    def one(b):
        slug, site, name = b
        root = ET.fromstring(get(f"https://{slug}.jobs.personio.de/xml"))
        out = []
        for p in root.findall("position"):
            g = lambda k: (p.findtext(k) or "").strip()
            desc = " ".join((d.findtext("value") or "") for d in p.iter("jobDescription"))
            out.append(job("Personio", f"{slug}-{g('id')}", g("name"), g("subcompany") or name, g("office"),
                           remote="remote" in g("office").lower(), remote_text=g("office"), posted=epoch(g("createdAt")),
                           url=f"https://{slug}.jobs.personio.de/job/{g('id')}", logo=logo_for(site), site=site,
                           summary=text(desc), tags=[g("department"), g("employmentType"), g("seniority"), g("schedule")]))
        return out
    return each(boards(specs), one)


# ---------- open job feeds (no key) ----------

def remotive(_):
    out = []
    for r in get_json("https://remotive.com/api/remote-jobs?limit=500").get("jobs", []):
        out.append(job("Remotive", r["id"], r.get("title"), r.get("company_name"), "Remote", remote=True,
                       remote_text=r.get("candidate_required_location"), posted=epoch(r.get("publication_date")),
                       url=r.get("url"), logo=r.get("company_logo"), summary=text(r.get("description")),
                       tags=[r.get("category"), r.get("job_type")] + (r.get("tags") or [])))
    return out


def remoteok(_):
    # Remote OK's terms: link back to the listing and credit Remote OK (the app's "View on Remote OK" does both).
    out = []
    for r in get_json("https://remoteok.com/api")[1:]:
        out.append(job("Remote OK", r["id"], r.get("position"), r.get("company"), "Remote", remote=True,
                       remote_text=r.get("location") or "", pay_min=r.get("salary_min"), pay_max=r.get("salary_max"),
                       currency="USD", posted=epoch(r.get("date")), url=r.get("url"), logo=r.get("company_logo") or None,
                       summary=text(r.get("description")), tags=r.get("tags") or []))
    return out


def himalayas(_):
    out = []
    for page in range(40):  # 20 per page; the newest ~800
        rows = get_json(f"https://himalayas.app/jobs/api?limit=20&offset={page * 20}").get("jobs", [])
        for r in rows:
            out.append(job("Himalayas", re.sub(r"\W+", "-", r.get("guid", "")[-60:]), r.get("title"), r.get("companyName"),
                           "Remote", remote=True, remote_text=" ".join(r.get("locationRestrictions") or []) or "worldwide",
                           pay_min=r.get("minSalary"), pay_max=r.get("maxSalary"), currency=r.get("currency"),
                           posted=epoch(r.get("pubDate")), url=r.get("applicationLink"), logo=r.get("companyLogo") or None,
                           summary=text(r.get("excerpt") or r.get("description")), tags=(r.get("categories") or [])[:4]))
        if len(rows) < 20:
            break
        time.sleep(0.3)
    return out


def jobicy(_):
    out = []
    for r in get_json("https://jobicy.com/api/v2/remote-jobs?count=100").get("jobs", []):
        out.append(job("Jobicy", r["id"], html.unescape(r.get("jobTitle") or ""), r.get("companyName"), "Remote", remote=True,
                       remote_text=r.get("jobGeo") or "", pay_min=r.get("annualSalaryMin"), pay_max=r.get("annualSalaryMax"),
                       period="y", currency=r.get("salaryCurrency"), posted=epoch(r.get("pubDate")), url=r.get("url"),
                       logo=r.get("companyLogo"), summary=text(r.get("jobExcerpt") or r.get("jobDescription")),
                       tags=(r.get("jobIndustry") or []) + (r.get("jobType") or [])))
    return out


def arbeitnow(_):
    out = []
    for page in range(1, 4):
        d = get_json(f"https://www.arbeitnow.com/api/job-board-api?page={page}")
        for r in d.get("data", []):
            out.append(job("Arbeitnow", r["slug"], r.get("title"), r.get("company_name"), r.get("location") or "",
                           remote=bool(r.get("remote")), remote_text="Europe", posted=epoch(r.get("created_at")),
                           url=r.get("url"), summary=text(r.get("description")), tags=(r.get("tags") or []) + (r.get("job_types") or [])))
        if not d.get("links", {}).get("next"):
            break
    return out


def bundesagentur(_):
    """Germany's Federal Employment Agency job board (public, no sign-up)."""
    out, seen = [], set()
    for city in COUNTRIES["de"]["cities"]:
        for page in (1, 2):
            q = urllib.parse.urlencode({"wo": city, "umkreis": 30, "size": 100, "page": page})
            d = get_json(f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs?{q}",
                         headers={"X-API-Key": "jobboerse-jobsuche"})
            for r in d.get("ergebnisliste", []):
                ref = r.get("referenznummer")
                if not ref or ref in seen:
                    continue
                seen.add(ref)
                loc = (r.get("stellenlokationen") or [{}])[0]
                adr = loc.get("adresse") or {}
                hourly = r.get("verguetungsangabe") == "STUNDENLOHN"
                monthly = r.get("verguetungsangabe") == "MONATSGEHALT"
                pay = num(r.get("festgehalt"))
                out.append(job("Bundesagentur", ref, r.get("stellenangebotsTitel"), r.get("firma"),
                               ", ".join(filter(None, [adr.get("ort")])), lat=loc.get("breite"), lon=loc.get("laenge"),
                               country="de", pay_min=pay * 12 if (pay and monthly) else pay,
                               period="h" if hourly else ("y" if pay else None), currency="EUR",
                               posted=epoch(r.get("datumErsteVeroeffentlichung")),
                               url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}",
                               tags=[r.get("hauptberuf"), "Vollzeit" if r.get("arbeitszeitVollzeit") else None]))
            if len(d.get("ergebnisliste", [])) < 100:
                break
    return out


# ---------- key-based (run only when the secret is set) ----------

def adzuna(_):
    app_id, key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and key):
        return None
    pages = int(os.environ.get("ADZUNA_PAGES", "4"))
    out = []
    for cc, c in COUNTRIES.items():
        if not c["adzuna"]:
            continue
        for page in range(1, pages + 1):
            q = urllib.parse.urlencode({"app_id": app_id, "app_key": key, "results_per_page": 50, "sort_by": "date"})
            d = get_json(f"https://api.adzuna.com/v1/api/jobs/{c['adzuna']}/search/{page}?{q}")
            for r in d.get("results", []):
                predicted = str(r.get("salary_is_predicted")) == "1"
                out.append(job("Adzuna", r["id"], text(r.get("title"), 200), (r.get("company") or {}).get("display_name"),
                               (r.get("location") or {}).get("display_name", ""), lat=r.get("latitude"), lon=r.get("longitude"),
                               country=cc, pay_min=None if predicted else r.get("salary_min"),
                               pay_max=None if predicted else r.get("salary_max"), currency=c["currency"],
                               posted=epoch(r.get("created")), url=r.get("redirect_url"), summary=text(r.get("description")),
                               tags=[(r.get("category") or {}).get("label"), r.get("contract_time")]))
    return out


def usajobs(_):
    key, email = os.environ.get("USAJOBS_KEY"), os.environ.get("USAJOBS_EMAIL")
    if not (key and email):
        return None
    out = []
    for page in (1, 2):
        d = get_json(f"https://data.usajobs.gov/api/search?ResultsPerPage=500&Page={page}",
                     headers={"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key})
        for item in d.get("SearchResult", {}).get("SearchResultItems", []):
            m = item.get("MatchedObjectDescriptor", {})
            loc = (m.get("PositionLocation") or [{}])[0]
            pay = (m.get("PositionRemuneration") or [{}])[0]
            out.append(job("USAJobs", m.get("PositionID"), m.get("PositionTitle"), m.get("OrganizationName") or m.get("DepartmentName"),
                           loc.get("LocationName", ""), lat=loc.get("Latitude"), lon=loc.get("Longitude"), country="us",
                           pay_min=pay.get("MinimumRange"), pay_max=pay.get("MaximumRange"),
                           period="h" if pay.get("RateIntervalCode") == "PH" else "y", currency="USD",
                           posted=epoch(m.get("PublicationStartDate")), url=m.get("PositionURI"),
                           summary=text(((m.get("UserArea") or {}).get("Details") or {}).get("JobSummary")),
                           tags=[c.get("Name") for c in m.get("JobCategory", [])]))
    return out


def reed(_):
    key = os.environ.get("REED_KEY")
    if not key:
        return None
    import base64
    auth = "Basic " + base64.b64encode(f"{key}:".encode()).decode()
    out = []
    for skip in range(0, 500, 100):
        d = get_json(f"https://www.reed.co.uk/api/1.0/search?resultsToTake=100&resultsToSkip={skip}", headers={"Authorization": auth})
        for r in d.get("results", []):
            out.append(job("Reed", r["jobId"], r.get("jobTitle"), r.get("employerName"), r.get("locationName", ""),
                           country="gb", pay_min=r.get("minimumSalary"), pay_max=r.get("maximumSalary"), currency="GBP",
                           posted=epoch(r.get("date")), url=r.get("jobUrl"), summary=text(r.get("jobDescription"))))
    return out


def jooble(_):
    """Jooble: free key from jooble.org/api/about. Untested until a key is added."""
    key = os.environ.get("JOOBLE_KEY")
    if not key:
        return None
    out = []
    for cc, c in COUNTRIES.items():
        for city in c["cities"][:3]:
            body = json.dumps({"keywords": "", "location": f"{city}, {c['name']}"}).encode()
            d = get_json(f"https://jooble.org/api/{key}", data=body, headers={"Content-Type": "application/json"})
            for r in d.get("jobs", []):
                out.append(job("Jooble", r.get("id"), r.get("title"), r.get("company"), r.get("location") or city,
                               country=cc, posted=epoch(r.get("updated")), url=r.get("link"), summary=text(r.get("snippet")),
                               tags=[r.get("type")], nearby=True))
    return out


def careerjet(_):
    """Careerjet partner API: free affiliate ID from careerjet.com/partners. Untested until an ID is added."""
    affid = os.environ.get("CAREERJET_AFFID")
    if not affid:
        return None
    out = []
    for cc, c in COUNTRIES.items():
        for city in c["cities"][:3]:
            q = urllib.parse.urlencode({"affid": affid, "locale_code": c["locale"], "location": city, "pagesize": 99,
                                        "user_ip": "127.0.0.1", "user_agent": UA, "sort": "date"})
            d = get_json(f"http://public.api.careerjet.net/search?{q}")
            for r in d.get("jobs", []):
                out.append(job("Careerjet", hashlib.md5(r.get("url", "").encode()).hexdigest()[:16], r.get("title"), r.get("company"),
                               r.get("locations") or city, country=cc, posted=epoch(r.get("date")), url=r.get("url"),
                               summary=text(r.get("description")), nearby=True))
    return out


NO_KEY = {"Greenhouse": greenhouse, "Lever": lever, "Ashby": ashby, "SmartRecruiters": smartrecruiters,
          "Workable": workable, "Recruitee": recruitee, "Personio": personio}
OPEN = {"Remotive": remotive, "Remote OK": remoteok, "Himalayas": himalayas, "Jobicy": jobicy,
        "Arbeitnow": arbeitnow, "Bundesagentur": bundesagentur}
KEYED = {"Adzuna": adzuna, "USAJobs": usajobs, "Reed": reed, "Jooble": jooble, "Careerjet": careerjet}
