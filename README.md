# LinkedIn Job Scraper

Scrapes LinkedIn public job listings and exports them to an Excel file. No LinkedIn account required.

## Requirements

```bash
pip install requests beautifulsoup4 pandas xlsxwriter
```

## Usage

```bash
python linkedin_scrapper.py --cities CITY [CITY ...] --keywords KEYWORD [KEYWORD ...]
```

`--cities` and `--keywords` are required. All other arguments are optional.

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--cities` | Yes | — | One or more city names |
| `--keywords` | Yes | — | One or more job titles to search |
| `--experience` | No | `mid senior` | Experience level filter (see values below) |
| `--time-range` | No | `24h` | How far back to search |
| `--max-pages` | No | `2` | Max pages per search (25 jobs/page) |

### `--experience` values

| Value | Level |
|---|---|
| `internship` | Internship |
| `entry` | Entry level |
| `associate` | Associate |
| `mid` | Mid-Senior level |
| `senior` | Senior level |
| `director` | Director |

### `--time-range` values

| Value | Range |
|---|---|
| `24h` | Last 24 hours |
| `week` | Last 7 days |
| `month` | Last 30 days |

## Examples

Minimal — search with defaults (mid/senior, last 24h, 2 pages):

```bash
python linkedin_scrapper.py \
  --cities "Paris" "London" \
  --keywords "Data Scientist" "Research Engineer"
```

Full example with all filters:

```bash
python linkedin_scrapper.py \
  --cities "Paris" "London" "Berlin" \
  --keywords "Data Scientist" "Machine Learning Engineer" \
  --experience entry mid senior \
  --time-range week \
  --max-pages 3
```

Single city, internship search:

```bash
python linkedin_scrapper.py \
  --cities "Singapore" \
  --keywords "Computer Vision" "Deep Learning" \
  --experience internship entry \
  --time-range month \
  --max-pages 1
```

Show help:

```bash
python linkedin_scrapper.py --help
```

## Output

Results are saved to `scraped_jobs_linkedin.xlsx` in the current directory with the following columns:

| Column | Description |
|---|---|
| `position` | Job title |
| `company` | Company name |
| `location` | Job location as listed |
| `posted_time` | Time since posting |
| `keyword` | Search keyword that matched this job |
| `city` | City passed via `--cities` |
| `geo_id` | LinkedIn internal geo ID |
| `job_linkedin` | Direct link to the job posting |

Duplicate listings (same URL + company) are automatically removed across keyword/city combinations.

## Notes

- Hits LinkedIn's public-facing job search page — no login or API key needed
- City names are resolved automatically via LinkedIn's geo API — no need to look up IDs manually
- Delays between requests are randomized (1.5–4s) to avoid bot detection
- Pagination stops early if a page returns fewer than 25 results
- Raises a clear error if an invalid `--experience` value is passed
