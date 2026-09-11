import json
from unittest.mock import patch, MagicMock
from github_digest.distributor import build_feishu_payload, send_feishu


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
    assert "测试项目" in json.dumps(data, ensure_ascii=False)
    assert "https://example.com/report.html" in json.dumps(data, ensure_ascii=False)


def test_build_feishu_payload_empty():
    summaries = []
    payload = build_feishu_payload(summaries, "2026-06-10", "https://example.com/report.html")
    data = json.loads(payload)
    assert "没有发现" in json.dumps(data, ensure_ascii=False) or "空" in json.dumps(data, ensure_ascii=False)


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
