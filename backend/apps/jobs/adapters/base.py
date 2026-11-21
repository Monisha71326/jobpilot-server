"""Job-source adapter architecture + a hardened HTTP fetcher (SSRF-safe, size-capped, robots-aware)."""
import ipaddress
import socket
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from django.conf import settings


class FetchError(Exception):
    """Raised with a user-presentable message."""


@dataclass
class NormalizedJob:
    external_id: str
    title: str
    company: str
    description: str = ""
    location: str = ""
    is_remote: bool = False
    employment_type: str = ""
    salary_text: str = ""
    apply_url: str = ""
    posted_at: datetime | None = None
    extra: dict = field(default_factory=dict)


class JobAdapter:
    """Subclass per source. `fetch` must only use official/public endpoints and return normalized jobs."""

    slug = ""
    name = ""
    kind = "api"
    base_url = ""
    terms_url = ""
    attribution = ""
    min_refresh_minutes = 60
    needs_board_token = False
    full_listing = False  # True when one fetch returns the board's complete list (allows deactivating missing jobs)

    def fetch(self, *, query: str = "", token: str = "") -> list[NormalizedJob]:
        raise NotImplementedError


def _headers():
    return {"User-Agent": settings.HTTP_USER_AGENT, "Accept": "application/json, text/html;q=0.9"}


def http_json(url: str, params: dict | None = None):
    """GET JSON from a fixed, trusted API host."""
    try:
        r = requests.get(url, params=params, headers=_headers(), timeout=15)
    except requests.RequestException as exc:
        raise FetchError(f"Could not reach {urlparse(url).netloc}: {exc.__class__.__name__}") from exc
    if r.status_code == 404:
        raise FetchError("Not found - check the company/board name.")
    if r.status_code == 429:
        raise FetchError("The source is rate-limiting us. Try again later.")
    if not r.ok:
        raise FetchError(f"{urlparse(url).netloc} returned HTTP {r.status_code}.")
    try:
        return r.json()
    except ValueError as exc:
        raise FetchError("The source returned an unexpected response.") from exc


# ------------------------------------------------------------- user-supplied URLs
def _is_public_ip(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return not (a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast or a.is_unspecified)


def assert_public_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or not p.hostname:
        raise FetchError("Only http(s) links are supported.")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError("Could not resolve that address.") from exc
    if not infos or not all(_is_public_ip(i[4][0]) for i in infos):
        raise FetchError("That address is not a public website.")


def robots_allows(url: str) -> bool:
    p = urlparse(url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        assert_public_url(robots_url)
        r = requests.get(robots_url, headers=_headers(), timeout=6)
        if r.status_code >= 400:
            return True  # no robots file -> no restriction published
        rp = RobotFileParser()
        rp.parse(r.text.splitlines())
        return rp.can_fetch(settings.HTTP_USER_AGENT, url)
    except (FetchError, requests.RequestException):
        return True


MAX_BYTES = 2 * 1024 * 1024
BLOCK_HINTS = ("captcha", "are you a robot", "verify you are human", "access denied", "enable javascript to continue", "cf-challenge")


def fetch_public_page(url: str) -> str:
    """Fetch one user-provided page politely. Never tries to bypass blocks, logins or CAPTCHAs."""
    url = url.strip()
    if not robots_allows(url):
        raise FetchError("That site asks automated tools not to read this page. Please paste the job description instead.")
    for _ in range(4):  # follow a few redirects manually, re-validating every hop (prevents SSRF via redirect)
        assert_public_url(url)
        try:
            r = requests.get(url, headers=_headers(), timeout=12, stream=True, allow_redirects=False)
        except requests.RequestException as exc:
            raise FetchError(f"Could not open that link: {exc.__class__.__name__}") from exc
        if r.is_redirect or r.status_code in (301, 302, 303, 307, 308):
            url = urljoin(url, r.headers.get("Location", ""))
            continue
        if r.status_code in (401, 403, 429) or r.status_code >= 400:
            raise FetchError(f"The site blocked automated access (HTTP {r.status_code}). Please paste the job description instead.")
        ctype = r.headers.get("Content-Type", "")
        if "html" not in ctype and "json" not in ctype and "text" not in ctype:
            raise FetchError("That link is not a web page.")
        body = b""
        for chunk in r.iter_content(65536):
            body += chunk
            if len(body) > MAX_BYTES:
                break
        text = body.decode(r.encoding or "utf-8", errors="replace")
        low = text[:6000].lower()
        if any(h in low for h in BLOCK_HINTS) and len(text) < 20000:
            raise FetchError("The site showed a verification/robot check. Please paste the job description instead.")
        return text
    raise FetchError("Too many redirects.")
