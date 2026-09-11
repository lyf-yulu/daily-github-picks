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
