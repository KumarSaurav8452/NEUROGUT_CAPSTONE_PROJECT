# Validation report: SCZ gut metagenome retrieval

Generated 28 Oct 2026 05:01 by `python -m scz_data report` from the pipeline outputs. Spec: `PRD_SCZ_Data_Retrieval.md`; reference counts: GutMIND Table S1 (`data/sTable1.xlsx`).

## Summary

- **742 samples included** (418 Healthy, 324 SCZ) from 5 public studies; 742 have a species profile.
- 208 archive samples excluded, each with one reason (below).
- Skipped: Vasileva_2024_SCZ.
- Outputs: `results/scz_samples.tsv` / `.parquet` (one row per subject, `results/DATA_DICTIONARY.md`), `results/profiles/metaphlan_merged.tsv` (species x sample), `results/profiles/by_study/`, `results/profiles/metaphlan_merged_all_levels.tsv`.

## 1. Expected vs obtained counts

Raw = labelled archive samples vs Table S1 'Raw'; filtered = after FR-4 vs Table S1 'Filtered'. PASS exact, WARN within +/-2, FAIL further off (reported, never forced).

| study_id | group | expected_raw | obtained_raw | raw | expected_filtered | obtained_filtered | filtered | skipped_filters |
|---|---|---|---|---|---|---|---|---|
| Li_2023_SCZ | Healthy | 36 | 36 | PASS | 30 | 36 | FAIL | unclassified |
| Li_2023_SCZ | SCZ | 19 | 19 | PASS | 17 | 19 | WARN | unclassified |
| Thirion_2023A_SCZ | Healthy | 174 | 257 | FAIL | 53 | 257 | FAIL | bmi;unclassified |
| Thirion_2023A_SCZ | SCZ | 132 | 132 | PASS | 47 | 132 | FAIL | bmi;unclassified |
| Xu_2020_SCZ | Healthy | 0 | 0 | PASS | 0 | 0 | PASS | unclassified |
| Xu_2020_SCZ | SCZ | 40 | 40 | PASS | 39 | 38 | WARN | unclassified |
| Zhu_2020A_SCZ | Healthy | 81 | 81 | PASS | 79 | 81 | WARN | unclassified |
| Zhu_2020A_SCZ | SCZ | 90 | 90 | PASS | 88 | 90 | WARN | unclassified |
| Zhu_2020B_SCZ | Healthy | 45 | 45 | PASS | 43 | 44 | WARN | unclassified |
| Zhu_2020B_SCZ | SCZ | 45 | 45 | PASS | 44 | 45 | WARN | unclassified |

**Reasons for differences**

- **Li_2023_SCZ** (FAIL/WARN): No per-sample BMI is published (GSA attributes and the paper's supplement mmc1.docx give group means only: SZ 23.1 +/- 3.1), so the BMI filter removes no one. The unclassified filter is skipped (MetaPhlAn 3 UNKNOWN is not comparable to the MetaPhlAn 4 cut-off). GutMIND's extra removals most likely came from these two filters.
- **Xu_2020_SCZ** (PASS/WARN): Depth uses the exact raw read counts of the paper's Supplementary Table 1 x the fraction our fastp + bowtie2 kept. Two samples fall below 10 M: CNS0063952 (SCZ39, 7.3 M; the paper's own QC gives 6.9 M) and CNS0063922 (SCZ08, 9.9 M; borderline, the paper's QC kept 10.9 M, so GutMIND probably kept it). BMI is NA for every shotgun sample in the supplement, so the BMI filter removes no one.
- **Zhu_2020A_SCZ** (WARN/WARN): Profiles come from curatedMetagenomicData, which has no unclassified estimate; GutMIND's 2 + 2 removals are most likely its unclassified filter. BMI is published and none is > 30.
- **Zhu_2020B_SCZ** (WARN/WARN): The unclassified filter is skipped; GutMIND removed 1 HC + 1 SCZ, most likely there.
- **Thirion_2023A_SCZ** (FAIL/FAIL): The public control projects (PRJEB41786, PRJEB41787) hold 257 controls; the paper used 132 and Table S1 lists 174 raw, with no published list of which. Per-sample BMI is not published (SCZ mean BMI 35), so GutMIND's BMI > 30 filter, which explains most of 132 -> 47 SCZ, cannot be applied. All 389 public samples are kept and the gap is reported, not forced (agreed fallback, 25 Oct 2026).

## 2. Filtering waterfall

GutMIND rules (Methods): shotgun only, study platform, baseline only, BMI <= 30, >= 10 M host-removed reads, <= 30 % unclassified. Each removed sample is counted once, at the first step that removes it.

### Li_2023_SCZ

| step | name | status | removed_healthy | removed_scz | removed_unlabelled | remaining_healthy | remaining_scz | note |
|---|---|---|---|---|---|---|---|---|
| 1 | shotgun | applied | 0 | 0 | 0 | 36 | 19 |  |
| 2 | platform | applied | 0 | 0 | 0 | 36 | 19 | single-platform study |
| 3 | baseline | applied | 0 | 0 | 21 | 36 | 19 |  |
| 4 | bmi | no-op | 0 | 0 | 0 | 36 | 19 | no BMI available for this study (NA kept) |
| 5 | depth | applied | 0 | 0 | 0 | 36 | 19 |  |
| 6 | unclassified | skipped | 0 | 0 | 0 | 36 | 19 | 30% cut-off is calibrated for MetaPhlAn 4; MetaPhlAn 3 UNKNOWN fraction is not comparable |

### Xu_2020_SCZ

| step | name | status | removed_healthy | removed_scz | removed_unlabelled | remaining_healthy | remaining_scz | note |
|---|---|---|---|---|---|---|---|---|
| 1 | shotgun | applied | 0 | 0 | 88 | 0 | 40 | 88 non-shotgun samples flagged |
| 2 | platform | applied | 0 | 0 | 0 | 0 | 40 | single-platform study |
| 3 | baseline | applied | 0 | 0 | 0 | 0 | 40 |  |
| 4 | bmi | no-op | 0 | 0 | 0 | 0 | 40 | no BMI available for this study (NA kept) |
| 5 | depth | applied | 0 | 2 | 0 | 0 | 38 |  |
| 6 | unclassified | skipped | 0 | 0 | 0 | 0 | 38 | 30% cut-off is calibrated for MetaPhlAn 4; MetaPhlAn 3 UNKNOWN fraction is not comparable |

### Zhu_2020A_SCZ

| step | name | status | removed_healthy | removed_scz | removed_unlabelled | remaining_healthy | remaining_scz | note |
|---|---|---|---|---|---|---|---|---|
| 1 | shotgun | applied | 0 | 0 | 0 | 81 | 90 |  |
| 2 | platform | applied | 0 | 0 | 0 | 81 | 90 | split on ILLUMINA (applied at fetch; re-checked) |
| 3 | baseline | applied | 0 | 0 | 38 | 81 | 90 |  |
| 4 | bmi | applied | 0 | 0 | 0 | 81 | 90 |  |
| 5 | depth | applied | 0 | 0 | 0 | 81 | 90 |  |
| 6 | unclassified | skipped | 0 | 0 | 0 | 81 | 90 | 30% cut-off is calibrated for MetaPhlAn 4; MetaPhlAn 3 UNKNOWN fraction is not comparable |

### Zhu_2020B_SCZ

| step | name | status | removed_healthy | removed_scz | removed_unlabelled | remaining_healthy | remaining_scz | note |
|---|---|---|---|---|---|---|---|---|
| 1 | shotgun | applied | 0 | 0 | 0 | 45 | 45 |  |
| 2 | platform | applied | 0 | 0 | 0 | 45 | 45 | split on BGISEQ (applied at fetch; re-checked) |
| 3 | baseline | applied | 0 | 0 | 58 | 45 | 45 |  |
| 4 | bmi | applied | 1 | 0 | 0 | 44 | 45 | 2 kept with BMI NA |
| 5 | depth | applied | 0 | 0 | 0 | 44 | 45 |  |
| 6 | unclassified | skipped | 0 | 0 | 0 | 44 | 45 | 30% cut-off is calibrated for MetaPhlAn 4; MetaPhlAn 3 UNKNOWN fraction is not comparable |

### Thirion_2023A_SCZ

| step | name | status | removed_healthy | removed_scz | removed_unlabelled | remaining_healthy | remaining_scz | note |
|---|---|---|---|---|---|---|---|---|
| 1 | shotgun | applied | 0 | 0 | 0 | 257 | 132 |  |
| 2 | platform | applied | 0 | 0 | 0 | 257 | 132 | single-platform study |
| 3 | baseline | applied | 0 | 0 | 0 | 257 | 132 | 237 kept samples have >1 run, merged |
| 4 | bmi | skipped | 0 | 0 | 0 | 257 | 132 | per-sample BMI not published (study_overrides.bmi_filter: false) |
| 5 | depth | applied | 0 | 0 | 0 | 257 | 132 |  |
| 6 | unclassified | skipped | 0 | 0 | 0 | 257 | 132 | 30% cut-off is calibrated for MetaPhlAn 4; MetaPhlAn 3 UNKNOWN fraction is not comparable |

## 3. Excluded and unlabelled samples

| study_id | exclusion_step | group | exclusion_reason | n |
|---|---|---|---|---|
| Li_2023_SCZ | 3:baseline | Exclude | non-baseline timepoint (treatment follow-up 4w/8w) | 21 |
| Xu_2020_SCZ | 1:shotgun | Exclude | not shotgun: AMPLICON | 88 |
| Xu_2020_SCZ | 5:depth | SCZ | clean_reads 7367008.0 < 10000000 | 1 |
| Xu_2020_SCZ | 5:depth | SCZ | clean_reads 9892589.0 < 10000000 | 1 |
| Zhu_2020A_SCZ | 3:baseline | Exclude | post-treatment follow-up sample | 38 |
| Zhu_2020B_SCZ | 3:baseline | Exclude | FMT donor (not part of the validation cohort) | 4 |
| Zhu_2020B_SCZ | 3:baseline | Exclude | mouse FMT recipient (non-human) | 54 |
| Zhu_2020B_SCZ | 4:bmi | Healthy | BMI 61.7 > 30 | 1 |

<details><summary>Every excluded sample</summary>

| sample_id | group | exclusion_step | exclusion_reason |
|---|---|---|---|
| Li_2023_SCZ__SAMC445028 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445029 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445030 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445031 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445032 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445033 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445034 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445035 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445036 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445037 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445038 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445039 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445040 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445041 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445042 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445043 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445044 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445045 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445046 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445047 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Li_2023_SCZ__SAMC445048 | Exclude | 3:baseline | non-baseline timepoint (treatment follow-up 4w/8w) |
| Xu_2020_SCZ__CNS0063922 | SCZ | 5:depth | clean_reads 9892589.0 < 10000000 |
| Xu_2020_SCZ__CNS0063952 | SCZ | 5:depth | clean_reads 7367008.0 < 10000000 |
| Xu_2020_SCZ__CNS0063954 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063955 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063956 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063957 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063958 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063959 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063960 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063961 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063962 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063963 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063964 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063965 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063966 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063967 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063968 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063969 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063970 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063971 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063972 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063973 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063974 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063975 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063976 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063977 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063978 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063979 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063980 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063981 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063982 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063983 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063984 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063985 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063986 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063987 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063988 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063989 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063990 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063991 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063992 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063993 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063994 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063995 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063996 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063997 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063998 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0063999 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064000 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064001 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064002 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064003 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064004 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064005 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064006 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064007 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064008 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064009 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064010 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064011 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064012 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064013 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064014 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064015 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064016 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064017 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064018 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064019 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064020 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064021 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064022 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064023 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064024 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064025 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064026 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064027 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064028 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064029 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064030 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064031 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064032 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064033 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064034 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064035 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064036 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064037 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064038 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064039 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064040 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Xu_2020_SCZ__CNS0064041 | Exclude | 1:shotgun | not shotgun: AMPLICON |
| Zhu_2020A_SCZ__CNS0064042 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064043 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064044 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064045 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064046 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064047 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064048 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064049 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064050 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064051 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064052 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064053 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064054 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064055 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064056 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064057 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064058 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064059 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064060 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064061 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064062 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064063 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064064 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064065 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064066 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064067 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064068 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064069 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064070 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064071 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064072 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064073 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064074 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064075 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064076 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064077 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064078 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020A_SCZ__CNS0064079 | Exclude | 3:baseline | post-treatment follow-up sample |
| Zhu_2020B_SCZ__CNS0064080 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064081 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064082 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064083 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064084 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064085 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064086 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064087 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064088 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064089 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064090 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064091 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064092 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064093 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064094 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064095 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064096 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064097 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064098 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064099 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064100 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064101 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064102 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064103 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064104 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064105 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064106 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064107 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064108 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064109 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064110 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064111 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064112 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064113 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064114 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064115 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064116 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064117 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064118 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064119 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064120 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064121 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064122 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064123 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064124 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064125 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064126 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064127 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064128 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064129 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064130 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064131 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064132 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064133 | Exclude | 3:baseline | mouse FMT recipient (non-human) |
| Zhu_2020B_SCZ__CNS0064134 | Exclude | 3:baseline | FMT donor (not part of the validation cohort) |
| Zhu_2020B_SCZ__CNS0064135 | Exclude | 3:baseline | FMT donor (not part of the validation cohort) |
| Zhu_2020B_SCZ__CNS0064136 | Exclude | 3:baseline | FMT donor (not part of the validation cohort) |
| Zhu_2020B_SCZ__CNS0064137 | Exclude | 3:baseline | FMT donor (not part of the validation cohort) |
| Zhu_2020B_SCZ__CNS0092518 | Healthy | 4:bmi | BMI 61.7 > 30 |

</details>

## 4. Skipped studies

- **Vasileva_2024_SCZ**: Data are in the University of Queensland Research Data Manager (RDM), not a public archive; an access request is needed. The pipeline reads data/manual/Vasileva_2024_SCZ/ when the files arrive.

## 5. Checksums and transfer integrity

- Whole files downloaded (Phase 3 stream runs): **4 passed MD5**; 1 mismatch event(s). Unresolved: none. Interrupted before a verified copy existed (never used; the sample was profiled from a fresh partial read): ERR8212332.fastq.gz.
- Profile mode reads only the first N reads of each file, so archive MD5s cannot apply. Instead every record is validated (4-line structure, `@`/`+`, sequence length = quality length), R1/R2 names are checked read by read, gzip's CRC covers decompression, and a garbled transfer is retried.

## 6. Profiling coverage and QC

Profiles: MetaPhlAn 3.0.14, `mpa_v30_CHOCOPhlAn_201901`, after fastp + bowtie2 (GRCh38) host removal. Coverage of samples that pass the filters (plus any profiled sample):

| study_id | samples | profiled | failed | pending | source |
|---|---|---|---|---|---|
| Li_2023_SCZ | 55 | 55 | 0 | 0 | subsample, this pipeline |
| Xu_2020_SCZ | 40 | 40 | 0 | 0 | subsample, this pipeline |
| Zhu_2020A_SCZ | 171 | 171 | 0 | 0 | curatedMetagenomicData 2021-03-31 ZhuF_2020 (MetaPhlAn 3, mpa_v30, full depth) |
| Zhu_2020B_SCZ | 89 | 89 | 0 | 0 | subsample, this pipeline |
| Thirion_2023A_SCZ | 389 | 389 | 0 | 0 | subsample, this pipeline |

Runbook red flags: **12 of 573** profiled samples (kept, flagged for review):

| sample_id | group | n_species | host_fraction | unclassified_frac | flags |
|---|---|---|---|---|---|
| Li_2023_SCZ__SAMC444989 | Healthy | 8 | 0.000324 | 0.587201 | species<10 |
| Li_2023_SCZ__SAMC444995 | Healthy | 6 | 0.000101 | 0.245541 | species<10 |
| Li_2023_SCZ__SAMC445006 | Healthy | 6 | 2.2e-05 | 0.613098 | species<10 |
| Li_2023_SCZ__SAMC445023 | SCZ | 4 | 8.2e-05 | 0.786299 | species<10 |
| Thirion_2023A_SCZ__SAMEA121025470 | Healthy | 8 | 3.7e-05 | 0.791904 | species<10 |
| Thirion_2023A_SCZ__SAMEA121025514 | Healthy | 9 | 1e-05 | 0.328525 | species<10 |
| Thirion_2023A_SCZ__SAMEA121025519 | Healthy | 8 | 1.7e-05 | 0.714959 | species<10 |
| Thirion_2023A_SCZ__SAMEA12687839 | SCZ | 8 | 1.3e-05 | 0.483539 | species<10 |
| Thirion_2023A_SCZ__SAMEA12687929 | SCZ | 9 | 0.0 | 0.26526 | species<10 |
| Thirion_2023A_SCZ__SAMEA12738214 | Healthy | 9 | 2.7e-05 | 0.381588 | species<10 |
| Zhu_2020B_SCZ__CNS0092499 | Healthy | 5 | 0.0009 | 0.32327 | species<10 |
| Zhu_2020B_SCZ__CNS0092550 | SCZ | 23 | 0.000345 | 0.328731 | kept<50% |

Species per sample: median 23 (min 4, max 46); host fraction median 0.0017%; UNKNOWN fraction median 44.3%.

## 7. Deviations from GutMIND / the PRD

- **Profiles from subsamples**: first 500 k reads per file (Thirion 300 k), not full depth; Zhu_2020A uses curatedMetagenomicData full-depth profiles. Reason: ~0.3 MB/s connection, 3.5 TB total (docs/phase3b.md).
- **MetaPhlAn 3 (`mpa_v30`) instead of MetaPhlAn 4**: the MetaPhlAn 4 index (21 GB) does not fit; `mpa_v30` matches curatedMetagenomicData and the team's training data.
- **Unclassified filter skipped**: the 30 % cut-off is calibrated for MetaPhlAn 4; values are recorded.
- **Depth filter on estimates** where no exact count exists (archive read counts preferred).
- **BMI filter** applied only where BMI is published (Zhu A, Zhu B); skipped for Thirion.
- **Host removal** with bowtie2 `--sensitive` (not `--very-sensitive`) on subsamples.
- **Thirion reads** taken partly from NCBI SRA's public AWS copy (same runs and reads) after ENA slowed down on 27 Oct 2026.

## 8. Acceptance criteria (PRD §9)

| criterion | status | detail |
|---|---|---|
| `studies.yaml` contains exactly the 6 SCZ studies from Table S1 | PASS | 6 studies |
| Metadata retrieved for all public studies (5); RDM handled as manual without crashing | PASS | 5/5 public; manual: Vasileva_2024_SCZ |
| Zhu A and B are split by platform with no overlapping samples | PASS | A: ['ILLUMINA'], B: ['BGISEQ']; shared samples 0, runs 0 |
| Filtered Healthy/SCZ counts within +/-2 of Table S1, or a documented reason | PASS (with documented reasons) | outside tolerance: Li_2023_SCZ, Thirion_2023A_SCZ; undocumented: none |
| 100% of downloaded FASTQs pass MD5 | PASS | 4 whole files MD5-verified; 1 interrupted download never completed or used; profile-mode partial reads cannot be MD5-checked: every record validated + gzip CRC instead |
| `scz_samples.tsv` matches the FR-8 schema with no duplicate `sample_id` | PASS | schema ok; 0 duplicates |
| Unit tests: accession->archive, label mapping, Zhu platform split, count validation | PASS (see `python -m pytest -q`) | test_phase1.py, test_phase2.py, test_phase3.py, test_phase5.py, test_profile.py |
| Full pipeline re-run is a no-op (idempotent) | see docs/phase5.md | checked by re-running every stage and comparing outputs |
