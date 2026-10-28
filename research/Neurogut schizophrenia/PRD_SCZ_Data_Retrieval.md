# PRD — Schizophrenia Gut Microbiome Data Retrieval & Harmonization

**Owner:** Yashvi B. Naik (CSE, Atria Institute of Technology — Major Project)
**Executor:** Claude Code
**Source table:** `sTable1.xlsx` → sheet `Table S1` (Study Information Overview)
**Version:** 1.0 · 25 Oct 2026

---

## 1. Goal

Build a reproducible pipeline that pulls every raw sequencing run and its sample metadata for the **six schizophrenia (SCZ) studies** in Table S1, filters them to match the published cohort sizes, labels each sample as `Healthy` or `SCZ`, and produces one harmonized, analysis-ready dataset.

Success = one command (`make all` or `python -m scz_data run`) goes from the accession list to a validated sample table plus QC'd reads, with every count difference against Table S1 explained in a report.

## 2. Scope

### In scope
- Retrieval of run-level metadata and raw reads (FASTQ) for the 6 SCZ studies below.
- Metadata harmonization into one schema.
- Case/control labelling and filtering to Table S1 "Filtered" counts.
- Read QC + host-read removal, and (optional phase) taxonomic profiling.
- Validation report against Table S1.

### Out of scope (for this PRD)
- The other 31 non-SCZ studies in Table S1 (the code should be reusable for them, but they are not retrieved).
- Statistical analysis / ML modelling (separate PRD).

## 3. Target studies (filtered from Table S1, `Abbreviation == "SCZ"`)

| StudyID | Accession | Archive | Country | Platform | Healthy (raw → filtered) | SCZ (raw → filtered) | Total filtered | Diagnosis |
|---|---|---|---|---|---|---|---|---|
| Li_2023_SCZ | CRA004772 | NGDC GSA (China) | China | Illumina | 36 → 30 | 19 → 17 | 47 | DSM-IV |
| Xu_2020_SCZ | CNP0000401 | CNGBdb / CNSA | China | Illumina | 0 → 0 | 40 → 39 | 39 | DSM-V |
| Zhu_2020A_SCZ | CNP0000119 | CNGBdb / CNSA | China | Illumina | 81 → 79 | 90 → 88 | 167 | DSM-IV |
| Zhu_2020B_SCZ | CNP0000119 | CNGBdb / CNSA | China | BGISEQ | 45 → 43 | 45 → 44 | 87 | DSM-IV |
| Thirion_2023A_SCZ | PRJEB41217 | ENA (EMBL-EBI) | Denmark | Ion Torrent | 174 → 53 | 132 → 47 | 100 | Not specified |
| Vasileva_2024_SCZ | RDM | UQ Research Data Manager (not a public archive) | Australia | Illumina | 25 → 25 | 72 → 71 | 96 | Not specified |

**Expected totals after filtering:** 230 Healthy + 306 SCZ = **536 samples** (raw: 361 + 398 = 759).

### Special cases the code must handle
1. **Zhu_2020A and Zhu_2020B share one accession (CNP0000119).** Split runs into A/B by the run-level `instrument_model` / platform field (Illumina → A, BGISEQ/DNBSEQ → B). Never double-count a sample.
2. **Xu_2020_SCZ has no healthy controls.** Keep it as a disease-only cohort; flag it so downstream case/control analyses can exclude or handle it.
3. **Thirion_2023A has heavy filtering (306 → 100).** The public project likely contains extra samples (e.g. other timepoints, relatives, or a different sub-study). Filtering logic must be derived from metadata and the source paper, not guessed.
4. **Vasileva_2024 ("RDM") is not a public accession.** Treat as **manual / access-request**: the pipeline must accept a local folder of FASTQs + a metadata CSV that Yashvi supplies after obtaining access, and skip cleanly with a clear message if absent.
5. **Ion Torrent (Thirion) and BGISEQ (Zhu B) are single-end / different error profiles.** QC parameters must be platform-aware (see §6.3).

## 4. Users & use case

- **Primary user:** Yashvi, running the pipeline locally or on a lab/cloud machine.
- **Use case:** Get clean, labelled SCZ vs healthy gut microbiome samples to feed into the major project's analysis/model.

## 5. Functional requirements

### FR-1 — Study config
- Parse `sTable1.xlsx` (header is on row 3 of the sheet; row 1–2 are title rows).
- Filter `Abbreviation == "SCZ"` and write `config/studies.yaml` with: StudyID, accession, archive, platform, expected raw and filtered counts.
- Archive is inferred from the accession prefix:
  - `PRJEB*/PRJNA*/PRJDB*` → ENA (INSDC)
  - `CRA*` → NGDC GSA
  - `CNP*` → CNGBdb / CNSA
  - anything else (`RDM`) → `manual`

### FR-2 — Metadata retrieval (per archive)
For each study, fetch **run-level** metadata to `data/raw_metadata/<StudyID>.tsv` with at minimum: run accession, sample accession, sample title/alias, library strategy, library layout (SE/PE), instrument model, read count, base count, FASTQ URLs + MD5s, and every sample attribute available (disease/status, age, sex, BMI, timepoint, medication, etc.).

| Archive | Method (Claude Code must verify the endpoint works before bulk use) |
|---|---|
| ENA | ENA Portal API `filereport` (`result=read_run`, fields incl. `fastq_ftp,fastq_md5,instrument_model,library_layout,library_strategy,sample_accession,sample_title,read_count`) + sample attributes via `result=sample` or the BioSamples API. |
| NGDC GSA | GSA project/BioProject page and run metadata export for CRA004772; FASTQs from the GSA download server (FTP/HTTP). Check whether data is open access. |
| CNGBdb | CNSA project page for CNP0000119 / CNP0000401; sample + run metadata export; FASTQs from the CNGB FTP. Check for any mirror in ENA/SRA (search ENA by the CNP/paper title) — prefer the mirror if available because it has a cleaner API. |
| manual | Read `data/manual/Vasileva_2024_SCZ/metadata.csv` + FASTQs if present; otherwise log `SKIPPED: awaiting access`. |

- Every API call: retries with exponential backoff, polite rate limiting, responses cached to disk so reruns don't refetch.

### FR-3 — Case/control labelling
- Map each sample's raw status field to `group ∈ {Healthy, SCZ, Exclude}`.
- Mapping rules live in `config/label_maps/<StudyID>.yaml` (keyword maps like `control|healthy|HC → Healthy`, `schizophrenia|SCZ|patient|case → SCZ`), never hardcoded.
- Unmappable samples → `Exclude` with a reason, listed in the report.
- Where labels are only in the source paper's supplement (not in archive metadata), Claude Code must stop and tell Yashvi which file is needed rather than inventing labels.

### FR-4 — Filtering to Table S1 counts
Apply, in order, and log how many samples each step removes:
1. Keep only shotgun metagenomic runs (`library_strategy == WGS` / metagenomic). If a study turns out to be 16S amplicon, flag it — don't silently mix.
2. Platform split (Zhu A/B).
3. Drop non-baseline timepoints, technical replicates, and non-gut sample types (keep one run-set per subject; merge multiple runs of the same sample).
4. Drop samples failing QC depth threshold (default: < 1M reads after host removal; configurable).
5. Compare to `HealthCount_Filtered` / `DiseaseCount_Filtered`.

The filtered counts in Table S1 come from the source authors' criteria, which aren't in the table. **Target is an exact match; tolerance is ±2 per group.** Anything beyond that is reported, not forced (no arbitrary dropping to hit a number).

### FR-5 — Raw data download
- Download FASTQs to `data/raw_fastq/<StudyID>/<run>/`.
- Verify MD5 for every file; re-download on mismatch (max 3 tries).
- Resumable: skip files already present with a valid checksum.
- Parallel downloads (configurable, default 4); prefer `aria2c`/`wget -c`; Aspera optional for ENA.
- A `--dry-run` flag that lists files and total size without downloading. **Print total size and ask before downloading** — this can be hundreds of GB.
- A `--subset N` flag to grab N samples per group for quick testing.

### FR-6 — Read QC & host removal
- `fastp` for adapter/quality trimming (platform-aware settings, §6.3).
- Host (human) read removal with `bowtie2` against GRCh38 (or `KneadData`).
- Record per-sample read counts at each stage in `results/qc/read_counts.tsv`.

### FR-7 — (Optional phase 2) Taxonomic & functional profiling
- `MetaPhlAn 4` → species-level relative abundance per sample → merged `results/profiles/metaphlan_merged.tsv`.
- `HUMAnN 3` (optional, heavy) for pathways.
- Gated behind a flag; not required for phase 1 completion.

### FR-8 — Harmonized output
`results/scz_samples.tsv`, one row per subject:

| column | description |
|---|---|
| sample_id | `<StudyID>__<archive sample accession>` |
| study_id, accession, archive | from config |
| run_ids | `;`-joined runs merged for this sample |
| group | Healthy / SCZ |
| country, platform, layout | |
| diagnosis_criteria | from Table S1 Clinical Assessment |
| age, sex, bmi | if available, else NA |
| raw_reads, clean_reads, host_removed_reads | from QC |
| included | TRUE/FALSE |
| exclusion_reason | if excluded |

Plus `results/scz_samples.parquet` and a data dictionary `results/DATA_DICTIONARY.md`.

### FR-9 — Validation report
`results/validation_report.md` containing:
- Per-study table: expected vs obtained (raw and filtered) for Healthy and SCZ, with PASS/WARN/FAIL.
- Filtering waterfall per study (how many dropped at each step and why).
- List of excluded/unlabelled samples.
- Any study skipped (e.g. RDM) and why.
- Checksum failures, if any.

## 6. Non-functional requirements

### 6.1 Reproducibility
- Pinned environment: `environment.yml` (conda/mamba, bioconda channel) for bio tools + `pyproject.toml` for Python.
- Optional `Snakefile` (preferred) or `Makefile` orchestrating stages so each stage is re-runnable independently.
- All parameters in `config/config.yaml`; nothing hardcoded.

### 6.2 Robustness
- Idempotent stages; safe to Ctrl-C and rerun.
- Structured logs to `logs/<stage>/<StudyID>.log`.
- Fail one study ≠ fail the whole run; report at the end.

### 6.3 Platform-specific QC defaults
| Platform | Notes |
|---|---|
| Illumina (PE) | standard fastp, paired mode, `--detect_adapter_for_pe` |
| BGISEQ/DNBSEQ | fastp with BGI adapters specified explicitly |
| Ion Torrent (SE, variable length) | single-end, length filter (e.g. ≥ 50 bp), no poly-G trimming |

### 6.4 Resources
- Must run on a laptop in `--subset` mode; full run expected on a machine with ≥ 16 GB RAM and ~1 TB free disk (Claude Code should compute the real total in dry-run and update this).

## 7. Proposed repo layout

```
scz-microbiome-data/
├── README.md
├── CLAUDE.md                 # notes for Claude Code: conventions, how to run
├── environment.yml
├── pyproject.toml
├── Snakefile
├── config/
│   ├── config.yaml
│   ├── studies.yaml          # generated from sTable1.xlsx
│   └── label_maps/<StudyID>.yaml
├── data/
│   ├── sTable1.xlsx
│   ├── raw_metadata/
│   ├── raw_fastq/
│   └── manual/Vasileva_2024_SCZ/
├── src/scz_data/
│   ├── parse_table.py        # FR-1
│   ├── fetch/ena.py          # FR-2
│   ├── fetch/gsa.py
│   ├── fetch/cngb.py
│   ├── fetch/manual.py
│   ├── label.py              # FR-3
│   ├── filter.py             # FR-4
│   ├── download.py           # FR-5
│   ├── qc.py                 # FR-6 wrappers
│   ├── harmonize.py          # FR-8
│   └── report.py             # FR-9
├── tests/
└── results/
```

## 8. Implementation phases (for Claude Code)

| Phase | Deliverable | Done when |
|---|---|---|
| 0. Discovery | Short `docs/discovery.md`: for each accession, the confirmed archive URL, access type (open/controlled), metadata fields actually present, library strategy, layout, and estimated total size. | Yashvi has reviewed it. **Stop here and ask before Phase 1 if any study is controlled-access, 16S, or labels are missing.** |
| 1. Config + metadata | FR-1, FR-2, FR-3 | `raw_metadata/*.tsv` exist for 5 public studies; labels mapped. |
| 2. Filtering + dry-run | FR-4, FR-5 `--dry-run` | Count table vs Table S1 printed; total download size known. |
| 3. Download | FR-5 | All files present with valid MD5 (start with `--subset 5`). |
| 4. QC | FR-6 | `read_counts.tsv` complete. |
| 5. Harmonize + report | FR-8, FR-9 | `scz_samples.tsv` + `validation_report.md` generated. |
| 6. (Optional) Profiling | FR-7 | Merged MetaPhlAn table. |

## 9. Acceptance criteria

- [ ] `studies.yaml` contains exactly the 6 SCZ studies from Table S1.
- [ ] Metadata retrieved for all public studies (5); RDM handled as manual without crashing.
- [ ] Zhu A and B are split by platform with no overlapping samples.
- [ ] Filtered Healthy/SCZ counts within ±2 of Table S1 for each study, or a documented reason for the difference.
- [ ] 100% of downloaded FASTQs pass MD5.
- [ ] `scz_samples.tsv` matches the schema in FR-8 with no duplicate `sample_id`.
- [ ] Unit tests for: accession→archive inference, label mapping, Zhu platform split, count validation.
- [ ] Full pipeline re-run is a no-op (idempotent).

## 10. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Vasileva_2024 data needs an access request | Email the corresponding author / UQ RDM; pipeline supports manual drop-in. |
| GSA / CNGB data may be controlled access or have slow FTP | Check access in Phase 0; look for ENA/SRA mirrors; use resumable downloads. |
| Disease labels missing from archive metadata | Pull from paper supplementary tables; Claude Code asks which file rather than guessing. |
| Exact filtering criteria behind Table S1 "Filtered" counts unknown | Read the source paper's methods for each study; document rules in `label_maps`/`config`. |
| Ion Torrent data behaves differently in profilers | Platform kept as a covariate; batch-effect correction handled in the analysis PRD. |
| Disk space | Dry-run size check; stream + delete raw FASTQ after QC (configurable `keep_raw: false`). |

## 11. Kick-off prompt for Claude Code

> Read `PRD_SCZ_Data_Retrieval.md` and `data/sTable1.xlsx`. Start with Phase 0 only: confirm the archive, access type, metadata fields, library strategy and total size for each of the 6 SCZ accessions, write `docs/discovery.md`, and stop for my review. Don't download any FASTQs yet.
