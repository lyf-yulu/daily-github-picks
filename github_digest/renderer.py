from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = APP_DIR / "templates"


def render_report(summaries: list[dict], output_path: Path, date_str: str) -> None:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    template = env.get_template("report.html")
    html = template.render(summaries=summaries, date_str=date_str)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
