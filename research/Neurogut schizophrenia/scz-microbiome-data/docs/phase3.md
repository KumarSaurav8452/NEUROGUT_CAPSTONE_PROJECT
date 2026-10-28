# Phase 3 — Stream mode: download → QC → host removal → delete raw (FR-5, FR-6)

**Built:** 25 Oct 2026 · **Tools installed:** 26 Oct 2026 · **Status:** code complete; tools and index installed and verified with real fastp/bowtie2 on synthetic reads. **No archive FASTQ downloaded yet.**

## What one sample goes through
`python -m scz_data stream [--subset N] [--study ID]` processes **one sample at a time** (`parallel = 1`), smallest first:

1. **Disk check.** It needs the missing raw bytes, plus the host-removed output if `keep_clean`, plus a 3 GB margin. Free space is measured on the drive that holds `data/`. A sample that doesn't fit is **skipped**, not started.
2. **Download** each file over HTTPS into `data/raw_fastq/<StudyID>/<run>/`:
   - resumes from `*.part` via HTTP Range;
   - **checks the MD5** against the archive's checksum;
   - deletes the file and retries on mismatch (up to 3 tries).
3. **QC + host removal per run**, platform-aware (PRD §6.3):
   ```
   fastp -i R1 [-I R2] --stdout <platform opts> -j run.fastp.json | bowtie2 --very-sensitive -x GRCh38 --interleaved - --un-conc-gz out.R%.fq.gz -S /dev/null
   ```
   - fastp streams straight into bowtie2, so trimmed reads still containing host DNA never hit the disk.
   - Illumina PE uses `--detect_adapter_for_pe`. BGISEQ uses explicit BGI adapters. Ion Torrent SE uses `--disable_trim_poly_g`. All use `--length_required 50`.
   - Each run's shell script, fastp json/html and bowtie2 log are kept in `results/qc/<StudyID>/<sample_id>/`.
4. **Counts:**
   - `raw_reads` and `clean_reads` come from fastp. `host_removed_reads` comes from bowtie2: the pairs not aligned concordantly × 2, counted as single reads to match fastp.
   - A consistency check makes sure bowtie2 received exactly the reads fastp passed.
   - Multi-run samples (Thirion top-ups) are summed, and their outputs are concatenated into one `<sample_id>_R1/_R2.fq.gz`.
5. **State + delete:** it writes `data/qc_state/<sample_id>.json`, then deletes the raw FASTQs (`keep_raw: false`). It also rebuilds `results/qc/read_counts.tsv`, which `python -m scz_data filter` uses for the FR-4 depth filter (step 5).

**Robustness:**
- A finished sample is skipped on rerun, so the run is idempotent.
- Ctrl-C keeps partial downloads, which resume.
- A failed sample keeps its raw files, writes `<sample_id>.failed.json` and doesn't stop the others. The next run retries it without re-downloading.

**Safety:** the command prints the plan (samples, GB, free disk) and **asks `[y/N]`**. No TTY counts as "no". `--dry-run` prints the plan only. `--yes` skips the prompt; it is only for when you have explicitly agreed.

## Why the tools run in WSL and the data stays on C:
fastp and bowtie2 have no Windows builds, so they run in **WSL Ubuntu** (`tools.runner: wsl`); the Python pipeline converts paths to `/mnt/c/...`.

The WSL disk reports 945 GB free, but it's a virtual disk on C:, and **space freed inside it is not returned to Windows**. So every transient file (raw and clean FASTQs, logs) stays on the Windows side under `data/`. Only the permanent ~4 GB GRCh38 index lives inside WSL (`~/scz-ref`), where reading it is fast.

## Verified
- **Unit tests:** `python -m pytest -q` passes 42 tests (15 new for Phase 3). These cover:
  - resumable download, MD5 retry and failure, presence check;
  - R1/R2 detection for ENA (incl. its 3-file layout), GSA `_f1/_r2`, CNGB `.1/.2` and `_combine_R1`;
  - the platform-specific fastp options, the PE/SE/count-only commands and the WSL path conversion;
  - bowtie2 summary parsing;
  - full sample processing (SE + PE, 2 runs merged, raw deleted);
  - failure keeps raw → retry succeeds; disk check skips the sample; and the disk-need maths.
- **Smoke test, stub tools:** `python scripts/smoke_stream.py` runs the real WSL runner, bash `pipefail` pipeline, paths with spaces and two merged paired runs, with stub fastp/bowtie2 (`tests/stubs/`) and a local HTTP server. Result: SMOKE OK.
- **Smoke test, real tools:** `python scripts/smoke_stream.py --real` uses the installed fastp 0.23.2 + bowtie2 2.5.3 + GRCh38. It builds 500 synthetic Illumina pairs over 2 runs: 200 pairs cut from human chr1 (taken from the index via `bowtie2-inspect`) and 300 random-sequence pairs. Result:
  - **0/200 human pairs kept, 300/300 non-human pairs kept**, host_fraction 0.40, exactly as constructed;
  - index load + alignment took ~5 s per run;
  - SMOKE OK (real tools).
- **Bug found and fixed by the real-tools run:** the bowtie2 wrapper hands `--un-conc-gz`/`--un-gz` paths to `sh` unquoted, so the space in "Neurogut schizophrenia" made it fail (exit 141). bowtie2 now writes through a space-free symlink to the output folder (`mktemp -d`, removed by `trap`). This is covered by a unit test.
- **Not yet tested: a real archive download.** That's the first `--subset 1` run.

## Setup (done 26 Oct 2026)
```
wsl.exe -d Ubuntu -- bash "/mnt/c/Neurogut schizophrenia/scz-microbiome-data/scripts/setup_wsl_tools.sh"
python -m scz_data check-tools     # -> tools ready: fastp=fastp 0.23.2, bowtie2=2.5.3, index=ok
```
- **micromamba env `scz-qc`** (`~/micromamba`, 449 MB): fastp 0.23.2, bowtie2 2.5.3, pigz. These are the GutMIND versions.
- **GRCh38 no-alt bowtie2 index** from `genome-idx.s3.amazonaws.com/bt/GRCh38_noalt_as.zip` (3,749,245,718 bytes; every zip member CRC checked on extraction). It sits in `~/scz-ref/` (3.9 GB). The zip has no top-level folder, so the files sit directly in `~/scz-ref`, and `tools.host_index` is `~/scz-ref/GRCh38_noalt_as`.
- **Download location:** the zip was downloaded to the Windows side (`data/cache/ref/`) and deleted after extraction, so it doesn't stay trapped in the WSL virtual disk. `unzip` isn't installed in WSL, so python3 `zipfile` does the extraction.
- **Rerunning the script is a no-op** (verified: nothing re-downloaded).
- **C: free: 26.2 GB → 22.0 GB.**

## What fits on this laptop (22 GB free on C: after setup)

| Mode | Peak disk | Outcome |
|---|---|---|
| `keep_clean: true` (default) | raw + clean of one sample, and **host-removed reads accumulate** (~0.9 × raw) | `--subset 1` (9 samples, 32.5 GB raw) would already fill the disk after ~5–6 samples; the rest get skipped. **The full run is impossible here (~3 TB of clean reads).** |
| `keep_clean: false` | raw of one sample + 3 GB (largest sample 23.8 GB, Zhu B) | All 744 samples get read counts (depth filter), except a few of the largest Zhu B / Li / Thirion samples that exceed ~19 GB. **MetaPhlAn (Phase 6) then needs a re-download elsewhere.** |

**Time:** at parallel 1, the bottleneck is download speed from CNGB/GSA in China plus bowtie2 at 8 threads, very roughly 20–40 min per 20 M-pair sample. 744 samples means weeks of continuous running. This is an order-of-magnitude estimate; the first `--subset 1` run will give real numbers.
