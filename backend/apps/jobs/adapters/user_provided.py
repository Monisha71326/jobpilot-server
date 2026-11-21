"""Turn a user-provided job link or pasted description into a NormalizedJob. No scraping beyond that single page."""
import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from apps.core.textutil import clean_html

from .base import FetchError, NormalizedJob, fetch_public_page
from .sources import _dt


def _jsonld_job(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if "@graph" in item and isinstance(item["@graph"], list):
                    stack.extend(item["@graph"])
                t = item.get("@type")
                if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                    return item
    return None


def _loc(item: dict) -> str:
    loc = item.get("jobLocation")
    loc = loc[0] if isinstance(loc, list) and loc else loc
    if isinstance(loc, dict):
        a = loc.get("address", {})
        if isinstance(a, dict):
            return ", ".join(x for x in [a.get("addressLocality"), a.get("addressRegion"), a.get("addressCountry") if isinstance(a.get("addressCountry"), str) else ""] if x)
    return ""


def from_url(url: str) -> NormalizedJob:
    page = fetch_public_page(url)
    soup = BeautifulSoup(page, "html.parser")
    ld = _jsonld_job(soup)
    host = urlparse(url).netloc.replace("www.", "")
    if ld:
        org = ld.get("hiringOrganization")
        company = org.get("name") if isinstance(org, dict) else (org or host)
        salary = ""
        bs = ld.get("baseSalary")
        if isinstance(bs, dict) and isinstance(bs.get("value"), dict):
            v = bs["value"]
            salary = f"{v.get('minValue', '')}-{v.get('maxValue', '')} {bs.get('currency', '')}".strip(" -")
        et = ld.get("employmentType")
        return NormalizedJob(
            external_id="", title=str(ld.get("title", ""))[:200], company=str(company)[:160],
            description=clean_html(str(ld.get("description", ""))), location=_loc(ld)[:160],
            is_remote=ld.get("jobLocationType") == "TELECOMMUTE", employment_type=(", ".join(et) if isinstance(et, list) else str(et or ""))[:40],
            salary_text=salary[:120], apply_url=url, posted_at=_dt(ld.get("datePosted")),
        )
    og = lambda p: (soup.find("meta", property=p) or {}).get("content", "")  # noqa: E731
    title = og("og:title") or (soup.title.string.strip() if soup.title and soup.title.string else "") or (soup.h1.get_text(strip=True) if soup.h1 else "")
    body = soup.find("main") or soup.find("article") or soup.body
    text = clean_html(str(body)) if body else ""
    if len(text) < 200:
        raise FetchError("Could not find a job description on that page. Please paste the description instead.")
    return NormalizedJob(external_id="", title=title[:200], company=(og("og:site_name") or host)[:160], description=text[:20000], apply_url=url)


def from_text(text: str, title: str = "", company: str = "", location: str = "", apply_url: str = "") -> NormalizedJob:
    text = text.strip()
    if len(text) < 60:
        raise FetchError("Please paste the full job description (at least a few lines).")
    if not title:
        first = next((l.strip() for l in text.split("\n") if l.strip()), "")
        title = first[:120]
    return NormalizedJob(
        external_id="", title=title[:200], company=(company or "Unknown company")[:160], description=text[:20000],
        location=location[:160], is_remote=bool(re.search(r"\bremote\b", f"{location} {text[:400]}", re.I)), apply_url=apply_url,
    )
