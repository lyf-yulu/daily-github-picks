# GitHub Trending Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend ai-wechat-digest with a GitHub trending monitoring pipeline that collects, filters, summarizes (via Claude), renders HTML reports, and pushes to Feishu.

**Architecture:** Modular pipeline with 5 stages (collector → ranker → summarizer → renderer → distributor), each reading/writing JSON intermediate files in `data/YYYY-MM-DD/`. Single entry point `main_github.py` orchestrates all stages sequentially, supports `--step` for running individual stages.

**Tech Stack:** Python 3.9+ (stdlib urllib/json/sqlite3), Jinja2 (templating), OpenAI-compatible API (Claude via t8star), Mermaid.js (client-side diagrams), Feishu webhook (card messages), GitHub Pages (report hosting).

---

## File Structure

```
ai-wechat-digest/
├── github_digest/
│   ├── __init__.py
│   ├── collector.py      # GitHub Trending scraper + Search API
│   ├── ranker.py         # Keyword filtering + scoring
│   ├── summarizer.py     # Claude API for Chinese summaries + Mermaid
│   ├── renderer.py       # Jinja2 HTML report generation
│   ├── distributor.py    # Git push + Feishu webhook
│   └── config.py         # Config loading with env var priority
├── templates/
│   └── report.html       # Jinja2 HTML template
├── tests/
│   ├── __init__.py
│   ├── test_collector.py
│   ├── test_ranker.py
│   ├── test_summarizer.py
│   ├── test_renderer.py
│   └── test_distributor.py
├── main_github.py        # Entry point / pipeline orchestrator
├── config_github.json    # GitHub digest config (separate from RSS config)
├── config_github.example.json
├── requirements_github.txt
└── launchd/
    └── com.user.github-digest.plist
```

---

## Task 1: Project Setup & Config Module

**Files:**
- Create: `github_digest/__init__.py`
- Create: `github_digest/config.py`
- Create: `config_github.example.json`
- Create: `requirements_github.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create requirements file**

```
jinja2>=3.1
```

- [ ] **Step 2: Install dependencies**

Run: `pip3 install jinja2`

- [ ] **Step 3: Create package init**

Create `github_digest/__init__.py` (empty file).

- [ ] **Step 4: Write the config test**

Create `tests/test_config.py`:

```python
import json
import tempfile
from pathlib import Path
from github_digest.config import load_github_config

def test_load_config_reads_json():
    cfg = {"github_token": "ghp_test", "top_k": 3, "topics": {"ai": ["llm"]}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(cfg, f)
        f.flush()
        result = load_github_config(Path(f.name))
    assert result["github_token"] == "ghp_test"
    assert result["top_k"] == 3

def test_load_config_env_overrides_api_key(monkeypatch):
    cfg = {"llm": {"api_key": "from-file", "provider": "openai_compatible"}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(cfg, f)
        f.flush()
        monkeypatch.setenv("LLM_API_KEY", "from-env")
        result = load_github_config(Path(f.name))
    assert result["llm"]["api_key"] == "from-env"

def test_load_config_defaults():
    cfg = {}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(cfg, f)
        f.flush()
        result = load_github_config(Path(f.name))
    assert result["top_k"] == 5
    assert "topics" in result
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_config.py -v`
Expected: FAIL (module not found)

- [ ] **Step 6: Implement config module**

Create `github_digest/config.py`:

```python
from __future__ import annotations
import json
import os
from pathlib import Path

DEFAULTS = {
    "github_token": "",
    "topics": {
        "ai_llm": ["llm", "agent", "rag", "prompt", "fine-tune", "inference", "transformer"],
        "dev_tools": ["cli", "plugin", "skill", "neovim", "vscode", "devtools", "copilot", "claude code", "codex"],
    },
    "top_k": 5,
    "llm": {
        "provider": "openai_compatible",
        "model": "claude-opus-4-7",
        "base_url": "https://ai.t8star.org",
        "api_key": "",
    },
    "feishu_webhook": "",
    "github_pages_base_url": "",
}


def load_github_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    for key, default in DEFAULTS.items():
        if key not in cfg:
            cfg[key] = default
        elif isinstance(default, dict):
            for subkey, subval in default.items():
                if subkey not in cfg[key]:
                    cfg[key][subkey] = subval

    env_key = os.environ.get("LLM_API_KEY", "")
    if env_key:
        cfg.setdefault("llm", {})["api_key"] = env_key

    env_gh = os.environ.get("GITHUB_TOKEN", "")
    if env_gh:
        cfg["github_token"] = env_gh

    return cfg
```

- [ ] **Step 7: Run tests**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 8: Create example config**

Create `config_github.example.json`:

```json
{
  "github_token": "",
  "topics": {
    "ai_llm": ["llm", "agent", "rag", "prompt", "fine-tune", "inference", "transformer"],
    "dev_tools": ["cli", "plugin", "skill", "neovim", "vscode", "devtools", "copilot", "claude code", "codex"]
  },
  "top_k": 5,
  "llm": {
    "provider": "openai_compatible",
    "model": "claude-opus-4-7",
    "base_url": "https://ai.t8star.org",
    "api_key": ""
  },
  "feishu_webhook": "",
  "github_pages_base_url": ""
}
```

- [ ] **Step 9: Commit**

```bash
git add github_digest/ tests/ config_github.example.json requirements_github.txt
git commit -m "feat: add project structure and config module for GitHub digest"
```

---

## Task 2: Collector Module — GitHub Trending Scraper

**Files:**
- Create: `github_digest/collector.py`
- Create: `tests/test_collector.py`

- [ ] **Step 1: Write collector tests**

Create `tests/test_collector.py`:

```python
import json
from github_digest.collector import parse_trending_html, search_repos_via_api, merge_and_dedup


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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_collector.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement collector module**

Create `github_digest/collector.py`:

```python
from __future__ import annotations
import json
import re
import time
import urllib.error
import urllib.request
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
    from datetime import datetime, timedelta
    date_threshold = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

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
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == 2:
                    print(f"[warn] Search API failed for '{kw}': {exc}")
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
    return list(seen.values())


def collect(config: dict) -> list[dict]:
    trending = fetch_trending()
    all_keywords = []
    for kws in config.get("topics", {}).values():
        all_keywords.extend(kws)
    search = search_repos(config.get("github_token", ""), all_keywords)
    return merge_and_dedup(trending, search)
```

- [ ] **Step 4: Add missing import**

Add `import urllib.parse` to the imports in `collector.py` (after `import urllib.error`).

- [ ] **Step 5: Run tests**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_collector.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add github_digest/collector.py tests/test_collector.py
git commit -m "feat: add GitHub collector module (trending scraper + search API)"
```

---

## Task 3: Ranker Module — Keyword Filtering & Scoring

**Files:**
- Create: `github_digest/ranker.py`
- Create: `tests/test_ranker.py`

- [ ] **Step 1: Write ranker tests**

Create `tests/test_ranker.py`:

```python
from github_digest.ranker import score_repo, rank_repos


def test_score_repo_keyword_match():
    repo = {
        "full_name": "user/llm-agent",
        "description": "An agent framework for LLM applications",
        "stars": 500,
        "stars_today": 50,
        "language": "Python",
        "created_at": "2026-06-08",
    }
    topics = {"ai_llm": ["llm", "agent", "rag"]}
    result = score_repo(repo, topics)
    assert result["score"] > 0
    assert "ai_llm" in result["matched_topics"]
    assert "llm" in result["matched_keywords"]
    assert "agent" in result["matched_keywords"]


def test_score_repo_no_match():
    repo = {
        "full_name": "user/cooking-recipes",
        "description": "A collection of recipes",
        "stars": 1000,
        "stars_today": 200,
        "language": "Markdown",
        "created_at": "2026-01-01",
    }
    topics = {"ai_llm": ["llm", "agent"]}
    result = score_repo(repo, topics)
    assert result["score"] == 0
    assert result["matched_topics"] == []
    assert result["matched_keywords"] == []


def test_score_repo_highlight_by_stars_today():
    repo = {
        "full_name": "user/hot-repo",
        "description": "A prompt engineering tool",
        "stars": 500,
        "stars_today": 250,
        "language": "Python",
        "created_at": "2026-06-09",
    }
    topics = {"ai_llm": ["prompt"]}
    result = score_repo(repo, topics)
    assert result["highlight"] is True


def test_rank_repos_returns_top_k():
    repos = [
        {"full_name": f"user/repo-{i}", "description": f"llm tool {i}",
         "stars": i * 100, "stars_today": i * 10, "language": "Python",
         "created_at": "2026-06-08", "url": f"https://github.com/user/repo-{i}",
         "source": "trending"}
        for i in range(10)
    ]
    topics = {"ai_llm": ["llm"]}
    ranked = rank_repos(repos, topics, top_k=3)
    assert len(ranked) == 3
    assert ranked[0]["score"] >= ranked[1]["score"]
    assert ranked[1]["score"] >= ranked[2]["score"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_ranker.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement ranker module**

Create `github_digest/ranker.py`:

```python
from __future__ import annotations
from datetime import datetime


def score_repo(repo: dict, topics: dict[str, list[str]]) -> dict:
    text = f"{repo['full_name']} {repo.get('description', '')}".lower()
    matched_topics = []
    matched_keywords = []

    for topic_name, keywords in topics.items():
        for kw in keywords:
            if kw.lower() in text:
                if topic_name not in matched_topics:
                    matched_topics.append(topic_name)
                if kw not in matched_keywords:
                    matched_keywords.append(kw)

    keyword_score = len(matched_keywords) * 10
    if keyword_score == 0:
        return {
            **repo,
            "score": 0,
            "matched_topics": [],
            "matched_keywords": [],
            "highlight": False,
        }

    stars_today = repo.get("stars_today", 0)
    stars_score = min(stars_today / 10, 20)

    recency_score = 0
    created = repo.get("created_at", "")
    if created and len(created) >= 10:
        try:
            days_old = (datetime.utcnow() - datetime.strptime(created[:10], "%Y-%m-%d")).days
            if days_old <= 7:
                recency_score = 15
            elif days_old <= 30:
                recency_score = 8
        except ValueError:
            pass

    total = keyword_score + stars_score + recency_score

    highlight = (stars_today > 200) or (
        recency_score == 15 and repo.get("stars", 0) > 100
    )

    return {
        **repo,
        "score": round(total, 2),
        "matched_topics": matched_topics,
        "matched_keywords": matched_keywords,
        "highlight": highlight,
    }


def rank_repos(repos: list[dict], topics: dict[str, list[str]], top_k: int = 5) -> list[dict]:
    scored = [score_repo(r, topics) for r in repos]
    relevant = [r for r in scored if r["score"] > 0]
    relevant.sort(key=lambda r: r["score"], reverse=True)
    return relevant[:top_k]
```

- [ ] **Step 4: Run tests**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_ranker.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add github_digest/ranker.py tests/test_ranker.py
git commit -m "feat: add ranker module with keyword scoring and highlight detection"
```

---

## Task 4: Summarizer Module — Claude API Integration

**Files:**
- Create: `github_digest/summarizer.py`
- Create: `tests/test_summarizer.py`

- [ ] **Step 1: Write summarizer tests**

Create `tests/test_summarizer.py`:

```python
import json
from unittest.mock import patch, MagicMock
from github_digest.summarizer import generate, build_prompt, parse_llm_response


def test_build_prompt_normal():
    repo = {
        "full_name": "owner/repo",
        "description": "A cool tool",
        "highlight": False,
    }
    readme = "# My Project\nThis is a CLI tool for managing prompts."
    prompt = build_prompt(repo, readme, highlight=False)
    assert "owner/repo" in prompt
    assert "200-300" in prompt
    assert "Mermaid" in prompt


def test_build_prompt_highlight():
    repo = {
        "full_name": "owner/repo",
        "description": "A cool tool",
        "highlight": True,
    }
    readme = "# My Project\nAdvanced agent framework."
    prompt = build_prompt(repo, readme, highlight=True)
    assert "400-500" in prompt
    assert "为什么值得关注" in prompt


def test_parse_llm_response_valid():
    raw = json.dumps({
        "title": "测试项目",
        "one_liner": "一句话",
        "summary": "详细摘要内容",
        "highlights": ["亮点1"],
        "tech_stack": ["Python"],
        "diagrams": [{"title": "架构", "mermaid": "graph TD\\n  A-->B"}],
    })
    result = parse_llm_response(raw)
    assert result["title"] == "测试项目"
    assert result["diagrams"][0]["title"] == "架构"


def test_parse_llm_response_invalid_json():
    result = parse_llm_response("This is not JSON at all")
    assert result is None


def test_generate_calls_api(monkeypatch):
    fake_response = json.dumps({
        "choices": [{
            "message": {
                "content": json.dumps({
                    "title": "测试",
                    "one_liner": "一句话",
                    "summary": "摘要",
                    "highlights": [],
                    "tech_stack": ["Go"],
                    "diagrams": [],
                })
            }
        }]
    }).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_response
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        llm_config = {
            "provider": "openai_compatible",
            "model": "claude-opus-4-7",
            "base_url": "https://ai.t8star.org",
            "api_key": "sk-test",
        }
        result = generate("test prompt", llm_config)
    assert "测试" in result
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_summarizer.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement summarizer module**

Create `github_digest/summarizer.py`:

```python
from __future__ import annotations
import base64
import json
import urllib.error
import urllib.request
import time


def _http_get(url: str, headers: dict | None = None, timeout: int = 15) -> bytes:
    hdrs = {"User-Agent": "github-digest/1.0"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_readme(full_name: str, token: str) -> str:
    url = f"https://api.github.com/repos/{full_name}/readme"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        data = json.loads(_http_get(url, headers=headers).decode("utf-8"))
        content = data.get("content", "")
        return base64.b64decode(content).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[warn] Failed to fetch README for {full_name}: {exc}")
        return ""


def build_prompt(repo: dict, readme: str, highlight: bool) -> str:
    length = "400-500" if highlight else "200-300"
    extra = "\n6. 给出「为什么值得关注」的点评（why_notable 字段）" if highlight else ""

    return f"""请分析以下 GitHub 仓库并输出 JSON 格式的中文摘要。

仓库: {repo['full_name']}
描述: {repo.get('description', '')}

README 内容:
{readme[:8000]}

要求:
1. 输出纯 JSON（不要 markdown code fence）
2. summary 字段为 {length} 字中文摘要，提取项目定位、功能亮点、技术栈
3. highlights 为 2-3 个核心亮点
4. tech_stack 列出主要技术栈
5. diagrams 字段输出 1-2 个 Mermaid 图表代码，梳理项目架构或数据流{extra}

JSON 结构:
{{
  "title": "项目中文简称",
  "one_liner": "一句话概括（20字内）",
  "summary": "详细中文摘要...",
  "highlights": ["亮点1", "亮点2"],
  "tech_stack": ["Python", "FastAPI"],
  "why_notable": "仅 highlight 项目需要此字段，否则为空字符串",
  "diagrams": [
    {{"title": "系统架构", "mermaid": "graph TD\\n  A[用户] --> B[API]"}}
  ]
}}"""


def generate(prompt: str, llm_config: dict) -> str:
    payload = json.dumps({
        "model": llm_config.get("model", "claude-opus-4-7"),
        "messages": [
            {"role": "system", "content": "你是一个严谨的中文技术编辑，擅长分析开源项目并输出结构化 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2000,
    }, ensure_ascii=False).encode("utf-8")

    base_url = llm_config.get("base_url", "https://ai.t8star.org").rstrip("/")
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {llm_config['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))

    choices = data.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content.strip()


def parse_llm_response(raw: str) -> dict | None:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def summarize_repo(repo: dict, token: str, llm_config: dict) -> dict | None:
    readme = fetch_readme(repo["full_name"], token)
    if not readme and not repo.get("description"):
        return None

    content = readme if readme else repo.get("description", "")
    prompt = build_prompt(repo, content, highlight=repo.get("highlight", False))

    for attempt in range(3):
        try:
            raw = generate(prompt, llm_config)
            parsed = parse_llm_response(raw)
            if parsed:
                parsed["full_name"] = repo["full_name"]
                parsed["stars"] = repo.get("stars", 0)
                parsed["stars_today"] = repo.get("stars_today", 0)
                parsed["url"] = repo.get("url", f"https://github.com/{repo['full_name']}")
                return parsed
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"[warn] LLM attempt {attempt+1} failed for {repo['full_name']}: {exc}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    print(f"[warn] Skipping {repo['full_name']} after 3 failed attempts")
    return None


def summarize_all(repos: list[dict], config: dict) -> list[dict]:
    token = config.get("github_token", "")
    llm_config = config.get("llm", {})
    results = []
    for repo in repos:
        result = summarize_repo(repo, token, llm_config)
        if result:
            results.append(result)
    return results
```

- [ ] **Step 4: Run tests**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_summarizer.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add github_digest/summarizer.py tests/test_summarizer.py
git commit -m "feat: add summarizer module with Claude API integration"
```

---

## Task 5: Renderer Module — Jinja2 HTML Report

**Files:**
- Create: `github_digest/renderer.py`
- Create: `templates/report.html`
- Create: `tests/test_renderer.py`

- [ ] **Step 1: Write renderer tests**

Create `tests/test_renderer.py`:

```python
import tempfile
from pathlib import Path
from github_digest.renderer import render_report


def test_render_report_produces_html():
    summaries = [
        {
            "full_name": "owner/repo",
            "title": "测试项目",
            "one_liner": "一句话概括",
            "summary": "这是一个详细的中文摘要",
            "highlights": ["亮点1", "亮点2"],
            "tech_stack": ["Python", "FastAPI"],
            "why_notable": "",
            "stars": 1234,
            "stars_today": 89,
            "url": "https://github.com/owner/repo",
            "diagrams": [
                {"title": "架构图", "mermaid": "graph TD\n  A-->B"}
            ],
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "report.html"
        render_report(summaries, output, date_str="2026-06-10")
        assert output.exists()
        html = output.read_text(encoding="utf-8")
        assert "测试项目" in html
        assert "owner/repo" in html
        assert "graph TD" in html
        assert "mermaid" in html
        assert "1,234" in html or "1234" in html


def test_render_report_highlight_style():
    summaries = [
        {
            "full_name": "hot/repo",
            "title": "热门项目",
            "one_liner": "很火",
            "summary": "摘要",
            "highlights": ["亮点"],
            "tech_stack": ["Rust"],
            "why_notable": "增长极快",
            "stars": 5000,
            "stars_today": 300,
            "url": "https://github.com/hot/repo",
            "diagrams": [],
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "report.html"
        render_report(summaries, output, date_str="2026-06-10")
        html = output.read_text(encoding="utf-8")
        assert "值得关注" in html or "highlight" in html


def test_render_report_empty_summaries():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "report.html"
        render_report([], output, date_str="2026-06-10")
        assert output.exists()
        html = output.read_text(encoding="utf-8")
        assert "今日没有" in html or "没有发现" in html or "GitHub" in html
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_renderer.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Create Jinja2 HTML template**

Create `templates/report.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub 每日精选 | {{ date_str }}</title>
<style>
:root { --bg: #f8f9fa; --card: #fff; --text: #1a1a2e; --accent: #667eea; --muted: #6c757d; --border: #e9ecef; --highlight-border: #f59e0b; }
@media (prefers-color-scheme: dark) { :root { --bg: #0d1117; --card: #161b22; --text: #c9d1d9; --accent: #79c0ff; --muted: #8b949e; --border: #30363d; --highlight-border: #f59e0b; } }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; padding: 2rem 1rem; max-width: 900px; margin: 0 auto; }
h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }
.subtitle { color: var(--muted); margin-bottom: 2rem; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
.card.highlight { border-color: var(--highlight-border); border-width: 2px; position: relative; }
.card.highlight::after { content: "值得关注"; position: absolute; top: -10px; right: 16px; background: var(--highlight-border); color: #fff; font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.card-title { font-size: 1.2rem; font-weight: 600; }
.card-title a { color: var(--accent); text-decoration: none; }
.card-title a:hover { text-decoration: underline; }
.stars { color: var(--muted); font-size: 0.9rem; }
.stars-today { color: var(--highlight-border); font-weight: 500; }
.one-liner { color: var(--muted); font-style: italic; margin-bottom: 0.75rem; }
.tags { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.75rem; }
.tag { background: var(--border); color: var(--text); padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; }
.summary { margin-bottom: 1rem; }
.why-notable { background: rgba(245,158,11,0.1); border-left: 3px solid var(--highlight-border); padding: 0.5rem 1rem; margin-bottom: 1rem; border-radius: 4px; }
.diagram-section { margin-top: 1rem; }
.diagram-title { font-size: 0.9rem; color: var(--muted); margin-bottom: 0.5rem; }
.empty { text-align: center; padding: 3rem; color: var(--muted); }
footer { text-align: center; color: var(--muted); margin-top: 3rem; font-size: 0.85rem; }
@media (max-width: 600px) { body { padding: 1rem 0.5rem; } .card { padding: 1rem; } }
</style>
</head>
<body>
<h1>GitHub 每日精选</h1>
<p class="subtitle">{{ date_str }} · 共 {{ summaries|length }} 个项目</p>

{% if summaries %}
{% for item in summaries %}
<div class="card{% if item.why_notable %} highlight{% endif %}">
  <div class="card-header">
    <span class="card-title"><a href="{{ item.url }}" target="_blank">{{ item.title }}</a></span>
    <span class="stars">⭐ {{ "{:,}".format(item.stars) }}{% if item.stars_today %} <span class="stars-today">(+{{ item.stars_today }} today)</span>{% endif %}</span>
  </div>
  <p class="one-liner">{{ item.one_liner }}</p>
  <div class="tags">
    {% for tech in item.tech_stack %}<span class="tag">{{ tech }}</span>{% endfor %}
  </div>
  <div class="summary">{{ item.summary }}</div>
  {% if item.why_notable %}<div class="why-notable">{{ item.why_notable }}</div>{% endif %}
  {% for diagram in item.diagrams %}
  <div class="diagram-section">
    <p class="diagram-title">{{ diagram.title }}</p>
    <div class="mermaid">{{ diagram.mermaid }}</div>
  </div>
  {% endfor %}
  <p style="font-size:0.85rem;color:var(--muted)"><a href="{{ item.url }}" target="_blank">{{ item.full_name }}</a></p>
</div>
{% endfor %}
{% else %}
<div class="empty">今日没有发现符合条件的新项目</div>
{% endif %}

<footer>由 GitHub Trending Monitor 自动生成</footer>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({startOnLoad:true, theme: window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'default'});</script>
</body>
</html>
```

- [ ] **Step 4: Implement renderer module**

Create `github_digest/renderer.py`:

```python
from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = APP_DIR / "templates"


def render_report(summaries: list[dict], output_path: Path, date_str: str) -> None:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    template = env.get_template("report.html")
    html = template.render(summaries=summaries, date_str=date_str)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
```

- [ ] **Step 5: Run tests**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_renderer.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add github_digest/renderer.py templates/report.html tests/test_renderer.py
git commit -m "feat: add HTML renderer with Jinja2 template and Mermaid support"
```

---

## Task 6: Distributor Module — Git Push + Feishu Webhook

**Files:**
- Create: `github_digest/distributor.py`
- Create: `tests/test_distributor.py`

- [ ] **Step 1: Write distributor tests**

Create `tests/test_distributor.py`:

```python
import json
from unittest.mock import patch, MagicMock
from github_digest.distributor import build_feishu_payload, send_feishu, deploy_to_pages


def test_build_feishu_payload():
    summaries = [
        {
            "full_name": "owner/repo",
            "title": "测试项目",
            "one_liner": "一个很酷的工具",
            "stars": 1234,
            "stars_today": 89,
        }
    ]
    payload = build_feishu_payload(summaries, "2026-06-10", "https://example.com/report.html")
    data = json.loads(payload)
    assert data["msg_type"] == "interactive"
    assert "测试项目" in json.dumps(data)
    assert "https://example.com/report.html" in json.dumps(data)


def test_build_feishu_payload_empty():
    summaries = []
    payload = build_feishu_payload(summaries, "2026-06-10", "https://example.com/report.html")
    data = json.loads(payload)
    assert "没有发现" in json.dumps(data) or "空" in json.dumps(data)


def test_send_feishu_success():
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"code": 0, "msg": "success"}'
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        send_feishu("https://hook.example.com", "{}")


def test_send_feishu_retries_on_failure():
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"code": 1, "msg": "error"}'
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        send_feishu("https://hook.example.com", "{}")
        assert mock_urlopen.call_count == 3
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_distributor.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement distributor module**

Create `github_digest/distributor.py`:

```python
from __future__ import annotations
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = APP_DIR / "docs" / "reports"


def build_feishu_payload(summaries: list[dict], date_str: str, report_url: str) -> str:
    if not summaries:
        md = f"GitHub 每日精选 | {date_str}\n\n今日没有发现符合条件的新项目。"
    else:
        lines = [f"今日发现 {len(summaries)} 个值得关注的项目：\n"]
        for s in summaries:
            stars = s.get("stars", 0)
            stars_today = s.get("stars_today", 0)
            extra = f" (+{stars_today} today)" if stars_today else ""
            lines.append(
                f"**{s['title']}** ({s['full_name']})\n"
                f"{s.get('one_liner', '')}\n"
                f":star: {stars}{extra}\n"
            )
        md = "\n".join(lines)

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": f"GitHub 每日精选 | {date_str}",
                "template": "blue",
            },
            "elements": [
                {"tag": "markdown", "content": md},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": "查看完整报告",
                            "url": report_url,
                            "type": "primary",
                        }
                    ],
                },
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def send_feishu(webhook_url: str, payload_str: str) -> None:
    req = urllib.request.Request(
        webhook_url,
        data=payload_str.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            if data.get("code") == 0:
                return
            print(f"[warn] Feishu webhook attempt {attempt+1}: {data}")
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"[warn] Feishu webhook attempt {attempt+1}: {exc}")
        if attempt < 2:
            time.sleep(2 ** attempt)
    print("[error] Feishu webhook failed after 3 attempts")


def deploy_to_pages(html_path: Path, date_str: str) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    target = DOCS_DIR / f"{date_str}.html"
    target.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")

    index = DOCS_DIR / "index.html"
    links = []
    for f in sorted(DOCS_DIR.glob("*.html"), reverse=True):
        if f.name != "index.html":
            links.append(
                f'<li><a href="{f.name}">{f.stem}</a></li>'
            )
    index_html = (
        "<!DOCTYPE html><html><head><meta charset=utf-8>"
        "<title>GitHub 每日精选 历史报告</title></head><body>"
        f"<h1>历史报告</h1><ul>{''.join(links[:30])}</ul></body></html>"
    )
    index.write_text(index_html, encoding="utf-8")

    for attempt in range(2):
        try:
            subprocess.run(["git", "add", str(DOCS_DIR.relative_to(APP_DIR))],
                           cwd=str(APP_DIR), check=True)
            subprocess.run(
                ["git", "commit", "-m",
                 f"report: GitHub daily digest {date_str}",
                 "--allow-empty"],
                cwd=str(APP_DIR), check=True)
            subprocess.run(["git", "push"], cwd=str(APP_DIR), check=True)
            return
        except subprocess.CalledProcessError as exc:
            print(f"[warn] Git push attempt {attempt+1}: {exc}")
            if attempt == 1:
                print("[error] Git push failed after 2 attempts")


def distribute(summaries: list[dict], html_path: Path, date_str: str, config: dict) -> None:
    base_url = config.get("github_pages_base_url", "").rstrip("/")
    report_url = f"{base_url}/{date_str}.html" if base_url else ""

    deploy_to_pages(html_path, date_str)

    webhook = config.get("feishu_webhook", "")
    if webhook and report_url:
        payload = build_feishu_payload(summaries, date_str, report_url)
        send_feishu(webhook, payload)
    elif webhook:
        payload = build_feishu_payload(summaries, date_str, "")
        send_feishu(webhook, payload)
```

- [ ] **Step 4: Run tests**

Run: `cd ~/ai-wechat-digest && python3 -m pytest tests/test_distributor.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add github_digest/distributor.py tests/test_distributor.py
git commit -m "feat: add distributor module with Feishu webhook and GitHub Pages deploy"
```

---

## Task 7: Entry Point — Pipeline Orchestrator

**Files:**
- Create: `main_github.py`

- [ ] **Step 1: Implement main_github.py**

Create `main_github.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path

from github_digest.config import load_github_config
from github_digest.collector import collect
from github_digest.ranker import rank_repos
from github_digest.summarizer import summarize_all
from github_digest.renderer import render_report
from github_digest.distributor import distribute

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = APP_DIR / "config_github.json"
DATA_DIR = APP_DIR / "data"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GitHub Trending Monitor - collect, summarize, and push daily GitHub picks."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config_github.json")
    parser.add_argument("--step", choices=["collect", "rank", "summarize", "render", "distribute", "all"],
                        default="all", help="Run a single pipeline step")
    parser.add_argument("--date", default=date.today().isoformat(), help="Override date (YYYY-MM-DD)")
    args = parser.parse_args()

    config = load_github_config(Path(args.config))
    day_dir = DATA_DIR / args.date
    day_dir.mkdir(parents=True, exist_ok=True)

    if args.step in ("collect", "all"):
        print(f"[collect] Fetching trending and search results...")
        repos = collect(config)
        with open(day_dir / "trending.json", "w", encoding="utf-8") as f:
            json.dump(repos, f, ensure_ascii=False, indent=2)
        print(f"[collect] {len(repos)} repos collected.")

    if args.step in ("rank", "all"):
        if args.step == "rank":
            with open(day_dir / "trending.json", "r", encoding="utf-8") as f:
                repos = json.load(f)
        print(f"[rank] Scoring and filtering...")
        ranked = rank_repos(repos, config.get("topics", {}), config.get("top_k", 5))
        with open(day_dir / "ranked.json", "w", encoding="utf-8") as f:
            json.dump(ranked, f, ensure_ascii=False, indent=2)
        print(f"[rank] {len(ranked)} repos ranked (top-{config.get('top_k', 5)}).")

    if args.step in ("summarize", "all"):
        if args.step == "summarize":
            with open(day_dir / "ranked.json", "r", encoding="utf-8") as f:
                ranked = json.load(f)
        print(f"[summarize] Generating Chinese summaries via Claude...")
        summaries = summarize_all(ranked, config)
        with open(day_dir / "summaries.json", "w", encoding="utf-8") as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2)
        print(f"[summarize] {len(summaries)} summaries generated.")

    if args.step in ("render", "all"):
        if args.step == "render":
            with open(day_dir / "summaries.json", "r", encoding="utf-8") as f:
                summaries = json.load(f)
        print(f"[render] Rendering HTML report...")
        html_path = day_dir / "report.html"
        render_report(summaries, html_path, args.date)
        print(f"[render] Report saved to {html_path}.")

    if args.step in ("distribute", "all"):
        if args.step == "distribute":
            html_path = day_dir / "report.html"
            with open(day_dir / "summaries.json", "r", encoding="utf-8") as f:
                summaries = json.load(f)
            if not html_path.exists():
                print("[error] report.html not found. Run --step render first.")
                return 1
        print(f"[distribute] Deploying to GitHub Pages and sending Feishu notification...")
        distribute(summaries, html_path, args.date, config)
        print("[distribute] Done.")

    if args.step == "all":
        print(f"\nPipeline complete. Report: {day_dir / 'report.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Test the full pipeline (dry run)**

Run: `cd ~/ai-wechat-digest && python3 main_github.py --help`
Expected: Help text showing `--step`, `--date`, `--config` options.

- [ ] **Step 3: Copy config and test with actual key**

```bash
cp config_github.example.json config_github.json
```

Edit `config_github.json` and fill in the `llm.api_key` (or set `LLM_API_KEY` env var).

- [ ] **Step 4: Run the pipeline manually for testing**

```bash
python3 main_github.py
```

This will run all 5 stages: collect trending repos, rank by keywords, summarize via Claude, render HTML, and attempt to distribute (git push + Feishu may fail without proper tokens — that's fine at this point).

Expected: Pipeline runs through all stages, data directory created with intermediate JSON files.

- [ ] **Step 5: Commit**

```bash
git add main_github.py
git commit -m "feat: add main_github.py pipeline orchestrator"
```

---

## Task 8: Launchd Scheduling

**Files:**
- Create: `launchd/com.user.github-digest.plist`

- [ ] **Step 1: Create launchd plist**

Create `launchd/com.user.github-digest.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.github-digest</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>~/ai-wechat-digest/main_github.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>~/ai-wechat-digest/github-digest.log</string>
    <key>StandardErrorPath</key>
    <string>~/ai-wechat-digest/github-digest.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>LLM_API_KEY</key>
        <string></string>
    </dict>
</dict>
</plist>
```

Note: Fill in `LLM_API_KEY` value in the plist (or remove the EnvironmentVariables section if using config.json).

- [ ] **Step 2: Commit**

```bash
git add launchd/com.user.github-digest.plist
git commit -m "feat: add launchd plist for daily GitHub digest"
```

---

## Plan Self-Review Checklist

- [x] Spec coverage: All 5 modules (collector, ranker, summarizer, renderer, distributor) have corresponding tasks; main_github.py orchestrator covered; config module with env var priority; launchd scheduling covered
- [x] No placeholders: All steps have concrete code, file paths, test assertions, and commands
- [x] Type consistency: `full_name`, `stars_today`, `highlight`, `summaries` fields consistent across modules
- [x] Config structure: `config_github.json` matches the structure expected by all modules via `load_github_config`
- [x] Error handling: Retry logic present in collector (rate limit), summarizer (API failures), distributor (push/webhook failures); Trending scrape failure falls back to Search API only
- [x] Open check: `config_github.json` needs to be manually created from `.example` before first real run
