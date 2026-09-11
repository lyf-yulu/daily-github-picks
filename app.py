#!/usr/bin/env python3
from __future__ import annotations
import argparse
from html.parser import HTMLParser
import hashlib
import json
import os
import random
import re
import socket
import sqlite3
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Iterable


APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = APP_DIR / "config.json"
DEFAULT_DB = APP_DIR / "sent.sqlite3"


RSS_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


FALLBACK_KNOWLEDGE = [
    {
        "title": "AI 工程知识：评估集要覆盖失败模式",
        "summary": "做 RAG 或 Agent 时，不要只看平均正确率。把误召回、幻觉、工具调用失败、权限边界、长上下文遗漏分别做成小评估集，才能知道每次改动到底改善了哪里。",
        "link": "local://knowledge/evals",
        "source": "本地知识库",
    },
    {
        "title": "计算机知识：缓存失效比缓存本身更难",
        "summary": "缓存能降低延迟和成本，但真正的复杂度在失效策略、热点 key、穿透、雪崩和一致性。上线缓存前，先明确数据允许陈旧多久，以及缓存不可用时系统如何降级。",
        "link": "local://knowledge/cache-invalidation",
        "source": "本地知识库",
    },
    {
        "title": "AI 工程知识：上下文窗口不是记忆",
        "summary": "长上下文能放更多材料，但模型仍可能忽略中间信息。重要事实应结构化、靠近问题、带引用，并通过检索或摘要机制持续维护，而不是全部塞进 prompt。",
        "link": "local://knowledge/context-window",
        "source": "本地知识库",
    },
    {
        "title": "计算机知识：队列让系统从同步压力里解耦",
        "summary": "消息队列适合处理耗时、可重试、峰值明显的任务。关键不是引入队列，而是定义幂等、重试上限、死信处理和可观测性。",
        "link": "local://knowledge/queues",
        "source": "本地知识库",
    },
]


@dataclass(frozen=True)
class Item:
    title: str
    summary: str
    link: str
    source: str
    published_at: str = ""

    @property
    def item_id(self) -> str:
        raw = f"{self.link}|{self.title}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


class ArticleTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "header", "footer", "nav", "aside"}:
            self._skip_depth += 1
        if tag in {"p", "br", "li", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "header", "footer", "nav", "aside"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "li", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self._parts.append(text)

    def text(self) -> str:
        raw = " ".join(self._parts)
        raw = re.sub(r"\s+", " ", raw)
        raw = re.sub(r"(\.|\?|!|。|？|！)\s+", r"\1\n", raw)
        return raw.strip()


def load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def init_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        create table if not exists sent_items (
            id text primary key,
            title text not null,
            link text not null,
            source text not null,
            sent_at text not null
        )
        """
    )
    conn.commit()
    return conn


def is_sent(conn: sqlite3.Connection, item_id: str) -> bool:
    row = conn.execute("select 1 from sent_items where id = ?", (item_id,)).fetchone()
    return row is not None


def mark_sent(conn: sqlite3.Connection, item: Item) -> None:
    conn.execute(
        """
        insert or ignore into sent_items (id, title, link, source, sent_at)
        values (?, ?, ?, ?, ?)
        """,
        (
            item.item_id,
            item.title,
            item.link,
            item.source,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def fetch_url(url: str, timeout: int, accept: str | None = None) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ai-wechat-digest/1.0 (+https://localhost)",
            "Accept": accept or "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def clean_text(value: str | None, limit: int = 240) -> str:
    if not value:
        return ""
    text = unescape(value)
    for old, new in (("<![CDATA[", ""), ("]]>", ""), ("\n", " "), ("\r", " "), ("\t", " ")):
        text = text.replace(old, new)
    while "<" in text and ">" in text:
        start = text.find("<")
        end = text.find(">", start)
        if end == -1:
            break
        text = text[:start] + " " + text[end + 1 :]
    text = " ".join(text.split())
    return textwrap.shorten(text, width=limit, placeholder="...")


def child_text(node: ET.Element, names: Iterable[str]) -> str:
    for name in names:
        child = node.find(name, RSS_NAMESPACES)
        if child is not None and child.text:
            return clean_text(child.text)
    return ""


def child_attr(node: ET.Element, names: Iterable[str], attr: str) -> str:
    for name in names:
        child = node.find(name, RSS_NAMESPACES)
        if child is not None and child.attrib.get(attr):
            return child.attrib[attr]
    return ""


def normalize_link(link: str) -> str:
    link = clean_text(link, limit=500)
    if not link:
        return ""
    parsed = urllib.parse.urlparse(link)
    if not parsed.scheme:
        return link
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(k, v) for k, v in query if not k.lower().startswith("utm_")]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def parse_date(value: str) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return clean_text(value, limit=32)


def parse_feed(xml_bytes: bytes, source_name: str) -> list[Item]:
    root = ET.fromstring(xml_bytes)
    items: list[Item] = []

    rss_items = root.findall(".//item")
    atom_entries = root.findall(".//atom:entry", RSS_NAMESPACES)

    for node in rss_items:
        title = child_text(node, ["title"])
        link = normalize_link(child_text(node, ["link"]))
        summary = child_text(node, ["description", "content:encoded"])
        published = parse_date(child_text(node, ["pubDate", "dc:date"]))
        if title and link:
            items.append(Item(title=title, summary=summary, link=link, source=source_name, published_at=published))

    for node in atom_entries:
        title = child_text(node, ["atom:title"])
        link = normalize_link(child_attr(node, ["atom:link"], "href"))
        summary = child_text(node, ["atom:summary", "atom:content"])
        published = child_text(node, ["atom:published", "atom:updated"])
        if published:
            published = clean_text(published[:10], limit=10)
        if title and link:
            items.append(Item(title=title, summary=summary, link=link, source=source_name, published_at=published))

    return items


def fetch_items(config: dict) -> list[Item]:
    timeout = int(config.get("request_timeout_seconds", 12))
    items: list[Item] = []
    for feed in config.get("feeds", []):
        try:
            xml_bytes = fetch_url(feed["url"], timeout=timeout)
            items.extend(parse_feed(xml_bytes, feed.get("name", feed["url"])))
        except (KeyError, ET.ParseError, urllib.error.URLError, TimeoutError) as exc:
            print(f"[warn] skipped feed {feed.get('name', feed)}: {exc}")
    return items


def get_llm_api_key(config: dict) -> str:
    api_key_env = config.get("llm_api_key_env", config.get("openai_api_key_env", "MOONSHOT_API_KEY"))
    return os.environ.get(api_key_env, "") or config.get("llm_api_key", "") or config.get("openai_api_key", "")


def has_llm_key(config: dict) -> bool:
    return bool(get_llm_api_key(config))


def extract_article_text(item: Item, config: dict) -> str:
    if item.link.startswith("local://"):
        return item.summary

    timeout = int(config.get("request_timeout_seconds", 12))
    limit = int(config.get("article_char_limit", 9000))
    try:
        html_bytes = fetch_url(
            item.link,
            timeout=timeout,
            accept="text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8",
        )
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"[warn] could not fetch article {item.link}: {exc}")
        return item.summary

    html = html_bytes.decode("utf-8", errors="replace")
    extractor = ArticleTextExtractor()
    try:
        extractor.feed(html)
    except Exception as exc:
        print(f"[warn] could not parse article {item.link}: {exc}")
        return item.summary

    text = extractor.text()
    if len(text) < 240:
        return item.summary
    return text[:limit]


def extract_chat_completion_text(data: dict) -> str:
    choices = data.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks = [part.get("text", "") for part in content if isinstance(part, dict)]
        return "\n".join(chunks).strip()
    return ""


def chinese_digest_with_llm(item: Item, article_text: str, config: dict) -> str | None:
    api_key = get_llm_api_key(config)
    if not api_key:
        return None

    prompt = f"""
请把下面这篇计算机或 AI 文章整理成中文微信群消息。

要求：
1. 不要只翻译标题，要提取文章里的关键知识。
2. 用通俗、准确、适合非专家但懂一点技术的人阅读的中文表达。
3. 控制在 500 到 800 个中文字符。
4. 结构固定为：
一句话结论：
为什么重要：
关键知识：
可以怎么用：
5. 不要编造原文没有的信息，不要输出 Markdown 链接。

标题：{item.title}
来源：{item.source}
发布时间：{item.published_at or "未知"}
RSS 摘要：{item.summary}
正文：
{article_text}
""".strip()
    payload_obj = {
        "model": config.get("llm_model", config.get("openai_model", "kimi-k2.6")),
        "messages": [
            {
                "role": "system",
                "content": "你是一个严谨的中文技术编辑，擅长把英文计算机和 AI 新闻解释成通俗中文。",
            },
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": int(config.get("llm_max_completion_tokens", config.get("openai_max_output_tokens", 800))),
    }
    thinking = config.get("llm_thinking", "disabled")
    if thinking in {"enabled", "disabled"}:
        payload_obj["thinking"] = {"type": thinking}

    payload = json.dumps(payload_obj, ensure_ascii=False).encode("utf-8")
    base_url = config.get("llm_base_url", "https://api.moonshot.cn/v1").rstrip("/")
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=int(config.get("llm_timeout_seconds", 45))) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError, ValueError) as exc:
        print(f"[warn] LLM summarization failed: {exc}")
        return None

    return extract_chat_completion_text(data) or None


def rough_chinese_fallback(item: Item) -> str:
    if item.summary:
        return (
            "Kimi 本次调用超时，先发这条新闻的基础信息，避免漏掉内容：\n"
            f"这条来自 {item.source}，主题是「{item.title}」。原始摘要：{item.summary}"
        )
    return (
        "Kimi 本次调用超时，且来源没有提供摘要。"
        f"这条来自 {item.source}，主题是「{item.title}」，可以稍后重试获取中文整理版。"
    )


def choose_item(conn: sqlite3.Connection, config: dict) -> Item | None:
    can_summarize_articles = (
        (not config.get("summarize_articles", True))
        or has_llm_key(config)
        or (not config.get("skip_external_articles_without_openai", True))
    )
    if can_summarize_articles:
        items = fetch_items(config)
        random.shuffle(items)
        for item in items:
            if not is_sent(conn, item.item_id):
                return item
    else:
        print("[info] LLM API Key is empty; external articles are skipped to avoid sending untranslated snippets.")

    for raw in FALLBACK_KNOWLEDGE:
        item = Item(**raw)
        if not is_sent(conn, item.item_id):
            return item
    return None


def build_digest_body(item: Item, config: dict) -> str:
    if not config.get("summarize_articles", True):
        return item.summary

    article_text = extract_article_text(item, config)
    ai_digest = chinese_digest_with_llm(item, article_text, config)
    if ai_digest:
        return ai_digest

    if item.link.startswith("local://"):
        return item.summary

    extracted = clean_text(article_text, limit=int(config.get("fallback_summary_chars", 900)))
    if extracted and extracted != item.summary:
        return f"未配置或未成功调用 Kimi，先发送原文摘录：\n{extracted}"
    if item.summary:
        return rough_chinese_fallback(item)
    return (
        "这条来源没有在 RSS 中提供摘要，且原文页面当前无法直接抓取正文。"
        "脚本已保留标题和出处；配置 Kimi API Key 后，遇到可抓取正文的链接会自动翻译并整理成中文解释。"
    )


def format_message(item: Item, config: dict) -> str:
    date_part = f"\n时间：{item.published_at}" if item.published_at else ""
    body = build_digest_body(item, config)
    summary = f"\n\n{body}" if body else ""
    link = "" if item.link.startswith("local://") else f"\n\n原文：{item.link}"
    message = f"【计算机 / AI 知识与新闻】\n{item.title}\n来源：{item.source}{date_part}{summary}{link}"
    return message[: int(config.get("message_char_limit", 3500))]


def send_wecom(webhook_url: str, text: str, timeout: int) -> None:
    payload = json.dumps({"msgtype": "text", "text": {"content": text}}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    data = json.loads(body)
    if data.get("errcode") != 0:
        raise RuntimeError(f"WeCom webhook failed: {body}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send non-duplicate computer and AI digest to WeChat/WeCom.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.json")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Print the selected message without sending or marking sent")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    conn = init_db(Path(args.db))
    item = choose_item(conn, config)
    if item is None:
        print("No unsent item remains.")
        return 0

    message = format_message(item, config)
    webhook_url = os.environ.get("WECOM_BOT_WEBHOOK") or config.get("wecom_bot_webhook", "")

    if args.dry_run or not webhook_url:
        print(message)
        if not webhook_url and not args.dry_run:
            print("\n[info] WECOM_BOT_WEBHOOK is empty; skipped sending and did not mark as sent.")
        return 0

    send_wecom(webhook_url, message, int(config.get("request_timeout_seconds", 12)))
    mark_sent(conn, item)
    print(f"Sent: {item.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
