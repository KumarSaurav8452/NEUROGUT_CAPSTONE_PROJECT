# Data dictionary: results/scz_samples.tsv

One row per subject (archive sample), all SCZ studies of GutMIND Table S1 that are publicly available.
`results/scz_samples.parquet` holds the same table with typed columns. Species abundances are in
`results/profiles/metaphlan_merged.tsv` (species x sample_id, % of classified reads) and
`results/profiles/by_study/<StudyID>.species.tsv`; all taxonomic levels in
`results/profiles/metaphlan_merged_all_levels.tsv`.

The first 18 columns are the PRD FR-8 schema; the rest are additions.

| column | type | description |
|---|---|---|
| sample_id | str | `<StudyID>__<archive sample accession>`; unique key, also the column name in the MetaPhlAn tables |
| study_id | str | GutMIND Table S1 StudyID |
| accession | str | study accession from Table S1 (config/studies.yaml) |
| archive | str | archive the metadata came from (ENA / CNGB / GSA) |
| run_ids | str | `;`-joined run accessions merged into this sample |
| group | str | Healthy / SCZ (label source per study: config/label_maps/<StudyID>.yaml) |
| country | str | from Table S1 |
| platform | str | sequencing platform (ILLUMINA / BGISEQ / ION_TORRENT) |
| layout | str | PAIRED / SINGLE |
| diagnosis_criteria | str | Table S1 Clinical Assessment (e.g. DSM-IV, ICD-10) |
| age | str | years, if published (archive attributes or paper supplement), else NA |
| sex | str | as published, else NA |
| bmi | float64 | kg/m2, if published, else NA (Thirion: not published per sample) |
| raw_reads | Int64 | full-depth single reads before QC (exact if streamed whole, else archive count or estimate) |
| clean_reads | Int64 | full-depth reads after fastp; exact only for samples streamed whole, else NA |
| host_removed_reads | Int64 | full-depth reads after fastp + bowtie2 GRCh38 host removal (exact or estimated); used for the 10 M depth filter |
| included | bool | TRUE if the sample passes every applied FR-4 filter |
| exclusion_reason | string | why it was removed (one reason per sample) |
| sample_accession | str | archive sample accession |
| sample_name | string | submitter's sample name (e.g. BGI ID for Zhu, used to join paper supplements) |
| source_accession | str | archive project the runs belong to (Thirion: SCZ and control projects differ) |
| exclusion_step | string | FR-4 step that removed it (`<n>:<name>`), see results/validation_report.md |
| reads_source | str | where raw/host_removed_reads come from: stream (exact) / archive read_count / file-size estimate |
| profiled | bool | TRUE if a MetaPhlAn 3 profile exists for this sample |
| profile_source | string | subsample (first N reads, this pipeline) or curatedMetagenomicData (full depth) |
| profile_reads | Int64 | reads in the profiled subsample before QC (NA for curatedMetagenomicData) |
| n_species | Int64 | species with non-zero abundance in the profile |
| unclassified_frac | float64 | MetaPhlAn 3 UNKNOWN fraction (0-1); recorded, not filtered on (docs/phase3b.md) |
| profile_host_fraction | float64 | human fraction of the profiled subsample (bowtie2 vs GRCh38) |
| profile_qc_flags | string | runbook red flags: species<10, host>5%, kept<50%, duplicate profile |

Units: read counts are single reads (both mates of a pair counted), matching the GutMIND 10 M depth filter.
NA means not published / not measured, never zero.
