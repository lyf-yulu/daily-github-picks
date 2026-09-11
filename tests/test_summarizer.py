import json
from unittest.mock import patch, MagicMock
from github_digest.summarizer import generate, build_prompt, parse_llm_response, fetch_readme, summarize_all


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
        "diagrams": [{"title": "架构", "mermaid": "graph TD\n  A-->B"}],
    })
    result = parse_llm_response(raw)
    assert result["title"] == "测试项目"
    assert result["diagrams"][0]["title"] == "架构"


def test_parse_llm_response_invalid_json():
    result = parse_llm_response("This is not JSON at all")
    assert result is None


def test_generate_calls_api():
    inner_content = json.dumps({
        "title": "测试",
        "one_liner": "一句话",
        "summary": "摘要",
        "highlights": [],
        "tech_stack": ["Go"],
        "diagrams": [],
    }, ensure_ascii=False)

    fake_response = json.dumps({
        "choices": [{
            "message": {
                "content": inner_content,
            }
        }]
    }, ensure_ascii=False).encode("utf-8")

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


def test_fetch_readme_success():
    fake_response = json.dumps({
        "content": "IyBUZXN0IFByb2plY3QKClRoaXMgaXMgYSB0ZXN0IHJlYWRtZS4="
    }).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_response
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = fetch_readme("owner/repo", "token123")
    assert "# Test Project" in result
    assert "test readme" in result


def test_fetch_readme_failure():
    from urllib.error import URLError
    with patch("urllib.request.urlopen", side_effect=URLError("connection refused")):
        result = fetch_readme("owner/repo", "")
    assert result == ""


def test_summarize_all_handles_partial_failure():
    with patch("github_digest.summarizer.summarize_repo") as mock_summarize:
        mock_summarize.side_effect = [
            {"full_name": "a/b", "title": "Good", "one_liner": "ok", "summary": "good", "stars": 100, "stars_today": 10, "url": "https://github.com/a/b"},
            Exception("Boom"),
            {"full_name": "c/d", "title": "Also Good", "one_liner": "ok", "summary": "also", "stars": 200, "stars_today": 20, "url": "https://github.com/c/d"},
        ]
        config = {"github_token": "", "llm": {}}
        results = summarize_all([{"full_name": "a/b"}, {"full_name": "x/y"}, {"full_name": "c/d"}], config)
    assert len(results) == 2
    assert results[0]["full_name"] == "a/b"
    assert results[1]["full_name"] == "c/d"
