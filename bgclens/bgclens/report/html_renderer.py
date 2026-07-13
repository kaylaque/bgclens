"""Self-contained HTML report renderer using Jinja2.

Renders RunRecord / BatchReport to HTML. No QMD/Quarto dependency.
LLM interpretation markdown is converted to HTML inline.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from bgclens.report.quarto import QuartoReport, _safe_get

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _clean_md(text: str) -> str:
    """Fix common LLM markdown artifacts before HTML conversion."""
    import re
    # Ensure ## headers are on their own line (LLM sometimes writes "## Header\ntext" without blank line after)
    text = re.sub(r'(#{1,3} [^\n]+)\n([^\n#])', r'\1\n\n\2', text)
    # Ensure blank line BEFORE a header if there's content above it
    text = re.sub(r'([^\n])\n(#{1,3} )', r'\1\n\n\2', text)
    # Replace literal \n (escaped newline as two chars) with real newline
    text = text.replace('\\n', '\n')
    # Replace \t with spaces
    text = text.replace('\\t', '    ')
    # Collapse more-than-two consecutive blank lines to two
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Fix **bold** that lost spacing: "word**bold**word" → "word **bold** word"
    text = re.sub(r'(\w)(\*\*\w)', r'\1 \2', text)
    text = re.sub(r'(\*\*\w+\*\*)(\w)', r'\1 \2', text)
    # Remove stray backslash escapes before punctuation (e.g., \. \, \*)
    text = re.sub(r'\\([.,!?;:()\[\]{}])', r'\1', text)
    return text.strip()


def _md_to_html(text: str) -> str:
    """Clean markdown then convert to HTML."""
    if not text:
        return ""
    text = _clean_md(text)
    try:
        import markdown as _md
        return _md.markdown(text, extensions=["nl2br", "tables", "fenced_code"])
    except Exception:
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        return "".join(f"<p>{p}</p>" for p in paras) or f"<p>{text}</p>"


def _extract_metrics(result_summary: dict) -> dict[str, Any]:
    skip = {"svg", "png", "interpretation", "method", "_cluster_id", "_method_id"}
    out = {}
    for k, v in (result_summary or {}).items():
        if k.startswith("_") or k in skip:
            continue
        if isinstance(v, (int, float, str)) and not isinstance(v, bool):
            text = str(v)
            if len(text) <= 30:
                out[k] = text
        if len(out) >= 6:
            break
    return out


def _record_to_section(rec: Any, idx: int) -> dict:
    rs = _safe_get(rec, "result_summary", {}) or {}
    run_spec = _safe_get(rec, "run_spec", {}) or {}
    method_id = (
        run_spec.get("method_id") if isinstance(run_spec, dict) else None
    ) or _safe_get(rec, "method_id", f"analysis_{idx}") or f"analysis_{idx}"
    cluster_id = (run_spec.get("cluster_id", "") if isinstance(run_spec, dict) else "") or ""
    inputs_hash = _safe_get(rec, "inputs_hash", "") or ""
    created_at = _safe_get(rec, "created_at", "") or ""
    confidence_band = rs.get("_confidence_band", rs.get("confidence_band", "")) if isinstance(rs, dict) else ""

    anchor = f"sec-{method_id}-{cluster_id or idx}".replace(" ", "-").replace("/", "-")

    interp_text = rs.get("interpretation", "") if isinstance(rs, dict) else ""
    interp_html = _md_to_html(interp_text)

    provenance = {
        "method_id": method_id,
        "cluster_id": cluster_id,
        "inputs_hash": inputs_hash[:16] if inputs_hash else "",
        "created_at": str(created_at),
    }

    return {
        "anchor": anchor,
        "method_id": method_id,
        "cluster_id": cluster_id,
        "svg": rs.get("svg", "") if isinstance(rs, dict) else "",
        "interpretation_html": interp_html,
        "confidence_band": (confidence_band or "").replace(" ", "-").lower(),
        "metrics": _extract_metrics(rs if isinstance(rs, dict) else {}),
        "provenance_json": json.dumps(provenance, indent=2, default=str),
    }


def _render_html(template_vars: dict, out_path: Path) -> None:
    env = _jinja_env()
    tmpl = env.get_template("report.html")
    html = tmpl.render(**template_vars)
    out_path.write_text(html, encoding="utf-8")


def render(run_record: Any, out_dir: Path | str) -> QuartoReport:
    """Render a single RunRecord to HTML. Never raises."""
    try:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        section = _record_to_section(run_record, 0)
        project_name = (
            Path(_safe_get(run_record, "project_path", "") or "").name or "BGCLens"
        )

        vars_ = {
            "project_name": project_name,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "summary": "",
            "sections": [section],
            "comparison": {},
        }

        html_path = out_dir / f"{section['method_id']}_{section['anchor']}.html"
        _render_html(vars_, html_path)

        return QuartoReport(
            qmd_path=None,
            html_path=html_path,
            rendered=True,
            note="rendered by Python/Jinja2",
        )
    except Exception as exc:
        return QuartoReport(
            qmd_path=None,
            html_path=None,
            rendered=False,
            note=f"html render error: {exc}",
        )


def render_batch(batch_report: Any, out_dir: Path | str) -> QuartoReport:
    """Render a BatchReport (multiple analyses) to a single HTML file. Never raises."""
    try:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        project_name = getattr(batch_report, "project_name", "BGCLens") or "BGCLens"
        records = getattr(batch_report, "records", []) or []
        summary = getattr(batch_report, "summary", "") or ""
        comparison = getattr(batch_report, "cluster_comparison", {}) or {}

        sections = [_record_to_section(rec, i) for i, rec in enumerate(records)]

        batch_hash = hashlib.sha256(project_name.encode()).hexdigest()[:8]
        vars_ = {
            "project_name": project_name,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "summary": _md_to_html(summary),
            "sections": sections,
            "comparison": comparison,
        }

        html_path = out_dir / f"batch_report_{batch_hash}.html"
        _render_html(vars_, html_path)

        return QuartoReport(
            qmd_path=None,
            html_path=html_path,
            rendered=True,
            note="rendered by Python/Jinja2",
        )
    except Exception as exc:
        return QuartoReport(
            qmd_path=None,
            html_path=None,
            rendered=False,
            note=f"html batch render error: {exc}",
        )
