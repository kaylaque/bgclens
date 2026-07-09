"""RunRecord: the unit of provenance, reproducibility, and config export."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field


class RunRecord(BaseModel):
    """Complete record of one BGCLens analysis run. Serialises to YAML for export."""
    project_path: str
    inputs_hash: str
    request: dict[str, Any] = Field(default_factory=dict)
    run_spec: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    literature: dict[str, Any] = Field(default_factory=dict)
    llm: dict[str, Any] = Field(default_factory=dict)
    result_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_yaml(self) -> str:
        return yaml.dump({"bgclens_run": self.model_dump()}, sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> "RunRecord":
        data = yaml.safe_load(text)
        return cls(**data["bgclens_run"])

    def save(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / f"bgclens_run_{self.inputs_hash[:8]}.yaml"
        out.write_text(self.to_yaml())
        return out


def hash_project(path: Path) -> str:
    """Stable SHA-256 of the project directory path + mtime of key files."""
    h = hashlib.sha256()
    h.update(str(path).encode())
    for f in sorted(path.rglob("*.csv"))[:20]:
        h.update(str(f.stat().st_mtime).encode())
    return "sha256:" + h.hexdigest()[:32]
