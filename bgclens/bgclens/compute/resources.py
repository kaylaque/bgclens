"""Detect available compute resources on the local machine or cluster."""
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class ResourceProfile:
    cpu_cores: int
    ram_available_mb: float
    ram_total_mb: float
    on_slurm: bool
    slurm_max_node_ram_mb: float | None  # None if SLURM not detected or sinfo fails


def probe() -> ResourceProfile:
    """Probe the current machine for available resources."""
    import psutil

    mem = psutil.virtual_memory()
    cpu = psutil.cpu_count(logical=False) or psutil.cpu_count() or 1

    on_slurm = shutil.which("sinfo") is not None
    slurm_max: float | None = None
    if on_slurm:
        slurm_max = _parse_sinfo_max_ram()

    return ResourceProfile(
        cpu_cores=cpu,
        ram_available_mb=mem.available / 1024 / 1024,
        ram_total_mb=mem.total / 1024 / 1024,
        on_slurm=on_slurm,
        slurm_max_node_ram_mb=slurm_max,
    )


def _parse_sinfo_max_ram() -> float | None:
    """Read max memory from sinfo --noheader -o '%m'. Returns MB or None."""
    try:
        result = subprocess.run(
            ["sinfo", "--noheader", "-o", "%m"],
            capture_output=True, text=True, timeout=5
        )
        values = []
        for line in result.stdout.strip().splitlines():
            line = line.strip().rstrip("+")
            try:
                values.append(float(line))
            except ValueError:
                pass
        return max(values) if values else None
    except Exception:
        return None
