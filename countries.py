"""The countries Jobbo covers. Keep in step with Region in the iOS app."""

COUNTRIES = {
    "us": {"name": "United States", "currency": "USD", "adzuna": "us", "locale": "en_US",
           "aliases": ["us", "usa", "u.s.", "united states", "united states of america"],
           "area": ["north america", "americas"],
           "cities": ["New York", "Los Angeles", "Chicago", "Houston", "Dallas", "San Francisco",
                      "Seattle", "Boston", "Austin", "Atlanta"]},
    "gb": {"name": "United Kingdom", "currency": "GBP", "adzuna": "gb", "locale": "en_GB",
           "aliases": ["uk", "gb", "united kingdom", "great britain", "england", "scotland", "wales",
                       "northern ireland"],
           "area": ["europe", "emea", "eu"],
           "cities": ["London", "Birmingham", "Manchester", "Leeds", "Glasgow", "Liverpool", "Bristol",
                      "Edinburgh", "Sheffield", "Newcastle"]},
    "ca": {"name": "Canada", "currency": "CAD", "adzuna": "ca", "locale": "en_CA",
           "aliases": ["canada", "can"], "area": ["north america", "americas"],
           "cities": ["Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton", "Ottawa", "Winnipeg",
                      "Quebec City", "Hamilton", "Waterloo"]},
    "au": {"name": "Australia", "currency": "AUD", "adzuna": "au", "locale": "en_AU",
           "aliases": ["australia", "aus"], "area": ["apac", "asia pacific", "asia-pacific"],
           "cities": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Gold Coast", "Canberra",
                      "Newcastle", "Hobart", "Darwin"]},
    "ie": {"name": "Ireland", "currency": "EUR", "adzuna": None, "locale": "en_IE",
           "aliases": ["ireland", "irl"], "area": ["europe", "emea", "eu"],
           "cities": ["Dublin", "Cork", "Limerick", "Galway", "Waterford", "Drogheda", "Dundalk",
                      "Swords", "Bray", "Navan"]},
    "de": {"name": "Germany", "currency": "EUR", "adzuna": "de", "locale": "de_DE",
           "aliases": ["germany", "deutschland", "deu"], "area": ["europe", "emea", "eu", "dach"],
           "cities": ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt", "Stuttgart", "Düsseldorf",
                      "Leipzig", "Dortmund", "Essen"]},
    "fr": {"name": "France", "currency": "EUR", "adzuna": "fr", "locale": "fr_FR",
           "aliases": ["france", "fra"], "area": ["europe", "emea", "eu"],
           "cities": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes", "Strasbourg",
                      "Montpellier", "Bordeaux", "Lille"]},
    "nl": {"name": "Netherlands", "currency": "EUR", "adzuna": "nl", "locale": "nl_NL",
           "aliases": ["netherlands", "the netherlands", "holland", "nld"], "area": ["europe", "emea", "eu"],
           "cities": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven", "Groningen", "Tilburg",
                      "Almere", "Breda", "Nijmegen"]},
    "es": {"name": "Spain", "currency": "EUR", "adzuna": "es", "locale": "es_ES",
           "aliases": ["spain", "españa", "esp"], "area": ["europe", "emea", "eu"],
           "cities": ["Madrid", "Barcelona", "Valencia", "Seville", "Zaragoza", "Málaga", "Murcia", "Palma",
                      "Bilbao", "Alicante"]},
    "in": {"name": "India", "currency": "INR", "adzuna": "in", "locale": "en_IN",
           "aliases": ["india", "ind"], "area": ["apac", "asia pacific", "asia-pacific"],
           "cities": ["Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune", "Kolkata", "Ahmedabad",
                      "Gurugram", "Noida"]},
}

ISO3 = {"usa": "us", "gbr": "gb", "can": "ca", "aus": "au", "irl": "ie", "deu": "de", "fra": "fr",
        "nld": "nl", "esp": "es", "ind": "in"}

ANYWHERE = ["worldwide", "anywhere", "global", "work from anywhere"]


def country_code(value):
    """'United States', 'US', 'usa', 'Deutschland' → 'us' / 'de'; None if not one of ours."""
    if not value:
        return None
    v = str(value).strip().lower()
    if v in COUNTRIES:
        return v
    if v == "uk":
        return "gb"
    if v in ISO3:
        return ISO3[v]
    for cc, c in COUNTRIES.items():
        if v == c["name"].lower() or v in c["aliases"]:
            return cc
    return None


def remote_countries(text):
    """Which of our countries a remote job's stated eligibility covers.
    'Worldwide' → all; 'USA' → us; 'Europe' → the European ones; nothing named → all."""
    t = " " + " ".join(str(text or "").lower().replace(",", " ").replace("/", " ").split()) + " "
    if any(w in t for w in ANYWHERE):
        return set(COUNTRIES)
    hits = set()
    for cc, c in COUNTRIES.items():
        words = [c["name"].lower()] + [a for a in c["aliases"] if len(a) > 3] + c["area"]
        short = [a for a in c["aliases"] if len(a) <= 3]
        if any(w in t for w in words) or any(f" {s} " in t or f"({s})" in t for s in short):
            hits.add(cc)
    if hits:
        return hits
    bare = {w for w in t.split() if w not in ("remote", "-", "–", "hybrid", "only", "")}
    return set(COUNTRIES) if not bare else set()
