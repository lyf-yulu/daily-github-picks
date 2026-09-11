from __future__ import annotations
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DEPLOY_DIR = Path.home() / "daily-github-picks"
DOCS_DIR = DEPLOY_DIR / "docs" / "reports"


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
                "title": {"tag": "plain_text", "content": f"GitHub 每日精选 | {date_str}"},
                "template": "blue",
            },
            "elements": [
                {"tag": "markdown", "content": md},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看完整报告"},
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
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=utf-8>"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>GitHub 每日精选 历史报告</title>"
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:600px;margin:2rem auto;padding:0 1rem;background:#f8f9fa;color:#1a1a2e}"
        "@media(prefers-color-scheme:dark){body{background:#0d1117;color:#c9d1d9}}"
        "h1{font-size:1.5rem}a{color:#667eea;text-decoration:none}"
        "li{margin:0.5rem 0}</style></head><body>"
        f"<h1>GitHub 每日精选 历史报告</h1><ul>{''.join(links[:30])}</ul></body></html>"
    )
    index.write_text(index_html, encoding="utf-8")

    for attempt in range(2):
        try:
            subprocess.run(["git", "checkout", "--", "."],
                           cwd=str(DEPLOY_DIR), check=True, capture_output=True)
            subprocess.run(["git", "pull", "--rebase"],
                           cwd=str(DEPLOY_DIR), check=True, capture_output=True)
            subprocess.run(["git", "add", "docs/"],
                           cwd=str(DEPLOY_DIR), check=True)
            subprocess.run(
                ["git", "commit", "-m",
                 f"report: GitHub daily digest {date_str}",
                 "--allow-empty"],
                cwd=str(DEPLOY_DIR), check=True)
            subprocess.run(["git", "push"], cwd=str(DEPLOY_DIR), check=True)
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
