from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML


def render_html(template_dir: Path, context: dict, out_html: Path) -> None:
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.get_template("report.html.j2")
    out_html.write_text(tpl.render(**context), encoding="utf-8")


def html_to_pdf(html_path: Path, out_pdf: Path) -> None:
    HTML(filename=str(html_path)).write_pdf(str(out_pdf))
