# Next Stop data

The job feed behind the Next Stop app (city jobs). On-site jobs are kept only within 12 miles of each
country's 10 major cities (see `countries.py`); remote jobs are kept too.

Every 6 hours, GitHub Actions pulls jobs from free sources,
works out where each one is, removes duplicates, and publishes one file per country on GitHub Pages:

```
https://gabrielbird.github.io/jobbo-data/v1/us.json   (also gb, ca, au, ie, de, fr, nl, es, in)
https://gabrielbird.github.io/jobbo-data/v1/meta.json  (when it last ran, and how each source did)
```

Next Stop reads these files instead of calling every job site itself, so free API limits are shared
by all users, keys never ship inside the app, and searches are instant.

## Sources

| Needs a key? | Source | Covers |
|---|---|---|
| No | Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Personio | Companies listed in `companies.json` |
| No | Bundesagentur für Arbeit | Germany (official federal job board) |
| No | Arbeitnow | Germany / Europe |
| No | Remotive, Remote OK, Himalayas, Jobicy | Remote jobs |
| Free key | Adzuna | US, UK, CA, AU, DE, FR, NL, ES, IN |
| Free key | Jooble, Careerjet | Most countries |
| Free key | USAJobs / Reed | US federal jobs / UK |

## Adding a key

Repo **Settings → Secrets and variables → Actions → New repository secret**, using these names:

`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOOBLE_KEY`, `CAREERJET_AFFID`, `USAJOBS_KEY`, `USAJOBS_EMAIL`, `REED_KEY`

Secrets stay private even though this repo is public. The next run picks them up; or run it now
from **Actions → Refresh jobs → Run workflow**. Jooble and Careerjet haven't been tested with a real
key yet, so check `meta.json` after adding them.

## Adding companies

Edit `companies.json`. Use the name from the company's careers link, for example
`jobs.ashbyhq.com/openai` → `"openai"`. Add `=website` for the right logo: `"linear=linear.app"`.
Boards that don't exist are skipped. Saving the file starts a refresh.

## Notes

- Locations are placed with OpenStreetMap's Nominatim at its 1-request-per-second limit, up to 400
  new place names per run, remembered between runs. Coverage fills in over the first day or two.
- Remote OK asks for a link back and credit; the app's "View on Remote OK" button does this.
- Jobs older than 45 days are dropped.

Run locally: `python3 fetch.py` (Python 3.9+, no packages needed).
