"""Tests for Quarto .qmd renderer — offline, no quarto binary needed."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from bgclens.report.quarto import render, QuartoReport


def _make_run_record(method_id="pcoa", has_svg=False):
    """Build a minimal mock RunRecord."""
    rr = MagicMock()
    rr.method_id = method_id
    rr.result_summary = {
        "_method_id": method_id,
        "_provenance": {"inputs_hash": "abc123", "method_id": method_id, "params": {}},
        "_confidence_band": "green",
    }
    if has_svg:
        rr.result_summary["svg"] = "<svg>test</svg>"
    rr.provenance = {"inputs_hash": "abc123", "method_id": method_id, "params": {}}
    rr.run_id = "test_run_001"
    return rr

def test_render_writes_qmd(tmp_path):
    rr = _make_run_record()
    with patch("bgclens.report.quarto.shutil.which", return_value=None):
        report = render(rr, tmp_path)
    assert report.qmd_path.exists()
    assert report.qmd_path.suffix == ".qmd"
    assert report.rendered is False
    assert "quarto not installed" in report.note

def test_render_qmd_has_params(tmp_path):
    rr = _make_run_record()
    with patch("bgclens.report.quarto.shutil.which", return_value=None):
        report = render(rr, tmp_path)
    content = report.qmd_path.read_text()
    assert "params:" in content
    assert "freeze: auto" in content
    assert "pcoa" in content

def test_render_qmd_has_firewall_badge(tmp_path):
    rr = _make_run_record()
    with patch("bgclens.report.quarto.shutil.which", return_value=None):
        report = render(rr, tmp_path)
    content = report.qmd_path.read_text()
    assert "deterministic" in content or "precedent" in content

def test_render_with_svg_embeds_data(tmp_path):
    rr = _make_run_record(has_svg=True)
    with patch("bgclens.report.quarto.shutil.which", return_value=None):
        report = render(rr, tmp_path)
    content = report.qmd_path.read_text()
    assert "<svg>" in content

def test_render_quarto_installed_calls_subprocess(tmp_path):
    rr = _make_run_record()
    with (
        patch("bgclens.report.quarto.shutil.which", return_value="/usr/bin/quarto"),
        patch("bgclens.report.quarto.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        report = render(rr, tmp_path)
    mock_run.assert_called_once()
    assert "quarto" in mock_run.call_args[0][0][0]

def test_render_quarto_failure_graceful(tmp_path):
    rr = _make_run_record()
    with (
        patch("bgclens.report.quarto.shutil.which", return_value="/usr/bin/quarto"),
        patch("bgclens.report.quarto.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="quarto render error")
        report = render(rr, tmp_path)
    assert report.rendered is False
    assert "quarto render failed" in report.note

def test_render_never_raises_on_broken_record(tmp_path):
    broken = MagicMock()
    broken.method_id = "pcoa"
    broken.result_summary = None  # will cause attribute errors
    broken.provenance = {}
    broken.run_id = "broken"
    with patch("bgclens.report.quarto.shutil.which", return_value=None):
        report = render(broken, tmp_path)
    assert isinstance(report, QuartoReport)
