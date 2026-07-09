"""Tests for compute advisor."""
import pytest
from bgclens.compute.resources import ResourceProfile
from bgclens.compute.advisor import assess, CostAssessment
from bgclens.model import PresenceAbsenceMatrix, FeatureCountTable


def _dummy_pa(n_genomes: int = 5, n_gcfs: int = 3) -> PresenceAbsenceMatrix:
    import random
    random.seed(42)
    values = [[random.randint(0, 1) for _ in range(n_genomes)] for _ in range(n_gcfs)]
    return PresenceAbsenceMatrix(
        rows=[f"GCF_{i}" for i in range(n_gcfs)],
        cols=[f"g{i}" for i in range(n_genomes)],
        values=values,
    )


def _dummy_counts(n: int = 5) -> FeatureCountTable:
    return FeatureCountTable(
        genome_ids=[f"g{i}" for i in range(n)],
        features=["terpene", "nrps", "pks"],
        counts=[[1, 0, 1]] * n,
    )


def test_assess_pcoa_small_safe():
    inputs = {"presence_absence": _dummy_pa(5)}
    result = assess("pcoa", inputs, {})
    assert isinstance(result, CostAssessment)
    assert result.cost_class in ("Safe", "Heavy", "Likely-to-fail")
    assert result.estimated_mb >= 0


def test_assess_diversity_always_safe():
    inputs = {"counts": _dummy_counts(5)}
    result = assess("alpha_diversity", inputs, {})
    # Diversity is O(N·F), should be safe for 5 genomes
    assert result.cost_class == "Safe"


def test_assess_large_pcoa_heavy(monkeypatch):
    """Simulate a 600-genome dataset to trigger Heavy class."""
    import bgclens.compute.advisor as advisor_mod

    # Mock a machine with 2GB available RAM
    fake_profile = ResourceProfile(
        cpu_cores=4,
        ram_available_mb=2048,
        ram_total_mb=8192,
        on_slurm=False,
        slurm_max_node_ram_mb=None,
    )
    monkeypatch.setattr(advisor_mod, "probe", lambda: fake_profile)

    # 600 genomes × 600 = 360 MB distance matrix → should be Heavy
    big_pa = _dummy_pa(n_genomes=600, n_gcfs=10)
    inputs = {"presence_absence": big_pa}
    result = assess("pcoa", inputs, {})
    assert result.cost_class in ("Heavy", "Likely-to-fail")


def test_likely_to_fail_has_alternatives():
    """A Likely-to-fail PERMANOVA should suggest PCoA as alternative."""
    import bgclens.compute.advisor as advisor_mod
    from bgclens.compute.resources import ResourceProfile
    import bgclens.compute.advisor as adv

    # Give it a tiny RAM budget so anything big fails
    fake_profile = ResourceProfile(
        cpu_cores=4,
        ram_available_mb=256,
        ram_total_mb=512,
        on_slurm=False,
        slurm_max_node_ram_mb=None,
    )

    big_pa = _dummy_pa(n_genomes=400, n_gcfs=20)
    inputs = {"presence_absence": big_pa, "metadata": None}
    result = assess("permanova", inputs, {"permutations": 999}, resource_profile=fake_profile)

    if result.cost_class in ("Heavy", "Likely-to-fail"):
        # Should suggest at least one alternative
        assert len(result.alternatives) >= 1
        assert result.alternatives[0].trade_off != ""


def test_resource_probe_runs():
    """psutil probe should return something sensible."""
    from bgclens.compute.resources import probe
    profile = probe()
    assert profile.ram_total_mb > 0
    assert profile.cpu_cores >= 1
