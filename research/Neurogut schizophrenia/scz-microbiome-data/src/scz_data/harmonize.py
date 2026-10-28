"""FR-8: one row per subject across all studies -> results/scz_samples.tsv (+ .parquet, DATA_DICTIONARY.md).

Read counts are single reads (both mates of a pair counted), the unit of the GutMIND 10 M depth filter. In profile
mode full-depth counts come from, in order: a full-sample stream run (exact), the archive read count, or an
estimate from file size (see docs/phase3b.md); `reads_source` says which.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scz_data.settings import Settings

COLUMNS = [
    # PRD FR-8 schema
    "sample_id", "study_id", "accession", "archive", "run_ids", "group", "country", "platform", "layout",
    "diagnosis_criteria", "age", "sex", "bmi", "raw_reads", "clean_reads", "host_removed_reads", "included",
    "exclusion_reason",
    # additions (documented in DATA_DICTIONARY.md)
    "sample_accession", "sample_name", "source_accession", "exclusion_step", "reads_source", "profiled",
    "profile_source", "profile_reads", "n_species", "unclassified_frac", "profile_host_fraction", "profile_qc_flags",
]

DICTIONARY = {
    "sample_id": "`<StudyID>__<archive sample accession>`; unique key, also the column name in the MetaPhlAn tables",
    "study_id": "GutMIND Table S1 StudyID",
    "accession": "study accession from Table S1 (config/studies.yaml)",
    "archive": "archive the metadata came from (ENA / CNGB / GSA)",
    "run_ids": "`;`-joined run accessions merged into this sample",
    "group": "Healthy / SCZ (label source per study: config/label_maps/<StudyID>.yaml)",
    "country": "from Table S1",
    "platform": "sequencing platform (ILLUMINA / BGISEQ / ION_TORRENT)",
    "layout": "PAIRED / SINGLE",
    "diagnosis_criteria": "Table S1 Clinical Assessment (e.g. DSM-IV, ICD-10)",
    "age": "years, if published (archive attributes or paper supplement), else NA",
    "sex": "as published, else NA",
    "bmi": "kg/m2, if published, else NA (Thirion: not published per sample)",
    "raw_reads": "full-depth single reads before QC (exact if streamed whole, else archive count or estimate)",
    "clean_reads": "full-depth reads after fastp; exact only for samples streamed whole, else NA",
    "host_removed_reads": "full-depth reads after fastp + bowtie2 GRCh38 host removal (exact or estimated); "
                          "used for the 10 M depth filter",
    "included": "TRUE if the sample passes every applied FR-4 filter",
    "exclusion_reason": "why it was removed (one reason per sample)",
    "sample_accession": "archive sample accession",
    "sample_name": "submitter's sample name (e.g. BGI ID for Zhu, used to join paper supplements)",
    "source_accession": "archive project the runs belong to (Thirion: SCZ and control projects differ)",
    "exclusion_step": "FR-4 step that removed it (`<n>:<name>`), see results/validation_report.md",
    "reads_source": "where raw/host_removed_reads come from: stream (exact) / archive read_count / "
                    "file-size estimate",
    "profiled": "TRUE if a MetaPhlAn 3 profile exists for this sample",
    "profile_source": "subsample (first N reads, this pipeline) or curatedMetagenomicData (full depth)",
    "profile_reads": "reads in the profiled subsample before QC (NA for curatedMetagenomicData)",
    "n_species": "species with non-zero abundance in the profile",
    "unclassified_frac": "MetaPhlAn 3 UNKNOWN fraction (0-1); recorded, not filtered on (docs/phase3b.md)",
    "profile_host_fraction": "human fraction of the profiled subsample (bowtie2 vs GRCh38)",
    "profile_qc_flags": "runbook red flags: species<10, host>5%, kept<50%, duplicate profile",
}


def _opt(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path, sep="\t") if path.exists() else None


def build(settings: Settings, studies: list[dict]) -> pd.DataFrame:
    res = settings.path("results")
    exact = _opt(settings.path("qc_read_counts"))
    est = _opt(settings.path("read_estimates"))
    pqc = _opt(res / "profiles" / "profile_qc.tsv")
    ext = settings.cfg["profile"].get("external_profiles", {})
    merged = res / "profiles" / "metaphlan_merged.tsv"
    species = pd.read_csv(merged, sep="\t", index_col=0) if merged.exists() else pd.DataFrame()
    n_sub = settings.cfg["profile"]["reads_per_sample"]

    frames = []
    for study in studies:
        sid = study["study_id"]
        src = settings.path("filtered") / f"{sid}.samples.tsv"
        if not src.exists():
            continue
        s = pd.read_csv(src, sep="\t", dtype={"age": str, "sex": str})
        s["accession"] = study["accession"]
        s["country"] = study.get("country")
        s["diagnosis_criteria"] = study.get("diagnosis_criteria")
        s["platform"] = s["instrument_platform"]
        s["layout"] = s["library_layout"]
        frames.append(s)
    if not frames:
        raise RuntimeError("no data/filtered/*.samples.tsv: run `python -m scz_data filter` first")
    s = pd.concat(frames, ignore_index=True)

    s["raw_reads"] = pd.NA
    s["clean_reads"] = pd.NA
    s["host_removed_reads"] = pd.NA
    s["reads_source"] = pd.NA
    if est is not None:
        e = est.set_index("sample_id")
        s["raw_reads"] = s["sample_id"].map(e["est_total_reads"])
        s["host_removed_reads"] = s["sample_id"].map(e["est_host_removed_reads"])
        s["reads_source"] = s["sample_id"].map(e["est_method"])
    if exact is not None:  # exact counts from whole-sample stream runs win
        x = exact.set_index("sample_id")
        hit = s["sample_id"].isin(x.index)
        for col in ("raw_reads", "clean_reads", "host_removed_reads"):
            s.loc[hit, col] = s.loc[hit, "sample_id"].map(x[col])
        s.loc[hit, "reads_source"] = "stream (exact, whole sample)"

    s["profiled"] = s["sample_id"].isin(species.columns)
    s["profile_source"] = pd.NA
    s["profile_reads"] = pd.NA
    s["n_species"] = s["sample_id"].map((species > 0).sum()) if len(species) else pd.NA
    s["profile_host_fraction"] = pd.NA
    s["profile_qc_flags"] = pd.NA
    if pqc is not None:
        q = pqc.set_index("sample_id")
        hit = s["sample_id"].isin(q.index)
        s.loc[hit, "profile_reads"] = s.loc[hit, "sample_id"].map(q["sub_raw_reads"])
        s.loc[hit, "profile_host_fraction"] = s.loc[hit, "sample_id"].map(q["host_fraction"])
        s.loc[hit, "profile_qc_flags"] = s.loc[hit, "sample_id"].map(q["flags"])
        per = s.loc[hit, "study_id"].map(lambda x: n_sub.get(x, n_sub["default"]))
        s.loc[hit, "profile_source"] = "subsample: first " + per.map("{:,}".format) + " reads per file (MetaPhlAn 3)"
    for study_id, e in ext.items():
        m = (s["study_id"] == study_id) & s["profiled"]
        s.loc[m, "profile_source"] = e["source"]

    out = s.reindex(columns=COLUMNS)
    if out["sample_id"].duplicated().any():
        raise RuntimeError("duplicate sample_id in harmonised table")
    for col in ("raw_reads", "clean_reads", "host_removed_reads", "profile_reads", "n_species"):
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
    for col in ("bmi", "unclassified_frac", "profile_host_fraction"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["included"] = out["included"].astype(bool)
    for col in out.columns[out.dtypes == object]:  # mixed int/str IDs (e.g. Li sample_name) -> text
        out[col] = out[col].astype("string")
    out["profiled"] = out["profiled"].astype(bool)
    return out


def write_dictionary(path: Path, df: pd.DataFrame) -> None:
    lines = [
        "# Data dictionary: results/scz_samples.tsv",
        "",
        "One row per subject (archive sample), all SCZ studies of GutMIND Table S1 that are publicly available.",
        "`results/scz_samples.parquet` holds the same table with typed columns. Species abundances are in",
        "`results/profiles/metaphlan_merged.tsv` (species x sample_id, % of classified reads) and",
        "`results/profiles/by_study/<StudyID>.species.tsv`; all taxonomic levels in",
        "`results/profiles/metaphlan_merged_all_levels.tsv`.",
        "",
        "The first 18 columns are the PRD FR-8 schema; the rest are additions.",
        "",
        "| column | type | description |",
        "|---|---|---|",
    ]
    for c in df.columns:
        lines.append(f"| {c} | {df[c].dtype} | {DICTIONARY[c]} |")
    lines += [
        "",
        "Units: read counts are single reads (both mates of a pair counted), matching the GutMIND 10 M depth filter.",
        "NA means not published / not measured, never zero.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(settings: Settings, studies: list[dict]) -> dict[str, str]:
    df = build(settings, studies)
    res = settings.path("results")
    df.to_csv(res / "scz_samples.tsv", sep="\t", index=False)
    try:
        df.to_parquet(res / "scz_samples.parquet", index=False)
        pq = "parquet written"
    except ImportError as e:  # pyarrow/fastparquet missing
        pq = f"parquet NOT written ({e})"
    write_dictionary(res / "DATA_DICTIONARY.md", df)
    status = {}
    for sid, g in df.groupby("study_id", sort=False):
        status[sid] = (f"{len(g)} samples, {int(g['included'].sum())} included "
                       f"({int((g['included'] & (g['group'] == 'Healthy')).sum())} HC / "
                       f"{int((g['included'] & (g['group'] == 'SCZ')).sum())} SCZ), {int(g['profiled'].sum())} profiled")
    status["(all)"] = f"{len(df)} rows -> results/scz_samples.tsv; {pq}"
    return status
