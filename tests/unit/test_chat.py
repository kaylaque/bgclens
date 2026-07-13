"""Smoke tests for chat, mentions, and reduce_summary — no LLM calls."""
from pathlib import Path
from unittest.mock import patch
import pytest

from bgclens.model import Cluster, Mention, Turn, PresenceAbsenceMatrix, Project, ProjectManifest
from bgclens.interpret.mentions import parse, _classify
from bgclens.interpret.reduce import reduce_summary
from bgclens.interpret.chat import chat


# ── mention parser ─────────────────────────────────────────────────────────────

def test_parse_basic():
    mentions = parse("What is @GCF_001 and @alpha_diversity?")
    ids = {m.object_id for m in mentions}
    assert "GCF_001" in ids
    assert "alpha_diversity" in ids


def test_parse_whitelist_filters_unknowns():
    mentions = parse("@known_cluster @unknown_thing", whitelist={"known_cluster"})
    assert len(mentions) == 1
    assert mentions[0].object_id == "known_cluster"


def test_parse_empty():
    assert parse("no mentions here") == []


def test_parse_no_whitelist_keeps_all():
    mentions = parse("@a @b @c", whitelist=None)
    assert len(mentions) == 3


def test_classify_cluster():
    assert _classify("gcf_001") == "cluster"
    assert _classify("bgc_abc") == "cluster"
    assert _classify("cluster_x") == "cluster"


def test_classify_method():
    assert _classify("alpha_diversity") == "method"
    assert _classify("permanova") == "method"


def test_classify_report():
    assert _classify("summary") == "report_section"
    assert _classify("analysis_A") == "report_section"


# ── reduce_summary ─────────────────────────────────────────────────────────────

def test_reduce_summary_empty():
    result = reduce_summary([])
    assert "No analysis" in result or len(result) > 0


def test_reduce_summary_dict_records():
    records = [
        {"_cluster_id": "GCF_001", "method": "alpha_diversity", "n_genomes": 10},
        {"_cluster_id": "GCF_002", "method": "alpha_diversity", "n_genomes": 8},
    ]
    # LLM disabled — should return deterministic fallback
    result = reduce_summary(records)
    assert isinstance(result, str)
    assert len(result) > 0


def test_reduce_summary_never_raises():
    # Deliberately malformed input
    result = reduce_summary([None, {}, "bad"])
    assert isinstance(result, str)


# ── chat ──────────────────────────────────────────────────────────────────────

def _make_project():
    pa = PresenceAbsenceMatrix(
        rows=["GCF_001", "GCF_002"],
        cols=["genome_a", "genome_b"],
        values=[[1, 0], [0, 1]],
    )
    return Project(
        manifest=ProjectManifest(
            project_name="test_chat",
            source_path=Path("/tmp/test"),
            available_pipelines={"antismash"},
        ),
        gcf_presence_absence=pa,
    )


def test_chat_returns_turn_no_llm():
    proj = _make_project()
    # LLM disabled by default in test env (no API key configured)
    turn = chat(proj, [], [], "What GCFs are in this project?", [])
    assert isinstance(turn, Turn)
    assert turn.role == "assistant"
    assert len(turn.content) > 0


def test_chat_with_mention():
    from bgclens.model import Mention
    proj = _make_project()
    mentions = [Mention(raw="@GCF_001", object_id="GCF_001", object_type="cluster")]
    turn = chat(proj, [], [], "@GCF_001 how many genomes?", mentions)
    assert turn.role == "assistant"
    assert "GCF_001" in turn.mentions


def test_chat_never_raises():
    """chat() must never raise — always returns a Turn."""
    # Pass broken inputs
    turn = chat(None, [], [], "test", [])  # type: ignore
    assert isinstance(turn, Turn)
    assert turn.role == "assistant"
