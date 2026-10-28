"""Studies without a public accession (Vasileva_2024 / UQ RDM): local drop-in folder."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scz_data.fetch.schema import RUN_COLUMNS


class AwaitingAccess(Exception):
    """Raised when the manual folder has not been populated yet."""


REQUIRED = ["sample_name", "fastq_files"]  # fastq_files: ';'-joined paths relative to the study folder


def fetch_project(study_id: str, folder: Path) -> pd.DataFrame:
    meta = folder / "metadata.csv"
    if not meta.exists():
        raise AwaitingAccess(f"SKIPPED: awaiting access - put metadata.csv and FASTQs in {folder}")
    df = pd.read_csv(meta, dtype=str, keep_default_na=False)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{meta}: missing required columns {missing}")
    files = df["fastq_files"].str.split(";")
    absent = [f for fl in files for f in fl if f and not (folder / f).exists()]
    if absent:
        raise FileNotFoundError(f"{len(absent)} FASTQs listed in {meta} not found, e.g. {absent[:3]}")
    out = pd.DataFrame(
        {
            "study_id": study_id,
            "archive": "manual",
            "source_accession": "RDM",
            "run_accession": df.get("run_accession", df["sample_name"]),
            "sample_accession": df.get("sample_accession", df["sample_name"]),
            "sample_name": df["sample_name"],
            "fastq_urls": files.map(lambda fl: ";".join(str((folder / f).resolve()) for f in fl if f)),
            "download_source": "manual",
        }
    )
    for col in df.columns:
        if col in RUN_COLUMNS and col not in out.columns:
            out[col] = df[col]
        elif col not in RUN_COLUMNS and col != "fastq_files":
            out[f"attr_{col.lower()}"] = df[col]
    return out
