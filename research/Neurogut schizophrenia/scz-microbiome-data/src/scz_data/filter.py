"""FR-4: filter labelled runs to one row per subject and compare with Table S1 "Filtered" counts.

Steps, applied in order; every sample removed is attributed to exactly one step:
  1 shotgun        keep runs whose library_strategy is shotgun (WGS); 16S etc. dropped and flagged
  2 platform       keep runs on the study's platform (Zhu A/B; already split at fetch, re-checked here)
  3 baseline       drop label-stage exclusions (follow-ups, non-human, donors, unmapped) and merge runs per sample
  4 bmi            GutMIND: BMI > max_bmi dropped (NA kept); skipped where per-sample BMI is not published
  5 depth          GutMIND: < min_reads after QC + host removal; pending until results/qc/read_counts.tsv
                   (columns sample_id, host_removed_reads = reads left after host removal) exists
  6 unclassified   GutMIND: > 30 % unclassified (MetaPhlAn 4); pending until
                   results/profiles/metaphlan_unclassified.tsv (sample_id, unclassified_frac) exists
Then: study-size check (GutMIND discards a study with < min_study_samples left) and count comparison.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scz_data.settings import Settings, get_logger
from scz_data.validate import compare_counts

STEPS = [
    (1, "shotgun", "keep shotgun metagenomic runs"),
    (2, "platform", "keep runs on the study platform"),
    (3, "baseline", "drop non-baseline / non-human / unlabelled samples; merge runs per sample"),
    (4, "bmi", "drop BMI > {max_bmi} (NA kept)"),
    (5, "depth", "drop < {min_reads:,} reads after QC + host removal"),
    (6, "unclassified", "drop > {max_unclassified_frac:.0%} unclassified at species level"),
]

SAMPLE_COLUMNS = [
    "sample_id", "study_id", "archive", "source_accession", "sample_accession", "sample_name", "group",
    "run_ids", "n_runs", "library_strategy", "instrument_platform", "library_layout", "archive_read_count", "published_reads",
    "fastq_urls", "fastq_md5", "fastq_bytes", "total_bytes", "download_source",
    "age", "sex", "bmi", "diagnosis_detail", "clean_reads", "unclassified_frac",
    "included", "exclusion_step", "exclusion_reason", "pending_filters",
]


def _join(values) -> str:
    return ";".join(str(v) for v in values if pd.notna(v) and str(v) != "")


def _uniq(values) -> str:
    return ";".join(sorted({str(v) for v in values if pd.notna(v) and str(v) != ""}))


def merge_runs(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per sample_accession; multiple runs of one sample (top-up lanes) are merged."""
    rows = []
    for acc, g in runs.groupby("sample_accession", sort=True):
        groups = g["group"].dropna().unique()
        if len(groups) > 1:
            raise ValueError(f"sample {acc}: runs carry conflicting labels {list(groups)}")
        rc = pd.to_numeric(g["read_count"], errors="coerce")
        sizes = [int(b) for s in g["fastq_bytes"].dropna() for b in str(s).split(";") if b]
        first = g.iloc[0]
        rows.append(
            {
                "sample_id": f"{first['study_id']}__{acc}",
                "study_id": first["study_id"],
                "archive": first["archive"],
                "source_accession": first["source_accession"],
                "sample_accession": acc,
                "sample_name": first["sample_name"],
                "group": groups[0] if len(groups) else pd.NA,
                "run_ids": _join(g["run_accession"]),
                "n_runs": len(g),
                "library_strategy": _uniq(g["library_strategy"]),
                "instrument_platform": _uniq(g["instrument_platform"]),
                "library_layout": _uniq(g["library_layout"]),
                "archive_read_count": int(rc.sum()) if rc.notna().all() else pd.NA,
                "fastq_urls": _join(g["fastq_urls"]),
                "fastq_md5": _join(g["fastq_md5"]),
                "fastq_bytes": _join(g["fastq_bytes"]),
                "total_bytes": sum(sizes),
                "download_source": _uniq(g["download_source"]),
                "age": first.get("age"),
                "sex": first.get("sex"),
                "bmi": pd.to_numeric(first.get("bmi"), errors="coerce"),
                "diagnosis_detail": first.get("diagnosis_detail"),
                # full-depth read count printed in the paper's supplement (single reads), e.g. Xu ST1
                "published_reads": pd.to_numeric(g["published_reads"], errors="coerce").sum(min_count=1)
                if "published_reads" in g else pd.NA,
                "label_exclusion_reason": first.get("exclusion_reason"),
            }
        )
    return pd.DataFrame(rows)


def _read_optional(path: Path, value_col: str) -> pd.Series | None:
    if not path.exists():
        return None
    df = pd.read_csv(path, sep="\t")
    return df.set_index("sample_id")[value_col]


def filter_study(
    runs: pd.DataFrame,
    study: dict,
    fcfg: dict,
    clean_reads: pd.Series | None = None,
    unclassified: pd.Series | None = None,
) -> tuple[pd.DataFrame, list[dict]]:
    """Return (one row per sample with included/exclusion_* columns, waterfall rows)."""
    runs = runs.copy()
    shotgun = runs["library_strategy"].isin(fcfg["shotgun_strategies"])
    platform = study.get("platform_split")
    on_platform = runs["instrument_platform"].eq(platform) if platform else pd.Series(True, index=runs.index)

    # Per-sample: does any run survive steps 1 / 2? Files of failing runs are not carried into the sample row.
    acc = runs["sample_accession"]
    has_shotgun = shotgun.groupby(acc).any()
    has_platform = (shotgun & on_platform).groupby(acc).any()
    kept_runs = runs[shotgun & on_platform]
    merged_all = merge_runs(runs).set_index("sample_accession")
    merged_kept = merge_runs(kept_runs).set_index("sample_accession") if len(kept_runs) else merged_all.iloc[0:0]
    samples = merged_all.copy()
    samples.update(merged_kept)  # samples with surviving runs describe only those runs
    samples = samples.reset_index()

    samples["included"] = True
    samples["exclusion_step"] = pd.NA
    samples["exclusion_reason"] = pd.NA
    samples["pending_filters"] = ""
    samples["clean_reads"] = samples["sample_id"].map(clean_reads) if clean_reads is not None else pd.NA
    samples["unclassified_frac"] = samples["sample_id"].map(unclassified) if unclassified is not None else pd.NA

    waterfall = []

    def drop(step: int, name: str, mask: pd.Series, reasons, status: str = "applied", note: str = ""):
        mask = mask & samples["included"]
        removed = samples[mask]
        samples.loc[mask, "included"] = False
        samples.loc[mask, "exclusion_step"] = f"{step}:{name}"
        samples.loc[mask, "exclusion_reason"] = reasons[mask] if isinstance(reasons, pd.Series) else reasons
        kept = samples[samples["included"]]
        desc = next(d for s, n, d in STEPS if s == step).format(**fcfg)
        waterfall.append(
            {
                "study_id": study["study_id"], "step": step, "name": name, "description": desc, "status": status,
                "removed_healthy": int((removed["group"] == "Healthy").sum()),
                "removed_scz": int((removed["group"] == "SCZ").sum()),
                "removed_unlabelled": int((~removed["group"].isin(["Healthy", "SCZ"])).sum()),
                "remaining_healthy": int((kept["group"] == "Healthy").sum()),
                "remaining_scz": int((kept["group"] == "SCZ").sum()),
                "note": note,
            }
        )

    none = pd.Series(False, index=samples.index)
    by_acc = samples["sample_accession"]

    # 1 shotgun
    not_shotgun = ~by_acc.map(has_shotgun).astype(bool)
    drop(1, "shotgun", not_shotgun, "not shotgun: " + samples["library_strategy"].astype(str),
         note=f"{int(not_shotgun.sum())} non-shotgun samples flagged" if not_shotgun.any() else "")

    # 2 platform
    off = ~by_acc.map(has_platform).astype(bool)
    drop(2, "platform", off, f"not on platform {platform}",
         note=f"split on {platform} (applied at fetch; re-checked)" if platform else "single-platform study")

    # 3 baseline / label exclusions; merge
    excl = samples["group"].eq("Exclude") | samples["group"].isna()
    multi = int((samples["included"] & ~excl & (samples["n_runs"] > 1)).sum())
    drop(3, "baseline", excl, samples["label_exclusion_reason"].fillna("unlabelled"),
         note=f"{multi} kept samples have >1 run, merged" if multi else "")

    # 4 BMI
    max_bmi = fcfg["max_bmi"]
    if not study.get("bmi_filter", True):
        drop(4, "bmi", none, "", status="skipped", note="per-sample BMI not published (study_overrides.bmi_filter: false)")
    elif samples.loc[samples["included"], "bmi"].isna().all():
        drop(4, "bmi", none, "", status="no-op", note="no BMI available for this study (NA kept)")
    else:
        bmi = pd.to_numeric(samples["bmi"], errors="coerce")
        n_na = int((samples["included"] & bmi.isna()).sum())
        drop(4, "bmi", bmi > max_bmi, "BMI " + bmi.round(1).astype(str) + f" > {max_bmi}",
             note=f"{n_na} kept with BMI NA" if n_na else "")

    # 5 depth, 6 unclassified: need FR-6 / FR-7 outputs
    for step, name, col, op, thr in (
        (5, "depth", "clean_reads", "lt", fcfg["min_reads"]),
        (6, "unclassified", "unclassified_frac", "gt", fcfg["max_unclassified_frac"]),
    ):
        if step == 6 and not fcfg.get("apply_unclassified_filter", True):
            # The value is still recorded per sample; only the cut-off is not applied.
            samples["unclassified_frac"] = pd.to_numeric(samples[col], errors="coerce")
            drop(6, name, none, "", status="skipped", note=fcfg.get("unclassified_skip_reason", "disabled in config"))
            continue
        vals = pd.to_numeric(samples[col], errors="coerce")
        missing = samples["included"] & vals.isna()
        samples.loc[missing, "pending_filters"] = samples.loc[missing, "pending_filters"].map(
            lambda p: f"{p};{name}" if p else name)
        fail = vals.lt(thr) if op == "lt" else vals.gt(thr)
        if vals[samples["included"]].isna().all():
            status = "pending"
        else:
            status = "partial" if missing.any() else "applied"
        label = f"{col} " + vals.astype(str) + (f" < {thr}" if op == "lt" else f" > {thr}")
        drop(step, name, fail.fillna(False), label, status=status,
             note=f"{int(missing.sum())} samples awaiting {'QC' if step == 5 else 'MetaPhlAn'}" if missing.any() else "")

    samples = samples.drop(columns=["label_exclusion_reason"])
    return samples[SAMPLE_COLUMNS], waterfall


def count_comparison(study: dict, samples: pd.DataFrame, waterfall: list[dict], fcfg: dict) -> list[dict]:
    kept = samples[samples["included"]]
    pending = sorted({w["name"] for w in waterfall if w["status"] in ("pending", "partial")})
    skipped = sorted({w["name"] for w in waterfall if w["status"] == "skipped"})
    rows = []
    for group, key in (("Healthy", "healthy_filtered"), ("SCZ", "scz_filtered")):
        exp, got = study["expected"][key], int((kept["group"] == group).sum())
        now = compare_counts(exp, got, fcfg["count_tolerance"])
        rows.append(
            {
                "study_id": study["study_id"], "group": group, "expected_filtered": exp, "obtained": got,
                "diff": got - exp,
                # Pending filters can only remove samples, so a surplus is not a verdict yet; a deficit already is.
                "status": "PENDING" if pending and got > exp and now != "PASS" else now,
                "status_if_final": now,
                "pending_filters": ";".join(pending), "skipped_filters": ";".join(skipped),
            }
        )
    return rows


def run(settings: Settings, studies: list[dict]) -> dict[str, str]:
    fcfg = settings.cfg["filters"]
    out_dir = settings.path("filtered")
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_reads = _read_optional(settings.path("qc_read_counts"), "host_removed_reads")  # exact (full stream)
    estimated = _read_optional(settings.path("read_estimates"), "est_host_removed_reads")  # profile mode
    if estimated is not None:
        clean_reads = estimated if clean_reads is None else clean_reads.combine_first(estimated)
    unclassified = _read_optional(settings.path("unclassified"), "unclassified_frac")
    status, waterfall_all, counts_all = {}, [], []
    for study in studies:
        sid = study["study_id"]
        log = get_logger(settings, "filter", sid)
        src = settings.path("labelled") / f"{sid}.tsv"
        if not src.exists():
            log.warning(f"SKIPPED: no labelled metadata ({src.name})")
            status[sid] = "SKIPPED: no labelled metadata"
            continue
        try:
            runs = pd.read_csv(src, sep="\t", dtype=str, keep_default_na=False, na_values=[""])
            samples, waterfall = filter_study(runs, study, fcfg, clean_reads, unclassified)
            if samples["sample_id"].duplicated().any():
                raise RuntimeError("duplicate sample_id after merge")
            samples.to_csv(out_dir / f"{sid}.samples.tsv", sep="\t", index=False)
            for w in waterfall:
                log.info(f"step {w['step']} {w['name']:<12} [{w['status']}] -{w['removed_healthy']} HC "
                         f"-{w['removed_scz']} SCZ -{w['removed_unlabelled']} other -> "
                         f"{w['remaining_healthy']} HC / {w['remaining_scz']} SCZ {w['note']}")
            n_kept = int(samples["included"].sum())
            if n_kept < fcfg["min_study_samples"]:
                log.warning(f"only {n_kept} samples left: GutMIND would discard this study (< {fcfg['min_study_samples']})")
            waterfall_all += waterfall
            counts_all += count_comparison(study, samples, waterfall, fcfg)
            status[sid] = "OK"
        except Exception as e:
            log.exception(f"FAILED: {e}")
            status[sid] = f"FAILED: {e}"
    res = settings.path("results")
    res.mkdir(parents=True, exist_ok=True)
    if waterfall_all:
        pd.DataFrame(waterfall_all).to_csv(res / "filter_waterfall.tsv", sep="\t", index=False)
    if counts_all:
        table = pd.DataFrame(counts_all)
        table.to_csv(res / "filter_counts_vs_table_s1.tsv", sep="\t", index=False)
        print("\nFiltered samples vs Table S1 'Filtered' counts:")
        print(table.to_string(index=False))
    return status
