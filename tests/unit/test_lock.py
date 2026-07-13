"""Smoke tests for RunRecord.lock() — idempotent, immutable."""
import os
import stat
from pathlib import Path
import tempfile

import pytest

from bgclens.core.provenance import RunRecord


def _make_record(tmp_path: Path) -> tuple[RunRecord, Path]:
    record = RunRecord(
        project_path=str(tmp_path),
        inputs_hash="sha256:abc123",
        run_spec={"method_id": "alpha_diversity", "params": {}},
    )
    report_file = tmp_path / "report_test.qmd"
    report_file.write_text("---\ntitle: Test\n---\nTest report content.")
    return record, report_file


def test_lock_renames_file(tmp_path):
    record, report_file = _make_record(tmp_path)
    locked = record.lock(report_file)
    assert locked.exists()
    assert not report_file.exists()  # original renamed
    assert locked.name != report_file.name  # different name (timestamp prepended)
    assert "qmd" in locked.suffix or locked.suffix == ".qmd"


def test_lock_sets_immutable(tmp_path):
    record, report_file = _make_record(tmp_path)
    locked = record.lock(report_file)
    mode = stat.S_IMODE(locked.stat().st_mode)
    # Should be read-only (0444)
    assert not (mode & stat.S_IWRITE)


def test_lock_marks_record(tmp_path):
    record, report_file = _make_record(tmp_path)
    record.lock(report_file)
    assert record.locked is True
    assert record.locked_at is not None
    assert record.report_path is not None


def test_lock_idempotent(tmp_path):
    record, report_file = _make_record(tmp_path)
    locked1 = record.lock(report_file)
    locked2 = record.lock(locked1)  # call again with locked file
    assert locked1 == locked2  # same path returned


def test_lock_timestamp_prefix(tmp_path):
    record, report_file = _make_record(tmp_path)
    locked = record.lock(report_file)
    # Timestamp format: YYYYMMDDTHHMMSS_slug
    name = locked.name
    # Should start with a digit (year)
    assert name[0].isdigit()
    assert "T" in name  # ISO timestamp separator
