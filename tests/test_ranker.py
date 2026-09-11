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
