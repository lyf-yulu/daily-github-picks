import json
from github_digest.collector import parse_trending_html, search_repos, merge_and_dedup


SAMPLE_TRENDING_HTML = """
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/owner/cool-repo">owner / cool-repo</a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">A cool AI tool for agents</p>
  <div class="f6 color-fg-muted mt-2">
    <span class="d-inline-block ml-0 mr-3">
      <span class="repo-language-color" style="background-color: #3572A5"></span>
      <span itemprop="programmingLanguage">Python</span>
    </span>
    <a class="Link Link--muted d-inline-block mr-3" href="/owner/cool-repo/stargazers">
      <svg class="octicon octicon-star" aria-hidden="true"></svg>
      2,345
    </a>
    <span class="d-inline-block float-sm-right">
      <svg class="octicon octicon-star" aria-hidden="true"></svg>
      120 stars today
    </span>
  </div>
</article>
"""


def test_parse_trending_html_extracts_repo():
    repos = parse_trending_html(SAMPLE_TRENDING_HTML)
    assert len(repos) == 1
    repo = repos[0]
    assert repo["full_name"] == "owner/cool-repo"
    assert repo["description"] == "A cool AI tool for agents"
    assert repo["language"] == "Python"
    assert repo["stars"] == 2345
    assert repo["stars_today"] == 120
    assert repo["source"] == "trending"
    assert repo["url"] == "https://github.com/owner/cool-repo"
    assert repo["created_at"] == ""


def test_parse_trending_html_empty():
    repos = parse_trending_html("<html><body>Nothing here</body></html>")
    assert repos == []


def test_merge_and_dedup():
    trending = [
        {"full_name": "a/b", "stars": 100, "stars_today": 10, "source": "trending"},
        {"full_name": "c/d", "stars": 200, "stars_today": 20, "source": "trending"},
    ]
    search = [
        {"full_name": "a/b", "stars": 100, "stars_today": 0, "source": "search"},
        {"full_name": "e/f", "stars": 300, "stars_today": 0, "source": "search"},
    ]
    merged = merge_and_dedup(trending, search)
    names = [r["full_name"] for r in merged]
    assert len(merged) == 3
    assert "a/b" in names
    assert "c/d" in names
    assert "e/f" in names
    dup = [r for r in merged if r["full_name"] == "a/b"][0]
    assert dup["stars_today"] == 10  # trending version kept
