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
        "base_url": "https://ai.t8star.org/v1",
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
