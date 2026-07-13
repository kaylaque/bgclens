"""Optional RO-Crate wrapper for locked BGCLens reports.

Wraps a locked QMD + its provenance YAML + input dataset manifests into a
zip-based RO-Crate archive. Failure is always soft — callers must handle
the case where rocrate_path is None.
"""
from __future__ import annotations
import json
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bgclens.core.provenance import RunRecord

logger = logging.getLogger(__name__)


def wrap(record: "RunRecord", extra_files: list[Path] | None = None) -> Path | None:
    """Build an RO-Crate archive around the locked report + provenance.

    Returns the crate zip path, or None if wrapping fails (soft failure).
    The crate is placed next to the locked report file.
    """
    try:
        if not record.report_path:
            logger.warning("rocrate.wrap: record has no report_path; skipping")
            return None

        report_file = Path(record.report_path)
        if not report_file.exists():
            logger.warning("rocrate.wrap: report file does not exist: %s", report_file)
            return None

        crate_name = report_file.stem + ".crate.zip"
        crate_path = report_file.parent / crate_name

        # Assemble the RO-Crate metadata (ro-crate-metadata.json)
        metadata = {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"},
                },
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "name": f"BGCLens Report: {record.project_path}",
                    "description": "BGCLens analysis report with provenance.",
                    "datePublished": record.locked_at or datetime.now(timezone.utc).isoformat(),
                    "hasPart": [{"@id": report_file.name}],
                },
                {
                    "@id": report_file.name,
                    "@type": "File",
                    "name": report_file.name,
                    "encodingFormat": "text/html" if report_file.suffix == ".html" else "text/plain",
                    "description": "Locked BGCLens report.",
                },
            ],
        }

        files_to_pack: list[Path] = [report_file]
        if extra_files:
            for f in extra_files:
                if f.exists():
                    files_to_pack.append(f)
                    metadata["@graph"][1]["hasPart"].append({"@id": f.name})
                    metadata["@graph"].append({
                        "@id": f.name,
                        "@type": "File",
                        "name": f.name,
                    })

        with zipfile.ZipFile(crate_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("ro-crate-metadata.json", json.dumps(metadata, indent=2))
            for f in files_to_pack:
                zf.write(f, arcname=f.name)

        logger.info("RO-Crate written: %s", crate_path)
        return crate_path

    except Exception as e:
        logger.warning("rocrate.wrap failed (non-fatal): %s", e)
        return None
