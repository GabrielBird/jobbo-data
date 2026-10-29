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


# Centre points of each country's cities (same order as "cities"); jobs further than
# CITY_RADIUS_MILES from all of them are left out, since the app is for big-city jobs.
CITY_RADIUS_MILES = 12   # the app shows 10 miles; a little margin for rounding
CITY_COORDS = {
    "us": [(40.7128, -74.0060), (34.0522, -118.2437), (41.8781, -87.6298), (29.7604, -95.3698), (32.7767, -96.7970),
           (37.7749, -122.4194), (47.6062, -122.3321), (42.3601, -71.0589), (30.2672, -97.7431), (33.7490, -84.3880)],
    "gb": [(51.5074, -0.1278), (52.4862, -1.8904), (53.4808, -2.2426), (53.8008, -1.5491), (55.8642, -4.2518),
           (53.4084, -2.9916), (51.4545, -2.5879), (55.9533, -3.1883), (53.3811, -1.4701), (54.9783, -1.6178)],
    "ca": [(43.6532, -79.3832), (45.5017, -73.5673), (49.2827, -123.1207), (51.0447, -114.0719), (53.5461, -113.4938),
           (45.4215, -75.6972), (49.8951, -97.1384), (46.8139, -71.2080), (43.2557, -79.8711), (43.4643, -80.5204)],
    "au": [(-33.8688, 151.2093), (-37.8136, 144.9631), (-27.4698, 153.0251), (-31.9505, 115.8605), (-34.9285, 138.6007),
           (-28.0167, 153.4000), (-35.2809, 149.1300), (-32.9283, 151.7817), (-42.8821, 147.3272), (-12.4634, 130.8456)],
    "ie": [(53.3498, -6.2603), (51.8985, -8.4756), (52.6638, -8.6267), (53.2707, -9.0568), (52.2593, -7.1101),
           (53.7179, -6.3561), (54.0090, -6.4049), (53.4597, -6.2181), (53.2028, -6.0983), (53.6528, -6.6814)],
    "de": [(52.5200, 13.4050), (53.5511, 9.9937), (48.1351, 11.5820), (50.9375, 6.9603), (50.1109, 8.6821),
           (48.7758, 9.1829), (51.2277, 6.7735), (51.3397, 12.3731), (51.5136, 7.4653), (51.4556, 7.0116)],
    "fr": [(48.8566, 2.3522), (43.2965, 5.3698), (45.7640, 4.8357), (43.6047, 1.4442), (43.7102, 7.2620),
           (47.2184, -1.5536), (48.5734, 7.7521), (43.6108, 3.8767), (44.8378, -0.5792), (50.6292, 3.0573)],
    "nl": [(52.3676, 4.9041), (51.9244, 4.4777), (52.0705, 4.3007), (52.0907, 5.1214), (51.4416, 5.4697),
           (53.2194, 6.5665), (51.5555, 5.0913), (52.3508, 5.2647), (51.5719, 4.7683), (51.8126, 5.8372)],
    "es": [(40.4168, -3.7038), (41.3874, 2.1686), (39.4699, -0.3763), (37.3891, -5.9845), (41.6488, -0.8891),
           (36.7213, -4.4214), (37.9922, -1.1307), (39.5696, 2.6502), (43.2630, -2.9350), (38.3452, -0.4810)],
    "in": [(12.9716, 77.5946), (19.0760, 72.8777), (28.7041, 77.1025), (17.3850, 78.4867), (13.0827, 80.2707),
           (18.5204, 73.8567), (22.5726, 88.3639), (23.0225, 72.5714), (28.4595, 77.0266), (28.5355, 77.3910)],
}


def near_a_city(cc, lat, lon):
    from math import asin, cos, radians, sin, sqrt
    for la, lo in CITY_COORDS.get(cc, []):
        d = 2 * 3958.8 * asin(sqrt(sin(radians(lat - la) / 2) ** 2 +
                                   cos(radians(la)) * cos(radians(lat)) * sin(radians(lon - lo) / 2) ** 2))
        if d <= CITY_RADIUS_MILES:
            return True
    return False
