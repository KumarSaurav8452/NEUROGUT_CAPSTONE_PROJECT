# Phase 1 — Config, metadata and labels (FR-1, FR-2, FR-3)

**Run date:** 25 Oct 2026 · **Command:** `python -m scz_data phase1` · **Status:** done for the 5 public studies; Vasileva skipped (awaiting access).

## Results

| StudyID | Runs fetched | Samples | Healthy (exp → got) | SCZ (exp → got) | Excluded at labelling | Kept FASTQ size |
|---|---|---|---|---|---|---|
| Li_2023_SCZ | 76 | 76 | 36 → 36 PASS | 19 → 19 PASS | 21 (4w/8w follow-ups) | 368.8 GB |
| Xu_2020_SCZ | 128 | 128 | 0 → 0 PASS | 40 → 40 PASS | 88 (16S sub-study) | 59.3 GB |
| Zhu_2020A_SCZ | 209 | 209 | 81 → 81 PASS | 90 → 90 PASS | 38 (medication follow-ups) | 1,025.5 GB (ENA) |
| Zhu_2020B_SCZ | 148 | 148 | 45 → 45 PASS | 45 → 45 PASS | 58 (54 FMT mice, 4 donors) | 1,000.9 GB |
| Thirion_2023A_SCZ | 753 | 389 | 174 → **257 FAIL** | 132 → 132 PASS | 0 | 1,035.8 GB |
| Vasileva_2024_SCZ | — | — | SKIPPED: awaiting access | | | — |

Counts are unique samples before FR-4 filtering, compared with Table S1's *raw* counts. The machine-readable table is in `results/label_counts_vs_table_s1.tsv`.

**Total to download for labelled samples: 3,490 GB.**

## Checks performed
- **Checksums and sizes:** every FASTQ has an MD5 and a byte size: 1,729 files across the 5 studies, none missing.
- **Zhu A/B split:** 0 shared samples and 0 shared runs. The 357 CNP0000119 runs split into 209 Illumina + 148 BGISEQ.
- **Zhu A downloads:** all 171 labelled Zhu A samples point at the ENA mirror PRJEB29127. The 38 excluded medication runs stay on CNGB.
- **Supplement joins:** both supplements joined 1:1 with no label-stage warnings. There are no orphan supplement rows and no unmapped groups.
- **Demographics:** age, sex and BMI come from the supplements for Zhu A (171/171) and Zhu B (90/90 age/sex, 88/90 BMI). None of the other studies publish them.
- **Idempotency:** rerunning `phase1` takes about 3 s, is served from the HTTP cache (`data/cache/http`, 858 entries), and produces byte-identical outputs.
- **Unit tests:** `python -m pytest -q` passes 19 tests covering archive inference, label rules + supplement join, Zhu platform split and count validation.

## Known gaps carried into Phase 2
- **Thirion HC 257 vs 174** (and filtered 53 / 47 in Table S1). Per the agreed fallback, the BMI filter is skipped for Thirion (`bmi_filter: false`) and the gap will be reported, not forced. The paper itself used 132 controls (74 + 58), which also doesn't match 174. See discovery §2.4 and §3d.
- **Zhu B HC `CL100089730_L02_558`**: BMI 61.7 as recorded (160 cm / 158 kg). The FR-4 BMI filter will drop it. If 158 kg is a typo for 58 kg it would stay; Table S1's 43 suggests GutMIND dropped it.
- **Li and Xu have no BMI**, so their BMI filter is a no-op (NA is kept), consistent with GutMIND keeping NA.
- **Filters needing QC/profiling output** (≥ 10 M reads, ≤ 30 % unclassified) can only run after Phases 3–4/6.
