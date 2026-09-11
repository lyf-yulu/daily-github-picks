import tempfile
from pathlib import Path
from github_digest.renderer import render_report


def test_render_report_produces_html():
    summaries = [
        {
            "full_name": "owner/repo",
            "title": "测试项目",
            "one_liner": "一句话概括",
            "summary": "这是一个详细的中文摘要",
            "highlights": ["亮点1", "亮点2"],
            "tech_stack": ["Python", "FastAPI"],
            "why_notable": "",
            "stars": 1234,
            "stars_today": 89,
            "url": "https://github.com/owner/repo",
            "diagrams": [
                {"title": "架构图", "mermaid": "graph TD\n  A-->B"}
            ],
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "report.html"
        render_report(summaries, output, date_str="2026-06-10")
        assert output.exists()
        html = output.read_text(encoding="utf-8")
        assert "测试项目" in html
        assert "owner/repo" in html
        assert "graph TD" in html
        assert "mermaid" in html
        assert "1,234" in html or "1234" in html


def test_render_report_highlight_style():
    summaries = [
        {
            "full_name": "hot/repo",
            "title": "热门项目",
            "one_liner": "很火",
            "summary": "摘要",
            "highlights": ["亮点"],
            "tech_stack": ["Rust"],
            "why_notable": "增长极快",
            "stars": 5000,
            "stars_today": 300,
            "url": "https://github.com/hot/repo",
            "diagrams": [],
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "report.html"
        render_report(summaries, output, date_str="2026-06-10")
        html = output.read_text(encoding="utf-8")
        assert "值得关注" in html or "highlight" in html


def test_render_report_empty_summaries():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "report.html"
        render_report([], output, date_str="2026-06-10")
        assert output.exists()
        html = output.read_text(encoding="utf-8")
        assert "今日没有" in html or "没有发现" in html or "GitHub" in html
