from __future__ import annotations
import base64
import json
import time
import urllib.error
import urllib.request


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

    base_url = llm_config.get("base_url", "https://ai.t8star.org/v1").rstrip("/")
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {llm_config.get('api_key', '')}",
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
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
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
        try:
            result = summarize_repo(repo, token, llm_config)
            if result:
                results.append(result)
        except Exception as exc:
            print(f"[warn] Unexpected error summarizing {repo.get('full_name', '?')}: {exc}")
    return results
