# Phase 2 — Filtering and download dry-run (FR-4, FR-5 `--dry-run`)

**Run date:** 25 Oct 2026 · **Commands:** `python -m scz_data phase2 --dry-run`, `python -m scz_data download --dry-run --subset N` · **No FASTQs downloaded.**

## FR-4 filter steps

Each removed sample is attributed to exactly one step. The per-step waterfall is in `results/filter_waterfall.tsv`, the per-sample table in `data/filtered/<StudyID>.samples.tsv`, and the logs in `logs/filter/`.

| # | Step | Rule | Status now |
|---|---|---|---|
| 1 | shotgun | keep `library_strategy` ∈ {WGS} | applied |
| 2 | platform | keep runs on `platform_split` (Zhu A/B) | applied (re-check of the fetch-time split) |
| 3 | baseline | drop label-stage exclusions; merge runs per sample | applied |
| 4 | bmi | BMI > 30 dropped, NA kept (GutMIND) | applied for Zhu A/B; no-op for Li/Xu (no BMI); **skipped** for Thirion (agreed fallback) |
| 5 | depth | < 10 M reads after QC + host removal (GutMIND) | **pending**: needs `results/qc/read_counts.tsv` (Phase 4) |
| 6 | unclassified | > 30 % unclassified, MetaPhlAn 4 (GutMIND) | **pending**: needs `results/profiles/metaphlan_unclassified.tsv` (Phase 6) |

### Waterfall (samples)

| Study | Start | 1 shotgun | 3 baseline | 4 bmi | Now (HC / SCZ) | Table S1 filtered | Status |
|---|---|---|---|---|---|---|---|
| Li_2023 | 76 | — | −21 (4w/8w) | no-op | 36 / 19 | 30 / 17 | PENDING (+6 / +2) |
| Xu_2020 | 128 | −88 (16S) | — | no-op | 0 / 40 | 0 / 39 | PASS / PENDING (+1) |
| Zhu_2020A | 209 | — | −38 (medication) | −0 | 81 / 90 | 79 / 88 | PENDING (+2 / +2) |
| Zhu_2020B | 148 | — | −58 (mice, donors) | −1 HC (BMI 61.7) | 44 / 45 | 43 / 44 | PENDING (+1 / +1) |
| Thirion_2023A | 389 | — | — | skipped | 257 / 132 | 53 / 47 | PENDING (+204 / +85) |

Step 2 removes nothing in any study, because the Zhu split already happens at fetch time. For Thirion, 237 samples had more than one run, and these were merged.

**`status`** is `PENDING` when the count is above target and steps 5–6 are still open. Those steps can only remove samples, so a surplus isn't a verdict yet. A deficit would already be `FAIL`. `status_if_final` in `results/filter_counts_vs_table_s1.tsv` gives the PASS/WARN/FAIL the current numbers would get if no more samples were removed.

**What steps 5–6 must explain:**
- **Zhu A/B and Xu:** 1–2 samples per group. That's plausible for the depth/unclassified filters.
- **Li:** 6 HC and 2 SCZ. These are deep samples (≥ 4.3 GB each), so the unclassified filter is the likelier cause.
- **Thirion:** the large surplus is expected under the fallback (no BMI filter, all public controls). Every Thirion sample has ≥ 15.8 M archive reads, so depth won't close the gap. It will be reported, not forced.

## FR-5 dry-run

| Scope | Samples | Files | Size |
|---|---|---|---|
| **Full** (all included samples) | 744 | 1,463 | **3,482.4 GB** |
| `--subset 5` | 45 | 93 | 184.2 GB |
| `--subset 2` | 18 | 38 | 68.3 GB |
| `--subset 1` | 9 | 20 | 32.5 GB |

Full run per study: Li 368.8, Xu 59.3, Zhu A 1,025.5 (ENA), Zhu B 993.0, Thirion 1,035.8 GB. The manifests are `results/download_manifest.tsv` and `results/download_manifest.subset<N>.tsv`. Each has one row per file with URL, MD5, bytes, destination `data/raw_fastq/<StudyID>/<run>/<file>`, and whether a size-matching copy is already present.

`--subset N` picks the N **smallest** samples per group per study (`download.subset_strategy`), so test runs stay as light as possible.

Per-sample size (GB, min / median / max): Li 4.3 / 6.1 / 13.3 · Thirion 1.6 / 2.6 / 13.5 · Xu 0.7 / 1.5 / 2.3 · Zhu A 3.5 / 6.0 / 8.4 · Zhu B 5.5 / 10.7 / 23.8.

`download` without `--dry-run` is refused until Phase 3.

## ⚠️ Disk space on this machine
**Free space at `data/`: 28.2 GB.** That is less than even `--subset 1` (32.5 GB), and far below the full 3.48 TB.

PRD §6.4 needs updating: the full run needs **~3.5 TB of transfer**, not ~1 TB. Options for Phase 3:
1. **Stream mode** (`keep_raw: false`, already anticipated in PRD §10): download one sample, run fastp + bowtie2, keep only the small host-removed/QC output (or just the MetaPhlAn profile), then delete the raw FASTQ. Peak disk ≈ the largest sample in flight × `parallel`, so about 24 GB for Zhu B at parallel 1. That fits here at `parallel: 1`, but only just.
2. Run Phase 3+ on a lab or cloud machine with ≥ 1 TB free (and ≥ 16 GB RAM for bowtie2/MetaPhlAn).
3. Point `paths.raw_fastq` at an external drive.
