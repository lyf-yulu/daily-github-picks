from __future__ import annotations
from datetime import datetime, timezone


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
            days_old = (datetime.now(timezone.utc) - datetime.strptime(created[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)).days
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
