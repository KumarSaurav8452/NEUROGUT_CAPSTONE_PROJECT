# scz-microbiome-data

Reproducible retrieval and harmonisation of the six schizophrenia gut-metagenome cohorts in **GutMIND Table S1** (Ju et al., *Gut Microbes* 2026, doi:10.1080/19490976.2026.2630563).

Status: **Phase 3 code done** (stream mode: download → fastp → bowtie2 host removal → delete raw), with no real data processed yet. Harmonisation, reporting and profiling come later (PRD §8). See `docs/phase1.md`, `docs/phase2.md`, `docs/phase3.md`.

## Quick start
```bash
pip install -e .[test]
python -m scz_data phase1        # = config + metadata + label
python -m pytest -q
```

| Stage | Command | Output |
|---|---|---|
| FR-1 config | `python -m scz_data config` | `config/studies.yaml` |
| FR-2 metadata | `python -m scz_data metadata [--study ID] [--refresh]` | `data/raw_metadata/<StudyID>.tsv` (one row per run) |
| FR-3 labels | `python -m scz_data label [--study ID]` | `data/labelled/<StudyID>.tsv`, `results/label_counts_vs_table_s1.tsv` |
| FR-4 filter | `python -m scz_data filter [--study ID]` | `data/filtered/<StudyID>.samples.tsv` (one row per sample), `results/filter_waterfall.tsv`, `results/filter_counts_vs_table_s1.tsv` |
| FR-5 dry-run | `python -m scz_data download --dry-run [--subset N]` | `results/download_manifest[.subsetN].tsv` + size / free-disk summary |

| Tools check | `python -m scz_data check-tools` | fastp / bowtie2 versions + host index presence |
| FR-5/6 stream | `python -m scz_data stream [--subset N] [--dry-run]` | per sample: download (MD5) → fastp \| bowtie2 → `data/qc_state/`, `results/qc/read_counts.tsv`, `data/clean_fastq/`; raw deleted |
| Profile status | `python -m scz_data profile-status` | done / failed / pending per study, QC red flags, refreshed merged tables |
| **Profile mode** (used here) | `python -m scz_data profile [--dry-run]` | first 500 k reads per file streamed → fastp \| bowtie2 \| MetaPhlAn 3 → `results/profiles/metaphlan_merged.tsv`, `metaphlan_unclassified.tsv`, `results/qc/read_estimates.tsv`; Zhu A from curatedMetagenomicData. ~30 GB instead of 3.5 TB: see `docs/phase3b.md` |

`python -m scz_data phase2 --dry-run` runs filter and the dry-run together. `stream` prints the plan and asks `[y/N]` before downloading. After a stream run, rerun `python -m scz_data filter` to apply the depth filter.

### Phase 3 tools (WSL)
fastp and bowtie2 run inside WSL Ubuntu. One-time setup (~3.6 GB download, ~4 GB on C:):
```
wsl.exe -d Ubuntu -- bash "/mnt/c/Neurogut schizophrenia/scz-microbiome-data/scripts/setup_wsl_tools.sh"
```
Then check with `python -m scz_data check-tools`. Smoke tests that download nothing from the internet:
- `python scripts/smoke_stream.py` runs the WSL pipeline end to end with stub tools.
- `python scripts/smoke_stream.py --real` runs the installed fastp/bowtie2/GRCh38 on synthetic human + non-human pairs.

HTTP responses are cached in `data/cache/http/`, so reruns are offline and idempotent. Use `--refresh` to refetch. Logs go to `logs/<stage>/<StudyID>.log`.

## Studies and sources

| StudyID | Metadata source | Label source |
|---|---|---|
| Li_2023_SCZ | GSA CRA004772 metadata export | GSA `Sample title` (HC / SZ/0w; 4w/8w follow-ups excluded) |
| Xu_2020_SCZ | CNGB CNP0000401 | disease-only; WGS runs = SCZ, 16S runs excluded |
| Zhu_2020A_SCZ | CNGB CNP0000119, Illumina runs; FASTQs via ENA mirror PRJEB29127 | Zhu 2020 Supplementary Data 1 |
| Zhu_2020B_SCZ | CNGB CNP0000119, BGISEQ runs | Zhu 2020 Supplementary Data 9a |
| Thirion_2023A_SCZ | ENA PRJEB41217 (SCZ) + PRJEB41786, PRJEB41787 (controls) | ENA project; **no per-sample BMI, so the BMI filter is skipped and the gap reported** |
| Vasileva_2024_SCZ | manual drop-in `data/manual/Vasileva_2024_SCZ/` | `config/label_maps/Vasileva_2024_SCZ.yaml` (adjust when data arrives) |

### Vasileva manual drop-in
Put `metadata.csv` in `data/manual/Vasileva_2024_SCZ/` with at least `sample_name` and `fastq_files` (`;`-joined paths relative to that folder), plus a `status` column for labelling. Until then the study is reported as `SKIPPED: awaiting access`.

## Layout
```
config/            config.yaml (all parameters), studies.yaml (generated), label_maps/
data/              sTable1.xlsx, supplements/, raw_metadata/, labelled/, manual/, cache/
docs/discovery.md  Phase 0 report + PRD corrections
src/scz_data/      parse_table.py, fetch/{http,ena,cngb,gsa,manual,schema}.py, label.py, filter.py, download.py,
                   qc.py, stream.py, validate.py, cli.py
scripts/           setup_wsl_tools.sh, smoke_stream.py
tests/
```
