"""Quarto .qmd report renderer for BGCLens run records.

Thin add-on: writes a .qmd from a RunRecord, then shells out to
`quarto render` if quarto is on PATH. Falls back to .qmd-only if not.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class QuartoReport:
    qmd_path: Path
    html_path: Path | None   # None if quarto not installed
    rendered: bool
    note: str = ""


def _safe_get(obj, attr, default=None):
    """Safely get attribute, falling back to default."""
    try:
        val = getattr(obj, attr, default)
        return val if val is not None else default
    except Exception:
        return default


def _build_qmd(method_id: str, run_id: str, method_hash: str,
               provenance: dict, result_summary: dict | None,
               has_literature: bool = False) -> str:
    """Build the .qmd document content."""
    badge = "precedent" if has_literature else "deterministic"

    # Embed SVG if present
    viz_section = ""
    try:
        if result_summary and isinstance(result_summary, dict):
            svg = result_summary.get("svg")
            if svg:
                viz_section = f"\n## Visualization\n\n{svg}\n"
            else:
                png = result_summary.get("png")
                if png:
                    import base64
                    b64 = base64.b64encode(png if isinstance(png, bytes) else png.encode()).decode()
                    viz_section = f'\n## Visualization\n\n![Figure](data:image/png;base64,{b64})\n'
    except Exception:
        pass

    # Embed interpretation if present
    interp_section = ""
    try:
        if result_summary and isinstance(result_summary, dict):
            interp = result_summary.get("interpretation") or result_summary.get("_interpretation", "")
            if interp:
                interp_section = f"\n::: {{.interpretation}}\n{interp}\n:::\n"
    except Exception:
        pass

    qmd = f"""---
title: "BGCLens Report: {method_id}"
params:
  method_id: "{method_id}"
  run_id: "{run_id}"
execute:
  freeze: auto
---

<!-- method_hash: {method_hash} -->

**Method:** `{method_id}`
**Run ID:** `{run_id}`
**Firewall badge:** `{badge}`
**Method source hash:** `{method_hash}`
{viz_section}{interp_section}
## Provenance

```json
{json.dumps(provenance, indent=2, default=str)}
```
"""
    return qmd


def render(run_record, out_dir: Path | str) -> QuartoReport:
    """Render a RunRecord to a Quarto .qmd document (and HTML if quarto installed).

    The .qmd uses `params:` for method_id, `freeze: auto` for caching,
    and embeds the viz SVG as a data URI and the interpret markdown inline.

    Returns QuartoReport. Never raises.
    """
    try:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Safely extract fields — handle both real RunRecord and mocks
        result_summary = _safe_get(run_record, "result_summary", None)

        # Real RunRecord stores method in run_spec; mocks may expose method_id directly
        run_spec = _safe_get(run_record, "run_spec", {}) or {}
        method_id = (
            run_spec.get("method_id") if isinstance(run_spec, dict) else None
        ) or _safe_get(run_record, "method_id", "unknown") or "unknown"

        # Real RunRecord uses inputs_hash as the run identifier; mocks expose run_id
        inputs_hash = _safe_get(run_record, "inputs_hash", "") or ""
        run_id = inputs_hash[:16] if inputs_hash else (_safe_get(run_record, "run_id", "unknown") or "unknown")

        # Build provenance from real RunRecord fields (inputs_hash + run_spec + params)
        provenance = _safe_get(run_record, "provenance", {}) or {}
        if not provenance:
            provenance = {
                "inputs_hash": inputs_hash,
                **(run_spec if isinstance(run_spec, dict) else {}),
            }

        # Compute method hash from provenance
        try:
            method_hash = hashlib.sha256(
                json.dumps(provenance, sort_keys=True, default=str).encode()
            ).hexdigest()[:12]
        except Exception:
            method_hash = "000000000000"

        # Determine if this run was literature-backed (RunRecord.literature non-empty)
        literature = _safe_get(run_record, "literature", {}) or {}
        has_literature = bool(literature and isinstance(literature, dict))

        # Build .qmd filename and content
        qmd_filename = f"{method_id}_{method_hash}.qmd"
        qmd_path = out_dir / qmd_filename

        try:
            qmd_content = _build_qmd(method_id, run_id, method_hash, provenance, result_summary, has_literature)
        except Exception as e:
            qmd_content = f"---\ntitle: BGCLens Report\nparams:\n  method_id: \"{method_id}\"\n  run_id: \"{run_id}\"\nexecute:\n  freeze: auto\n---\n\n<!-- method_hash: {method_hash} -->\n\n**Firewall badge:** `deterministic`\n\n*Report generation error: {e}*\n"

        qmd_path.write_text(qmd_content)

        # Try to run quarto if available
        quarto_bin = shutil.which("quarto")
        if quarto_bin is None:
            return QuartoReport(
                qmd_path=qmd_path,
                html_path=None,
                rendered=False,
                note="quarto not installed; .qmd written",
            )

        result = subprocess.run(
            ["quarto", "render", str(qmd_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return QuartoReport(
                qmd_path=qmd_path,
                html_path=None,
                rendered=False,
                note=f"quarto render failed: {result.stderr[:200]}",
            )

        html_path = qmd_path.with_suffix(".html")
        return QuartoReport(
            qmd_path=qmd_path,
            html_path=html_path if html_path.exists() else None,
            rendered=True,
            note="",
        )

    except Exception as exc:
        # render() must never raise — return a spec-compliant fallback .qmd
        fallback_path = Path(out_dir) / "report_error.qmd"
        try:
            fallback_path.write_text(
                "---\ntitle: BGCLens Report (error)\nparams:\n  method_id: \"unknown\"\n  run_id: \"unknown\"\nexecute:\n  freeze: auto\n---\n\n"
                "<!-- firewall: deterministic -->\n\n"
                f"*Render error: {exc}*\n"
            )
        except Exception:
            pass
        return QuartoReport(
            qmd_path=fallback_path,
            html_path=None,
            rendered=False,
            note=f"render error: {exc}",
        )
