# Phase 5: harmonised table (FR-8) and validation report (FR-9)

**Date:** 27–28 Oct 2026

## Commands
```
python -m scz_data filter          # FR-4 with the final depth estimates
python -m scz_data profile-status  # refresh merged profiles, read estimates, profile QC
python -m scz_data phase5          # filter -> harmonize -> report
```
`profile-status` must run between the two filter passes: the depth filter reads `results/qc/read_estimates.tsv`, which `profile-status` rewrites.

## Outputs
| file | content |
|---|---|
| `results/scz_samples.tsv`, `.parquet` | One row per archive sample, all 5 public studies. The first 18 columns are the PRD FR-8 schema, then profile/QC additions. Excluded samples stay in, with one `exclusion_step` + reason. |
| `results/DATA_DICTIONARY.md` | Every column: type and meaning. Read counts are single reads (both mates counted). |
| `results/validation_report.md` | Expected vs obtained (raw, filtered) per study, reasons for gaps, waterfall, every excluded sample, skipped studies, checksums, profiling coverage + QC flags, deviations, PRD §9 acceptance checklist. |
| `results/profiles/metaphlan_merged.tsv` | Species × `sample_id`, % of classified reads; `by_study/` per study; `metaphlan_merged_all_levels.tsv` all ranks. |

Reasons for count gaps and skipped studies live in `config/config.yaml` → `report:`, so the report never invents them.

## Paper supplements checked for per-sample BMI (28 Oct 2026, downloaded with Yashvi's OK)
The publisher pages (ScienceDirect) showed a CAPTCHA, so the files came from Elsevier's CDN (`ars.els-cdn.com/content/image/1-s2.0-<PII>-mmcN.*`), the same route as Thirion.

| file | PII | MD5 | what it holds |
|---|---|---|---|
| `data/supplements/Li2023_SchizophrRes_mmc1.docx` | S0920996423000981 | cfb83bf58849d97f0560af618a9ca809 | Supp. Tables 1–4. Table 1 is demographics by **group only** (e.g. BMI 23.07 ± 3.09 at 0 w). No sample IDs, so no per-sample BMI. |
| `data/supplements/Xu2020_BrainBehavImmun_mmc1.docx` | S0889159119300807 | 26d08c6915a40d3c01ffa0a060dc7c81 | Supplementary methods/figures. |
| `data/supplements/Xu2020_BrainBehavImmun_mmc2.xlsx` | S0889159119300807 | 0fd82fd54541f9e8d6d8e4e5dd2f009e | **ST1: per-sample** name, group, method, raw/remaining reads, sex, age, BMI, diet… for 80 shotgun + 88 16S samples. |

### Xu ST1
- **BMI:** `NA` for all 40 shotgun SCZ samples, so the BMI filter stays a no-op.
- **Sex and age** for all 40 are now in `scz_samples.tsv`: 25 male, 15 female.
- **Exact raw read counts** (`published_reads`) now replace the file-size estimates for the depth filter. Our estimates had been 1–4 % low.
- **The paper renames samples:** CNGB `wmb-(62+k)` = ST1 `SCZk`, handled by `key_transform` in `config/label_maps/Xu_2020_SCZ.yaml`. Evidence:
  - correlation 0.998 between ST1 raw reads and our independent file-size estimates (offsets 61/63: 0.12);
  - `SCZ39` = 7,661,814 raw reads, exactly what we counted streaming `wmb-101` (CNS0063952) whole.
- **Depth result:** two samples are below 10 M host-removed reads.
  - CNS0063952 (SCZ39): 7.3 M; the paper's own QC gives 6.9 M.
  - CNS0063922 (SCZ08): 9.9 M, borderline. Exact raw 13.38 M × the 73.9 % our fastp + bowtie2 kept, whereas the paper's QC kept 10.87 M.
  - So we get 38 vs Table S1's 39 (WARN, within ±2). Not tuned to match.

## Acceptance criteria (PRD §9)
The report evaluates them from the outputs. The last one, the idempotence check, is done here by hand (see below).

## Idempotence check
28 Oct 2026, after the profile run finished (all 573 subsample profiles done, 0 failed):
1. `filter` → `profile-status` → `phase5` produced the final outputs (742 included: 418 HC / 324 SCZ; 950 rows in `scz_samples.tsv`).
2. MD5 of 13 outputs taken (`logs/idem_1.md5`): `scz_samples.tsv`, `DATA_DICTIONARY.md`, `validation_report.md`, `filter_counts_vs_table_s1.tsv`, `qc/read_estimates.tsv`, the three `profiles/` tables, and the five `data/filtered/*.samples.tsv`.
3. The same three stages were run again, and MD5s taken again (`logs/idem_2.md5`).

Result: **all 13 identical**. A rerun of `profile --yes` is also a no-op: every sample is `done` in `data/profile_state/`, so nothing is fetched again. `scz_samples.parquet` is not hashed (its file metadata can differ between writes), but it has the same rows and columns as the TSV (950 × 30).
