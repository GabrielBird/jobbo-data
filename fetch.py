"""Pull every source, place each job on the map, and write one file per country.

    python fetch.py            # writes site/v1/<country>.json and site/v1/meta.json

Runs in GitHub Actions on a schedule (see .github/workflows/refresh.yml).
Standard library only."""

import json
import os
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from countries import COUNTRIES, country_code, near_a_city, remote_countries
import sources

ROOT = Path(__file__).parent
OUT = ROOT / "site" / "v1"
CACHE = ROOT / "cache" / "geocode.json"
GEOCODE_BUDGET = int(os.environ.get("GEOCODE_BUDGET", "400"))   # new place names looked up per run (1/second)
MAX_AGE_DAYS = 45


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------- 1. fetch ----------

def run_sources():
    companies = json.loads((ROOT / "companies.json").read_text())
    tasks = {name: (fn, companies.get(name.lower(), [])) for name, fn in sources.NO_KEY.items()}
    tasks.update({name: (fn, None) for name, fn in {**sources.OPEN, **sources.KEYED}.items()})

    status, jobs = {}, []

    def one(item):
        name, (fn, arg) = item
        t = time.time()
        try:
            res = fn(arg)
            if res is None:
                return name, [], "no key set"
            return name, res, f"{len(res)} jobs in {time.time() - t:.0f}s"
        except Exception as e:  # one broken source never stops the rest
            return name, [], f"error: {type(e).__name__}: {str(e)[:120]}"

    with ThreadPoolExecutor(6) as pool:
        for name, res, msg in pool.map(one, tasks.items()):
            status[name] = msg
            jobs += res
            log(f"{name:16} {msg}")
    return jobs, status


# ---------- 2. place on the map ----------

def segments(loc):
    """'Hybrid - San Francisco, CA • New York, NY' → ['San Francisco, CA', 'New York, NY']"""
    parts = re.split(r"[•;|]| or ", loc or "")
    parts = [re.sub(r"(?i)^(hybrid|in[- ]office|onsite|on-site)\s*[-–:]?\s*", "", p).strip() for p in parts]
    return [p for p in parts if p and "remote" not in p.lower()]


class Geocoder:
    """OpenStreetMap's Nominatim, at its 1-request-per-second limit, remembered between runs."""

    def __init__(self):
        self.cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        self.budget = GEOCODE_BUDGET
        self.last = 0.0

    def find(self, place, cc=None):
        key = f"{cc or '*'}|{place.lower().strip()}"[:120]
        if key in self.cache:
            hit = self.cache[key]
            return tuple(hit) if hit else None
        if self.budget <= 0:
            return None
        self.budget -= 1
        wait = 1.05 - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()
        q = {"q": place, "format": "jsonv2", "limit": 1, "addressdetails": 1}
        if cc:
            q["countrycodes"] = cc
        try:
            rows = sources.get_json("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(q))
        except Exception:
            return None  # don't cache network errors
        hit = None
        if rows:
            r = rows[0]
            hit = (float(r["lat"]), float(r["lon"]), (r.get("address") or {}).get("country_code"))
        self.cache[key] = list(hit) if hit else []
        return hit

    def save(self):
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(self.cache, separators=(",", ":"), ensure_ascii=False))


def place_jobs(jobs):
    geo = Geocoder()
    # Most common place names first, so the lookup budget goes where it helps most.
    counts = {}
    for j in jobs:
        if not j["r"] and (j["la"] is None or j["lo"] is None):
            for seg in segments(j["l"])[:1]:
                counts[(seg, j["cc"])] = counts.get((seg, j["cc"]), 0) + 1
    for (seg, cc), _ in sorted(counts.items(), key=lambda kv: -kv[1]):
        geo.find(seg, cc)

    placed = []
    for j in jobs:
        if j["r"]:
            placed.append(j)
            continue
        if j["la"] is None or j["lo"] is None:
            seg = (segments(j["l"]) or [None])[0]
            hit = geo.find(seg, j["cc"]) if seg else None
            if not hit:
                continue
            j["la"], j["lo"] = round(hit[0], 4), round(hit[1], 4)
            j["cc"] = j["cc"] or country_code(hit[2])
        if j["cc"] in COUNTRIES:
            placed.append(j)
    geo.save()
    log(f"geocoder: {GEOCODE_BUDGET - geo.budget} new lookups, {len(geo.cache)} places remembered")
    return placed


# ---------- 3. write ----------

def dedupe(jobs):
    seen, out = set(), []
    for j in sorted(jobs, key=lambda j: -(j["d"] or 0)):
        city = (j["l"].split(",")[0] if not j["r"] else "remote").lower()
        key = "|".join(re.sub(r"[^a-z]", "", x.lower()) for x in (j["t"], j["c"], city))
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


def write(jobs, status):
    OUT.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - MAX_AGE_DAYS * 86400
    jobs = [j for j in jobs if j["t"] and (j["d"] is None or j["d"] >= cutoff)]
    counts = {}
    for cc, c in COUNTRIES.items():
        rows = []
        for j in jobs:
            if j["r"]:
                if cc not in remote_countries(j["rt"]):
                    continue
            elif j["cc"] != cc or not near_a_city(cc, j["la"], j["lo"]):
                continue   # only jobs in and around the country's big cities
            # Drop empty fields to keep files small. Checked by identity: `0 in (False,)` is True in Python,
            # which would drop a longitude of exactly 0 (Greenwich) or a 0 coordinate.
            row = {k: v for k, v in j.items()
                   if k not in ("rt", "cc") and v is not None and v is not False and v != [] and v != ""}
            if j["cur"] != c["currency"]:  # pay in another currency: drop it rather than mislabel it
                for k in ("mn", "mx", "p", "cur"):
                    row.pop(k, None)
            rows.append(row)
        counts[cc] = len(rows)
        (OUT / f"{cc}.json").write_text(json.dumps({"country": cc, "generated": int(time.time()), "jobs": rows},
                                                   separators=(",", ":"), ensure_ascii=False))
    meta = {"generated": int(time.time()), "countries": counts, "sources": status}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    (OUT.parent / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Jobbo data</title><body style='font:15px system-ui;padding:24px'>"
        "<h1>Jobbo job data</h1><p>Refreshed automatically. Files: "
        + " ".join(f"<a href='v1/{cc}.json'>{cc}</a> ({n})" for cc, n in counts.items())
        + " · <a href='v1/meta.json'>status</a></p>")
    log("written:", counts)


if __name__ == "__main__":
    all_jobs, status = run_sources()
    log(f"fetched {len(all_jobs)} jobs")
    write(dedupe(place_jobs(all_jobs)), status)
