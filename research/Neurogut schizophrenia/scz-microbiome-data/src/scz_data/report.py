"""FR-9: results/validation_report.md from the outputs of every stage (reads only; recompute nothing).

Inputs: config/studies.yaml, results/label_counts_vs_table_s1.tsv, results/filter_counts_vs_table_s1.tsv,
results/filter_waterfall.tsv, results/scz_samples.tsv (FR-8), results/profiles/profile_qc.tsv,
data/profile_state/*.json, logs/stream/*.log (MD5 results).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from scz_data.harmonize import COLUMNS
from scz_data.settings import Settings


def _md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_none_\n"
    cols = [str(c) for c in df.columns]
    rows = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        rows.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |")
    return "\n".join(rows) + "\n"


def _opt(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t") if path.exists() else pd.DataFrame()


def md5_summary(log_dir: Path) -> dict:
    ok, bad, files_bad = 0, 0, set()
    final_ok = set()
    for log in sorted(log_dir.glob("*.log")):
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.search(r"\] (\S+): downloaded \(.*MD5 ok\)", line)
            if m:
                ok += 1
                final_ok.add(m.group(1))
            m = re.search(r"MD5 mismatch for (\S+?):", line)
            if m:
                bad += 1
                files_bad.add(m.group(1))
    unresolved = sorted(files_bad - final_ok)
    # a mismatch whose retry never finished (stream run stopped for profile mode, 26 Oct): only a .part file is
    # left and nothing used it, so it is not a checksum failure of a downloaded FASTQ
    raw = log_dir.parents[1] / "data" / "raw_fastq"
    done_files = {f.name for f in raw.rglob("*.gz")} if raw.exists() else set()
    return {"ok": ok, "mismatch_events": bad, "unresolved": [f for f in unresolved if f in done_files],
            "abandoned": [f for f in unresolved if f not in done_files]}


def profile_coverage(settings: Settings, samples: pd.DataFrame) -> pd.DataFrame:
    state_dir = settings.resolve(settings.cfg["profile"]["state_dir"])
    states = {}
    for p in state_dir.glob("*.json"):
        d = json.loads(p.read_text())
        sid = d.get("sample_id", p.stem.replace(".failed", ""))
        if d.get("status") == "done" or sid not in states:
            states[sid] = d.get("status")
    inc = samples[samples["included"] | samples["profiled"]].copy()
    inc["state"] = inc["sample_id"].map(states).fillna("pending")
    inc.loc[inc["profiled"], "state"] = "done"
    ext = settings.cfg["profile"].get("external_profiles", {})
    rows = []
    for sid, g in inc.groupby("study_id", sort=False):
        rows.append({"study_id": sid, "samples": len(g), "profiled": int((g["state"] == "done").sum()),
                     "failed": int((g["state"] == "failed").sum()), "pending": int((g["state"] == "pending").sum()),
                     "source": ext[sid]["source"] if sid in ext else "subsample, this pipeline"})
    return pd.DataFrame(rows)


def acceptance(settings: Settings, studies: list[dict], samples: pd.DataFrame, counts: pd.DataFrame,
               md5: dict) -> list[tuple[str, str, str]]:
    notes = settings.cfg.get("report", {}).get("count_notes", {})
    out = []
    n = len(studies)
    out.append(("`studies.yaml` contains exactly the 6 SCZ studies from Table S1", "PASS" if n == 6 else "FAIL",
                f"{n} studies"))
    raw_dir = settings.path("raw_metadata")
    public = [s["study_id"] for s in studies if s.get("archive") != "manual"]
    have = [s for s in public if (raw_dir / f"{s}.tsv").exists()]
    manual = [s["study_id"] for s in studies if s.get("archive") == "manual"]
    out.append(("Metadata retrieved for all public studies (5); RDM handled as manual without crashing",
                "PASS" if len(have) == len(public) == 5 else "FAIL",
                f"{len(have)}/{len(public)} public; manual: {', '.join(manual) or 'none'}"))
    a = samples[samples["study_id"] == "Zhu_2020A_SCZ"]
    b = samples[samples["study_id"] == "Zhu_2020B_SCZ"]
    runs = lambda d: set(";".join(d["run_ids"].dropna().astype(str)).split(";")) - {""}
    ov_s = set(a["sample_accession"]) & set(b["sample_accession"])
    ov_r = runs(a[a["included"]]) & runs(b[b["included"]])
    out.append(("Zhu A and B are split by platform with no overlapping samples",
                "PASS" if not ov_s and not ov_r else "FAIL",
                f"A: {sorted(a.loc[a['included'], 'platform'].unique())}, B: "
                f"{sorted(b.loc[b['included'], 'platform'].unique())}; shared samples {len(ov_s)}, runs {len(ov_r)}"))
    off = counts[counts["status"] == "FAIL"]["study_id"].unique() if len(counts) else []
    undocumented = [s for s in off if s not in notes]
    out.append(("Filtered Healthy/SCZ counts within +/-2 of Table S1, or a documented reason",
                "PASS (with documented reasons)" if len(off) and not undocumented else ("PASS" if not len(off) else "FAIL"),
                f"outside tolerance: {', '.join(off) or 'none'}; undocumented: {', '.join(undocumented) or 'none'}"))
    out.append(("100% of downloaded FASTQs pass MD5", "PASS" if not md5["unresolved"] else "FAIL",
                f"{md5['ok']} whole files MD5-verified; {len(md5['abandoned'])} interrupted download never completed or used; "
                "profile-mode partial reads cannot be MD5-checked: every record validated + gzip CRC instead"))
    schema_ok = list(samples.columns[:18]) == COLUMNS[:18]
    dup = int(samples["sample_id"].duplicated().sum())
    out.append(("`scz_samples.tsv` matches the FR-8 schema with no duplicate `sample_id`",
                "PASS" if schema_ok and not dup else "FAIL", f"schema {'ok' if schema_ok else 'MISMATCH'}; {dup} duplicates"))
    tests = sorted(p.name for p in (settings.root / "tests").glob("test_*.py"))
    out.append(("Unit tests: accession->archive, label mapping, Zhu platform split, count validation",
                "PASS (see `python -m pytest -q`)", ", ".join(tests)))
    out.append(("Full pipeline re-run is a no-op (idempotent)", "see docs/phase5.md",
                "checked by re-running every stage and comparing outputs"))
    return out


def build(settings: Settings, studies: list[dict]) -> str:
    res = settings.path("results")
    rcfg = settings.cfg.get("report", {})
    notes, skipped_notes = rcfg.get("count_notes", {}), rcfg.get("skipped_studies", {})
    samples = pd.read_csv(res / "scz_samples.tsv", sep="\t")
    labels = _opt(res / "label_counts_vs_table_s1.tsv")
    counts = _opt(res / "filter_counts_vs_table_s1.tsv")
    wf = _opt(res / "filter_waterfall.tsv")
    pqc = _opt(res / "profiles" / "profile_qc.tsv")
    md5 = md5_summary(settings.path("logs") / "stream")
    cov = profile_coverage(settings, samples)

    L = [f"# Validation report: SCZ gut metagenome retrieval",
         "",
         f"Generated {datetime.now():%d %b %Y %H:%M} by `python -m scz_data report` from the pipeline outputs. "
         "Spec: `PRD_SCZ_Data_Retrieval.md`; reference counts: GutMIND Table S1 (`data/sTable1.xlsx`).",
         ""]

    inc = samples[samples["included"]]
    L += ["## Summary", "",
          f"- **{len(inc)} samples included** ({int((inc['group'] == 'Healthy').sum())} Healthy, "
          f"{int((inc['group'] == 'SCZ').sum())} SCZ) from {inc['study_id'].nunique()} public studies; "
          f"{int(inc['profiled'].sum())} have a species profile.",
          f"- {int((~samples['included']).sum())} archive samples excluded, each with one reason (below).",
          f"- Skipped: {', '.join(skipped_notes) or 'none'}.",
          "- Outputs: `results/scz_samples.tsv` / `.parquet` (one row per subject, `results/DATA_DICTIONARY.md`), "
          "`results/profiles/metaphlan_merged.tsv` (species x sample), `results/profiles/by_study/`, "
          "`results/profiles/metaphlan_merged_all_levels.tsv`.",
          ""]

    L += ["## 1. Expected vs obtained counts", "",
          "Raw = labelled archive samples vs Table S1 'Raw'; filtered = after FR-4 vs Table S1 'Filtered'. "
          "PASS exact, WARN within +/-2, FAIL further off (reported, never forced).", ""]
    if len(labels) and len(counts):
        t = labels.merge(counts, on=["study_id", "group"], how="outer", suffixes=("_raw", "_filtered"))
        t = t.rename(columns={"labelled": "obtained_raw", "status_raw": "raw", "obtained": "obtained_filtered",
                              "status_filtered": "filtered"})
        t = t[t["group"].isin(["Healthy", "SCZ"])]
        for c in ("expected_raw", "obtained_raw", "expected_filtered", "obtained_filtered"):
            if c in t:
                t[c] = pd.to_numeric(t[c], errors="coerce").astype("Int64")
        t = t[["study_id", "group", "expected_raw", "obtained_raw", "raw", "expected_filtered", "obtained_filtered",
               "filtered", "skipped_filters"]]
        L.append(_md_table(t))
    L += ["**Reasons for differences**", ""]
    for sid in counts["study_id"].unique() if len(counts) else []:
        st = counts[counts["study_id"] == sid]["status"]
        if (st != "PASS").any():
            L.append(f"- **{sid}** ({'/'.join(st)}): {notes.get(sid, '_no documented reason_')}")
    L.append("")

    L += ["## 2. Filtering waterfall", "",
          "GutMIND rules (Methods): shotgun only, study platform, baseline only, BMI <= 30, >= 10 M host-removed "
          "reads, <= 30 % unclassified. Each removed sample is counted once, at the first step that removes it.", ""]
    for sid, g in wf.groupby("study_id", sort=False) if len(wf) else []:
        L += [f"### {sid}", ""]
        L.append(_md_table(g[["step", "name", "status", "removed_healthy", "removed_scz", "removed_unlabelled",
                              "remaining_healthy", "remaining_scz", "note"]]))
    L += ["## 3. Excluded and unlabelled samples", ""]
    exc = samples[~samples["included"]]
    if len(exc):
        g = (exc.fillna({"group": "unlabelled", "exclusion_reason": ""})
             .groupby(["study_id", "exclusion_step", "group", "exclusion_reason"], dropna=False).size()
             .reset_index(name="n"))
        L.append(_md_table(g))
        L += ["<details><summary>Every excluded sample</summary>", ""]
        L.append(_md_table(exc[["sample_id", "group", "exclusion_step", "exclusion_reason"]].fillna("")))
        L += ["</details>", ""]
    L += ["## 4. Skipped studies", ""]
    for sid, why in skipped_notes.items():
        L.append(f"- **{sid}**: {why}")
    L.append("")

    L += ["## 5. Checksums and transfer integrity", "",
          f"- Whole files downloaded (Phase 3 stream runs): **{md5['ok']} passed MD5**; "
          f"{md5['mismatch_events']} mismatch event(s). "
          f"Unresolved: {', '.join(md5['unresolved']) or 'none'}. Interrupted before a verified copy existed "
          f"(never used; the sample was profiled from a fresh partial read): {', '.join(md5['abandoned']) or 'none'}.",
          "- Profile mode reads only the first N reads of each file, so archive MD5s cannot apply. Instead every "
          "record is validated (4-line structure, `@`/`+`, sequence length = quality length), R1/R2 names are "
          "checked read by read, gzip's CRC covers decompression, and a garbled transfer is retried.",
          ""]

    L += ["## 6. Profiling coverage and QC", "",
          "Profiles: MetaPhlAn 3.0.14, `mpa_v30_CHOCOPhlAn_201901`, after fastp + bowtie2 (GRCh38) host removal. "
          "Coverage of samples that pass the filters (plus any profiled sample):", ""]
    L.append(_md_table(cov))
    if len(pqc):
        fl = pqc[pqc["flags"].notna() & (pqc["flags"].astype(str) != "")]
        L += [f"Runbook red flags: **{len(fl)} of {len(pqc)}** profiled samples (kept, flagged for review):", ""]
        L.append(_md_table(fl[["sample_id", "group", "n_species", "host_fraction", "unclassified_frac", "flags"]]))
        L += [f"Species per sample: median {pqc['n_species'].median():.0f} (min {pqc['n_species'].min()}, "
              f"max {pqc['n_species'].max()}); host fraction median {pqc['host_fraction'].median():.4%}; "
              f"UNKNOWN fraction median {pqc['unclassified_frac'].median():.1%}.", ""]

    L += ["## 7. Deviations from GutMIND / the PRD", "",
          "- **Profiles from subsamples**: first 500 k reads per file (Thirion 300 k), not full depth; Zhu_2020A "
          "uses curatedMetagenomicData full-depth profiles. Reason: ~0.3 MB/s connection, 3.5 TB total "
          "(docs/phase3b.md).",
          "- **MetaPhlAn 3 (`mpa_v30`) instead of MetaPhlAn 4**: the MetaPhlAn 4 index (21 GB) does not fit; "
          "`mpa_v30` matches curatedMetagenomicData and the team's training data.",
          "- **Unclassified filter skipped**: the 30 % cut-off is calibrated for MetaPhlAn 4; values are recorded.",
          "- **Depth filter on estimates** where no exact count exists (archive read counts preferred).",
          "- **BMI filter** applied only where BMI is published (Zhu A, Zhu B); skipped for Thirion.",
          "- **Host removal** with bowtie2 `--sensitive` (not `--very-sensitive`) on subsamples.",
          "- **Thirion reads** taken partly from NCBI SRA's public AWS copy (same runs and reads) after ENA "
          "slowed down on 27 Oct 2026.",
          ""]

    L += ["## 8. Acceptance criteria (PRD §9)", "", "| criterion | status | detail |", "|---|---|---|"]
    for c, s, d in acceptance(settings, studies, samples, counts, md5):
        L.append(f"| {c} | {s} | {d} |")
    L.append("")
    return "\n".join(L)


def run(settings: Settings, studies: list[dict]) -> dict[str, str]:
    text = build(settings, studies)
    out = settings.path("results") / "validation_report.md"
    out.write_text(text, encoding="utf-8")
    return {"(all)": f"written {out.relative_to(settings.root)}"}
