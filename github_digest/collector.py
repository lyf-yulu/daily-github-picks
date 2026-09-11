from __future__ import annotations
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape


def _http_get(url: str, headers: dict | None = None, timeout: int = 15) -> bytes:
    hdrs = {"User-Agent": "github-digest/1.0"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_trending_html(html: str) -> list[dict]:
    repos = []
    articles = re.findall(r"<article[^>]*class=\"Box-row\"[^>]*>(.*?)</article>", html, re.DOTALL)
    for article in articles:
        name_match = re.search(r'<a[^>]*href="/([^"]+)"[^>]*>', article)
        if not name_match:
            continue
        full_name = name_match.group(1).strip()
        if full_name.count("/") != 1:
            continue

        desc_match = re.search(r'<p[^>]*class="[^"]*color-fg-muted[^"]*"[^>]*>(.*?)</p>', article, re.DOTALL)
        description = ""
        if desc_match:
            description = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip()
            description = unescape(description)

        lang_match = re.search(r'itemprop="programmingLanguage">(.*?)</span>', article)
        language = lang_match.group(1).strip() if lang_match else ""

        star_matches = re.findall(r'</svg>\s*([\d,]+)\s*(?:\n|stars)', article)
        stars = int(star_matches[0].replace(",", "")) if star_matches else 0

        today_match = re.search(r'([\d,]+)\s+stars?\s+today', article)
        stars_today = int(today_match.group(1).replace(",", "")) if today_match else 0

        repos.append({
            "full_name": full_name,
            "description": description,
            "stars": stars,
            "stars_today": stars_today,
            "language": language,
            "url": f"https://github.com/{full_name}",
            "source": "trending",
            "created_at": "",
        })
    return repos


def fetch_trending(language: str = "", since: str = "daily") -> list[dict]:
    url = "https://github.com/trending"
    params = []
    if language:
        params.append(f"language={language}")
    if since:
        params.append(f"since={since}")
    if params:
        url += "?" + "&".join(params)

    try:
        html = _http_get(url).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"[warn] Failed to fetch trending: {exc}")
        return []
    return parse_trending_html(html)


def search_repos(token: str, keywords: list[str], min_stars: int = 50, days_back: int = 7) -> list[dict]:
    date_threshold = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    repos = []
    for kw in keywords[:5]:
        query = f"{kw} created:>={date_threshold} stars:>={min_stars}"
        url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars&order=desc&per_page=30"
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        for attempt in range(3):
            try:
                data = json.loads(_http_get(url, headers=headers).decode("utf-8"))
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                if attempt == 2:
                    status_info = ""
                    if isinstance(exc, urllib.error.HTTPError):
                        status_info = f" (HTTP {exc.code})"
                    elif isinstance(exc, json.JSONDecodeError):
                        status_info = " (invalid JSON response)"
                    print(f"[warn] Search API failed for '{kw}'{status_info}: {exc}")
                    data = {"items": []}
                time.sleep(2 ** attempt)

        for item in data.get("items", []):
            repos.append({
                "full_name": item["full_name"],
                "description": item.get("description", "") or "",
                "stars": item.get("stargazers_count", 0),
                "stars_today": 0,
                "language": item.get("language", "") or "",
                "url": item["html_url"],
                "source": "search",
                "created_at": item.get("created_at", "")[:10],
            })
    return repos


def merge_and_dedup(trending: list[dict], search: list[dict]) -> list[dict]:
    seen = {}
    for repo in trending:
        seen[repo["full_name"]] = repo
    for repo in search:
        if repo["full_name"] not in seen:
            seen[repo["full_name"]] = repo
        else:
            # Backfill missing fields from search version
            existing = seen[repo["full_name"]]
            if not existing.get("created_at") and repo.get("created_at"):
                existing["created_at"] = repo["created_at"]
    return list(seen.values())


def collect(config: dict) -> list[dict]:
    trending = fetch_trending()
    all_keywords = []
    for kws in config.get("topics", {}).values():
        all_keywords.extend(kws)
    search = search_repos(config.get("github_token", ""), all_keywords)
    return merge_and_dedup(trending, search)
