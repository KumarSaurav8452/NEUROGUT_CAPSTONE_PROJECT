"""Common run-level schema for data/raw_metadata/<StudyID>.tsv (PRD FR-2)."""

from __future__ import annotations

import pandas as pd

# One row per sequencing run. Sample attributes follow as attr_<name> columns.
RUN_COLUMNS = [
    "study_id",
    "archive",
    "source_accession",      # project the run was retrieved from
    "run_accession",
    "experiment_accession",
    "sample_accession",
    "sample_name",           # submitter's sample name: the key used to join paper supplements
    "sample_title",
    "library_strategy",
    "library_source",
    "library_layout",        # SINGLE | PAIRED
    "instrument_platform",   # ILLUMINA | BGISEQ | ION_TORRENT | ...
    "instrument_model",
    "read_count",
    "base_count",
    "fastq_urls",            # ';'-joined, https/ftp
    "fastq_md5",             # ';'-joined, same order as fastq_urls
    "fastq_bytes",           # ';'-joined, same order as fastq_urls
    "download_source",       # archive the fastq_* columns point at (differs from archive when a mirror is used)
    "alt_fastq_urls",        # the other archive's copy, if any
]

_LAYOUT = {"paired": "PAIRED", "fragment/single": "SINGLE", "single": "SINGLE"}
_PLATFORM = {"ILLUMINA": "ILLUMINA", "BGISEQ": "BGISEQ", "DNBSEQ": "BGISEQ", "ION_TORRENT": "ION_TORRENT"}


def norm_layout(value: str) -> str:
    v = (value or "").strip()
    return _LAYOUT.get(v.lower(), v.upper())


def norm_platform(value: str) -> str:
    v = (value or "").strip().upper().replace(" ", "_")
    return _PLATFORM.get(v, v)


def platform_from_model(model: str) -> str:
    m = (model or "").lower()
    if "illumina" in m or "hiseq" in m or "novaseq" in m or "nextseq" in m:
        return "ILLUMINA"
    if "bgiseq" in m or "dnbseq" in m or "mgiseq" in m:
        return "BGISEQ"
    if "ion torrent" in m or "proton" in m:
        return "ION_TORRENT"
    return ""


def finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Order columns: standard ones first (created empty if missing), then attr_* sorted."""
    for col in RUN_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    attrs = sorted(c for c in df.columns if c.startswith("attr_"))
    extra = [c for c in df.columns if c not in RUN_COLUMNS and c not in attrs]
    if extra:
        raise ValueError(f"non-schema columns: {extra}")
    return df[RUN_COLUMNS + attrs].sort_values(["sample_accession", "run_accession"]).reset_index(drop=True)


def attr_name(raw: str) -> str:
    return "attr_" + "_".join(str(raw).strip().lower().replace("(", " ").replace(")", " ").split())
