# Phase 3b — Profile mode: done in ~2 days on this laptop

**Date:** 26 Oct 2026 · **Why:** the full-sample stream (Phase 3) measured **~0.2–0.3 MB/s from ENA, CNGB and GSA alike**, so the limit is this connection. At that speed the 3.48 TB dataset needs ~6 months, and the disk has ~22 GB. The goal is to finish in 2–3 days.

## What changed

| | Phase 3 (full reads) | **Phase 3b (profile mode)** |
|---|---|---|
| Reads fetched per sample | all (median 2.6–10.7 GB) | **first 500 k reads per file** (Thirion: 300 k), ~50–90 MB |
| Transfer, all samples | 3,482 GB | **~29–33 GB** |
| Time at 0.25 MB/s | ~6 months | **~32–37 h** |
| Disk | one whole sample (≤ 24 GB) | ≤ 6 prefetched subsamples (< 1 GB) |
| Profiler | MetaPhlAn 4 (GutMIND) | **MetaPhlAn 3, `mpa_v30`** (see below) |
| Zhu_2020A | 1,025 GB download | **0 bytes of reads**: curatedMetagenomicData profiles |

### How a subsample is fetched
`python -m scz_data profile` opens each FASTQ over HTTPS (FTP fallback for GSA) and decompresses the gzip stream on the fly.
- **It closes the connection as soon as the first N reads are in**, so only those bytes cross the network.
- R1/R2 are checked read-by-read for matching names.
- If a run has fewer than N reads, the next run of the same sample is used (Thirion top-ups).
- There is no MD5 check, since a partial file can't be checksummed. Instead every record is validated (4-line structure, `@`/`+`, sequence length = quality length), and gzip's own integrity check covers the decompression.

Then **fastp → bowtie2 `--sensitive` vs GRCh38 → MetaPhlAn 3 `--unclassified_estimation`** runs on the subsample. The profile, fastp json, bowtie2 and MetaPhlAn logs are kept in `results/profiles/<StudyID>/`, and the reads are deleted. Downloads run up to 6 samples ahead of processing, and core cohorts go first (Zhu B → Li → Xu → Thirion).

### Why MetaPhlAn 3 and not MetaPhlAn 4
- **MetaPhlAn 4's index doesn't fit:** its `mpa_vOct22` database ships without a bowtie2 index. The prebuilt index is **21.3 GB**, and building it needs far more than WSL's 7 GB RAM.
- **`mpa_v30` is small:** 0.37 GB, and its index is built locally in WSL (`scripts/setup_metaphlan3.sh`).
- **It matches curatedMetagenomicData:** `mpa_v30` is the database cMD used, so **our profiles and cMD's Zhu_2020A profiles are on the same taxonomy**, with no MetaPhlAn 3-vs-4 batch effect inside this dataset.
- **Consequence:** species names follow the 2019 ChocoPhlAn taxonomy rather than SGBs. Matching GutMIND's MetaPhlAn 4 numbers exactly isn't possible either way (see "Deviations").

### Zhu_2020A from curatedMetagenomicData
- **What it is:** cMD `2021-03-31.ZhuF_2020`, MetaPhlAn 3 + HUMAnN 3 at **full depth**, from Bioconductor ExperimentHub (EH5944 species, EH5942 pathways). It was fetched directly from the OSN mirror: 128 KB + 5.4 MB.
- **Conversion:** `scripts/cmd_rda_to_tsv.R` turns it into `data/external/cmd/ZhuF_2020.{relative_abundance,pathway_abundance}.tsv`, giving 792 taxa / 21,282 pathway rows × 171 samples.
- **Matching:** columns are BGI IDs (`wHAXPI…`) = our `sample_name`. It covers the same 171 samples, 81 HC / 90 SCZ, exactly matching Supp Data 1.
- **Depth:** taken from the ENA read counts (files were host-removed by the submitters).
- **Limitation:** cMD has no unclassified estimate, so **filter step 6 stays pending for Zhu A**. Table S1's gap there is only 2/2, within tolerance.

### Full-depth read counts for the depth filter (FR-4 step 5)
Taken in this order of preference:
1. exact counts from a full-sample stream run (`results/qc/read_counts.tsv`: Xu CNS0063952, Thirion SAMEA121025472);
2. archive read counts (ENA: Zhu A, Thirion);
3. **estimates**: file size ÷ compressed bytes per read on the subsample, × host-removed fraction (`results/qc/read_estimates.tsv`).

**Estimate accuracy, measured:**
- Xu CNS0063952: estimated **7.76 M vs exact 7.66 M (+1.3 %)**.
- Thirion: 14.1 M vs ENA's 15.8 M (−11 %; Ion Torrent read lengths vary). That's why archive counts win when present.

## Measured so far (26 Oct 2026)
- **MetaPhlAn 3 setup:** 3.0.14 + `mpa_v30` (database tar MD5-checked by MetaPhlAn); the bowtie2 index was built locally in ~14 min, 2.1 GB in WSL.
- **One Zhu B sample (CNS0092497):**
  - 500 k pairs fetched as ~120 MB;
  - fastp kept 430 k pairs;
  - host 0.01 %;
  - MetaPhlAn: 24 species, UNKNOWN 23.9 %;
  - **QC + host removal + MetaPhlAn took 94 s**, so ~15 h for all 573 samples. That's less than the download time, and the two overlap.
- **Bug found on the first real run:** MetaPhlAn 3 calls the option `--unknown_estimation` (`--unclassified_estimation` is MetaPhlAn 4). Fixed in config. Failed samples now **keep their subsample** (with a `subsample.json` marker), so a retry doesn't download again.

## Taken from the team runbook ("Shotgun Metagenomics to MetaPhlAn 3 Abundance Table", 19 Oct 2026)
- **Profiler choice confirmed.** The team's training data (`Source_Data_24Oct2022.xlsx`) uses **MetaPhlAn 3 clades**. MetaPhlAn 4 would break the feature match, so MetaPhlAn 3.0.14 + `mpa_v30` is right for this project, not just a disk/RAM workaround.
- **Added `results/profiles/metaphlan_merged_all_levels.tsv`:** all taxonomic levels, in the layout of `merge_metaphlan_tables.py`, so it aligns with the training data's features.
- **Added `results/profiles/profile_qc.tsv`** with the runbook's red flags: < 10 species, host > 5 %, less than half the subsample kept, and identical numbers in two samples (a reused file).
  - The runbook's "< 1 M clean pairs" flag doesn't apply here: subsamples are 500 k by design.
  - **Expected:** species counts are lower than the runbook's 33–60 at full depth. The first samples have a median of 19 and a minimum of 14, because rare species fall out at 500 k reads.
- **Added `python -m scz_data profile-status`:** done + failed + pending = total per study, flagged samples, failure reasons and median time. It also refreshes the merged tables.
- **Zenodo mirror** for `mpa_v30` (records/3957592) recorded in config, in case cibio stops serving it.
- **Not adopted:** the runbook's "never work under /mnt/c". We keep transient files on the Windows side on purpose. For whole samples, space freed inside the WSL disk isn't returned to C:. In profile mode the transient files are < 1 GB, so either would work.
- **Power, from the runbook's troubleshooting section:** a long run dies on sleep, hibernation or power loss. On 26 Oct this laptop was **on battery, with hibernate-after-60-min on battery**. Keep it plugged in. Rerunning `python -m scz_data profile` resumes; finished samples are skipped.

## Decision: unclassified filter (FR-4 step 6) switched off (26 Oct 2026, agreed with Yashvi)
GutMIND drops samples with > 30 % unclassified reads, but that cut-off was set on **MetaPhlAn 4**, whose much larger SGB database classifies far more reads. MetaPhlAn 3's `UNKNOWN` estimate is systematically higher:
- **Zhu B:** median 29.9 % (IQR 23.9–39.3 %). 44 of 89 samples (22 HC, 22 SCZ) exceed 30 %, whereas GutMIND removed only 1–2 per group.
- **Li, first 4 samples:** 36–53 %. GutMIND kept 30 of 36 controls.

Applied as-is, the filter would remove about half the samples for a reason unrelated to quality. Re-tuning the cut-off until counts match Table S1 would be fitting to the target, which the PRD rules out. So:
- `filters.apply_unclassified_filter: false`, and step 6 is reported as *skipped*.
- Every sample's `unclassified_frac` is still recorded (`data/filtered/*.samples.tsv`, `results/profiles/metaphlan_unclassified.tsv`), so it can be used as a covariate or re-filtered later.
- Genuinely bad samples are caught by `profile_qc.tsv` flags (e.g. < 10 species: Zhu B CNS0092499 with 5 species).

## Thirion read from NCBI's AWS copy (27 Oct 2026, agreed with Yashvi)
- **Parallel downloads:** `profile.fetch_workers: 3`.
  - On ENA, 1 connection gave 0.30 MB/s and 3 together gave 0.58 MB/s.
  - On CNGB (Xu), 3 connections gave no gain.
- **ENA slowdown:** from ~16:20, ENA dropped to ~35 KB/s per connection. Thirion fell to ~5 samples/h with repeated stalls, while a Cloudflare test on the same Wi-Fi gave 3.7 MB/s.
- **Switch:** the remaining Thirion runs are now read with `fastq-dump -X 300000` (sra-tools 3.4.1, `scripts/setup_sratools.sh`) from NCBI's public AWS Open Data bucket, `sra-pub-run-odp`.
  - It uses anonymous HTTPS; there is no account and no cost.
  - fastq-dump fetches only the blobs holding the first 300 k reads: **39 MB** for ERR16139458, the same as from ENA.
  - It gives the same reads with the same read IDs (`ERR….1, .2, …`).
- **Fallback:** if AWS fails twice, the ENA FASTQ is used.
- **Some runs hang on AWS** (e.g. ERR8262894: 1,000 reads took 323 s and 227 MB); most do not (36 of 45 ERR826 runs were fine).
- **A hung fastq-dump ignores SIGTERM.** Hung copies kept downloading in the background and took bandwidth from the rest.
- **So, as of 23:45:**
  - `timeout -s KILL` at 4 min (`timeout_s: 240`).
  - `tries: 1`: every timeout had repeated on the retry, so a hung run goes straight to ENA.
  - The watchdog alerts on a fastq-dump pile-up.
- **Logging:** each sample's `subsample.json` and the log line record the source (`sra_aws` / `archive`).
- **Byte counts:** `bytes_per_read` for AWS-read samples is measured on our own `gzip -1` output, not ENA's gzip, so it isn't comparable. Thirion's depth filter uses ENA archive read counts, so nothing depends on it.
- **Transient transfer errors:** a malformed record (one garbled ENA transfer; the same file re-read cleanly) is now retried like other transient errors.

## Deviations from GutMIND to keep in mind
- **Profiles come from 500 k-read subsamples** (300 k for Thirion), not full depth, except Zhu A (full depth via cMD). Dominant and common species are robust at this depth; rare species (< ~0.01 %) will be missed more often.
- **MetaPhlAn 3 / `mpa_v30` instead of MetaPhlAn 4 / `mpa_vOct22`.**
- **Host removal uses `--sensitive`** instead of `--very-sensitive`, which is twice as fast. The measured host fractions are ≈ 0 for these already-cleaned uploads.

## Outputs
- `results/profiles/metaphlan_merged.tsv`: species × samples, relative abundance renormalised to 100 over classified species (the cMD convention), for all studies including Zhu A.
- `results/profiles/metaphlan_unclassified.tsv`: feeds FR-4 step 6.
- `results/qc/read_estimates.tsv`: feeds FR-4 step 5. Then `python -m scz_data filter` gives the final Table S1 comparison.

## Commands
```
wsl.exe -d Ubuntu -- bash "/mnt/c/Neurogut schizophrenia/scz-microbiome-data/scripts/setup_metaphlan3.sh"   # once
python -m scz_data profile --dry-run      # plan: samples, GB, hours
python -m scz_data profile                # asks [y/N]; resumable, finished samples are skipped
python -m scz_data filter                 # apply depth + unclassified filters
```
