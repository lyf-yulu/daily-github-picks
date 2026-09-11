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
