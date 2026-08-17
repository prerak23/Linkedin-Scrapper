import argparse
import random
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 15
RATE_LIMIT_SECONDS = (1.5, 4.0)   # randomized range (min, max)
PAGE_SIZE = 25                     # LinkedIn returns 25 results per page
MAX_PAGES = 2                      # stop early regardless; raise carefully


def resolve_geo_id(city: str) -> tuple[str, str] | None:
    """Return (geo_id, canonical_name) for a city using LinkedIn's typeahead API."""
    url = "https://www.linkedin.com/jobs-guest/api/typeaheadHits"
    params = {"query": city, "typeaheadType": "GEO", "geoTypes": "CITY,COUNTRY,STATE"}
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        hits = response.json()
        if hits:
            first = hits[0]
            return str(first["id"]), first.get("displayName", city)
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"  Geo lookup failed for '{city}': {e}")
    return None


def resolve_cities(cities: list[str]) -> dict[str, str]:
    """Resolve a list of city names to {geo_id: city_name}, skipping failures."""
    resolved = {}
    for city in cities:
        print(f"Resolving geo ID for: {city}")
        result = resolve_geo_id(city)
        if result:
            geo_id, canonical = result
            print(f"  {city} -> {canonical} (id={geo_id})")
            resolved[geo_id] = canonical
        else:
            print(f"  Could not resolve '{city}', skipping")
        time.sleep(1)
    return resolved


EXPERIENCE_LEVELS = {
    "internship": "1",
    "entry":      "2",
    "associate":  "3",
    "mid":        "4",
    "senior":     "5",
    "director":   "6",
}

TIME_RANGES = {
    "24h":   "r86400",
    "week":  "r604800",
    "month": "r2592000",
}


def build_url(keyword: str, geo_id: str, experience: list[str], time_range: str, start: int = 0) -> str:
    encoded = "%22" + keyword.replace(" ", "%20") + "%22"
    exp_param = ",".join(EXPERIENCE_LEVELS[e] for e in experience)
    tpr_param = TIME_RANGES[time_range]
    return (
        f"https://www.linkedin.com/jobs/search/"
        f"?f_TPR={tpr_param}&f_E={exp_param}&geoId={geo_id}&keywords={encoded}"
        f"&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&start={start}"
    )


def extract_text(element) -> str | None:
    return element.text.strip() or None if element else None


def parse_jobs(html: str, keyword: str, geo_id: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results_list = soup.find("ul", class_="jobs-search__results-list")
    if not results_list:
        return []

    jobs = []
    for card in results_list.find_all("li"):
        links = card.find_all("a")
        time_el = card.find("time")
        location_el = card.find("span", class_="job-search-card__location")

        if len(links) < 2 or not time_el:
            continue

        jobs.append(
            {
                "position": extract_text(links[0]),
                "company": extract_text(links[1]),
                "location": extract_text(location_el),
                "posted_time": extract_text(time_el),
                "keyword": keyword,
                "geo_id": geo_id,
                "job_linkedin": links[0].get("href", "").split("?")[0] or None,
            }
        )
    return jobs


def extract_job_id(url: str | None) -> str | None:
    # LinkedIn job URLs look like: /jobs/view/1234567890/?refId=...
    if not url:
        return None
    for part in url.split("/"):
        if part.isdigit():
            return part
    return None


def deduplicate(jobs: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for job in jobs:
        job_id = extract_job_id(job.get("job_linkedin"))
        key = job_id or (job.get("position"), job.get("company"))
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn job listings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python linkedin_scrapper.py \\
      --cities Paris "New York" Berlin \\
      --keywords "Data Scientist" "Research Engineer" \\
      --experience entry mid senior \\
      --time-range week \\
      --max-pages 3

  python linkedin_scrapper.py \\
      --cities London \\
      --keywords "Machine Learning Engineer" \\
      --experience internship entry \\
      --time-range 24h \\
      --max-pages 1
        """,
    )
    parser.add_argument(
        "--cities", nargs="+", required=True, metavar="CITY",
        help='One or more cities. e.g.: Paris "New York" Berlin',
    )
    parser.add_argument(
        "--keywords", nargs="+", required=True, metavar="KEYWORD",
        help='One or more job titles. e.g.: "Data Scientist" "Research Engineer"',
    )
    parser.add_argument(
        "--experience", nargs="+", default=["mid", "senior"],
        choices=list(EXPERIENCE_LEVELS.keys()), metavar="LEVEL",
        help=(
            "Experience levels to filter by. "
            f"Choices: {', '.join(EXPERIENCE_LEVELS)}. "
            "Default: mid senior. "
            "e.g.: --experience entry mid senior"
        ),
    )
    parser.add_argument(
        "--time-range", default="24h",
        choices=list(TIME_RANGES.keys()), metavar="RANGE",
        help=(
            "How far back to search. "
            f"Choices: {', '.join(TIME_RANGES)}. "
            "Default: 24h. "
            "e.g.: --time-range week"
        ),
    )
    parser.add_argument(
        "--max-pages", type=int, default=MAX_PAGES, metavar="N",
        help=(
            f"Max pages to fetch per search (25 jobs/page). Default: {MAX_PAGES}. "
            "Stops early if a page returns fewer than 25 results. "
            "e.g.: --max-pages 3"
        ),
    )
    args = parser.parse_args()

    # validate experience values (choices= with metavar doesn't auto-validate)
    invalid = [e for e in args.experience if e not in EXPERIENCE_LEVELS]
    if invalid:
        parser.error(f"Invalid experience level(s): {invalid}. Choose from: {list(EXPERIENCE_LEVELS)}")

    geo_map = resolve_cities(args.cities)
    if not geo_map:
        print("No locations resolved, aborting.")
        return

    all_jobs: list[dict] = []

    for geo_id, city_name in geo_map.items():
        for keyword in args.keywords:
            print(f"Fetching: {keyword} | {city_name}")
            for page in range(args.max_pages):
                start = page * PAGE_SIZE
                url = build_url(keyword, geo_id, args.experience, args.time_range, start)
                try:
                    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                    response.raise_for_status()
                    jobs = parse_jobs(response.text, keyword, geo_id)
                    for job in jobs:
                        job["city"] = city_name
                    print(f"  Page {page + 1}: {len(jobs)} jobs")
                    all_jobs.extend(jobs)
                    if len(jobs) < PAGE_SIZE:
                        break  # last page, no point fetching further
                except requests.RequestException as e:
                    print(f"  Request failed (page {page + 1}): {e}")
                    break
                time.sleep(random.uniform(*RATE_LIMIT_SECONDS))

    all_jobs = deduplicate(all_jobs)
    print(f"\nTotal unique jobs: {len(all_jobs)}")

    df = pd.DataFrame(all_jobs)
    output_file = "scraped_jobs_linkedin.xlsx"
    df.to_excel(output_file, engine="xlsxwriter", index=False)
    print(f"Saved to {output_file}")


if __name__ == "__main__":
    main()
