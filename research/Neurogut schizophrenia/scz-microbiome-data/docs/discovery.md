# Phase 0 — Discovery report

**PRD:** `PRD_SCZ_Data_Retrieval.md` v1.0 · **Run date:** 25 Oct 2026 · **Status:** awaiting Yashvi's review — no FASTQs downloaded.

All numbers below come from live queries made on 25 Oct 2026 to ENA Portal API, EBI BioSamples, CNGBdb (`/cnsa/ajax/project/public_view/` plus the public metadata TSVs on `ftp.cngb.org`) and the GSA metadata export / download server. Sizes are bytes summed from archive file listings and given in GB (10⁹ bytes).

---

## 1. Summary

| StudyID | Primary source | Access | Strategy | Layout | Platform (archive) | Labels in metadata? | Raw count vs Table S1 | Size to download |
|---|---|---|---|---|---|---|---|---|
| Li_2023_SCZ | GSA CRA004772 (BioProject PRJCA006197) | Open | WGS | PE 2×100 | Illumina NovaSeq 6000 | **Yes** (`Sample title`) | 36 HC + 19 SCZ ✅ exact | 368.8 GB (baseline only) |
| Xu_2020_SCZ | CNGB CNP0000401 | Open | **WGS 40 + 16S 88** | PE | Illumina HiSeq 4000 (WGS) | No (none needed: all WGS = SCZ) | 0 + 40 ✅ exact | 59.3 GB |
| Zhu_2020A_SCZ | CNGB CNP0000119 → **ENA mirror PRJEB29127** | Open | WGS | PE | Illumina HiSeq X Ten | **No** | 171 human Illumina = 81 + 90 ✅ total matches | 1,025 GB (ENA) / 977 GB (CNGB) |
| Zhu_2020B_SCZ | CNGB CNP0000119 (no mirror) | Open | WGS | PE | BGISEQ-500 | **No** | 90 human BGISEQ = 45 + 45 ✅ total matches | 1,001 GB |
| Thirion_2023A_SCZ | ENA PRJEB41217 (SCZ) + **PRJEB41786 + PRJEB41787 (controls)** | Open | WGS | SE | Ion Torrent Proton | By project only | 132 SCZ ✅; 257 HC candidates vs 174 expected ⚠️ | 352 GB SCZ + 684 GB HC candidates |
| Vasileva_2024_SCZ | UQ RDM | **Not public** (access request) | — | — | Illumina (per Table S1) | — | — | unknown |

**Estimated total for the 5 public studies: ≈ 3.5 TB**, with Thirion's controls downloaded in full (≈ 3.4 TB if only the 174 relevant controls are known in advance). That is roughly 3.5× the PRD's "~1 TB" estimate in §6.4. With `keep_raw: false` the peak disk use is much lower, but total network transfer is still ~3.5 TB.

### Stop conditions triggered (PRD §8, Phase 0)
- **16S present:** Xu_2020 (CNP0000401) mixes 88 16S amplicon runs with the 40 shotgun runs. Plan: keep the 40 WGS runs and flag/drop the 16S runs in FR-4 step 1. No action needed from you unless you disagree.
- **Labels missing:** Zhu_2020A/B (CNP0000119) have **no** case/control field in CNGB or ENA. Per FR-3, I need a source file — see §3.
- **Controlled / non-public:** Vasileva_2024 (RDM) needs an access request, as the PRD expects.
- **Unknown selection:** Thirion's 174 raw controls are a subset of 257 public control samples, and the selection rule isn't in the metadata.

---

## 2. Per-study detail

### 2.1 Li_2023_SCZ — GSA CRA004772
- **URLs:** browse `https://ngdc.cncb.ac.cn/gsa/browse/CRA004772` · files `https://download.cncb.ac.cn/gsa2/CRA004772/` (FTP `ftp://download.big.ac.cn/gsa2/CRA004772/`) · metadata `POST https://ngdc.cncb.ac.cn/gsa/file/exportExcelFile` with `type=3&dlAcession=CRA004772`, which returns an xlsx with sheets Sample / Experiment / Run.
- **Access:** open; HTTPS directory listing works without login.
- **Content:** 76 samples = 76 experiments = 76 runs, 152 FASTQ files, WGS / METAGENOMIC / PAIRED, 2×100 bp, Illumina NovaSeq 6000. Location China: Wuhu.
- **Labels:** `Sample title` holds `HC` = 36, `SZ/0w` = 19, `4w` = 14, `8w` = 7. The `4w`/`8w` samples are treatment follow-ups and get dropped as non-baseline in FR-4 step 3. HC 36 and SZ/0w 19 match Table S1's raw counts exactly. `Public description` reads e.g. "Gut microbiota from healthy control 3".
- **Fields present:** sample name/accession, collection date, geo location, platform, strategy, layout, read lengths, file names **with byte sizes**, **MD5 per file**, FTP URLs. Age, sex and BMI columns exist but are **empty**.
- **Size:** 497.6 GB total; baseline (HC + SZ/0w) 368.8 GB.
- **Filtering to 30 HC / 17 SCZ:** the 6 HC and 2 SCZ removed are not identifiable from metadata. Candidate explanation: depth/QC in FR-4 step 4. To be checked after QC.

### 2.2 Xu_2020_SCZ — CNGB CNP0000401
- **URLs:** `https://db.cngb.org/data_resources/project/CNP0000401/` · files `https://ftp.cngb.org/pub/CNSA/data1/CNP0000401/<CNS>/<CNX>/<CNR>/` · metadata `https://ftp.cngb.org/pub/CNSA/data7/public_info/CNP0000401/` (`metadata_*_experiment.tsv`, `metadata_*_sample_GSC_MIxS_environmental_sample.tsv`, `data_download_links_*_ftp.txt`).
- **Access:** open. **No ENA/SRA mirror** (`external_accession_id` is empty, and an ENA text search found none). Literature PMID listed by CNGB: 31255682.
- **Content:** 128 samples/runs:
  - 40 × WGS, paired, Illumina HiSeq 4000, sample names `wmb-#`, collected 2015-09-02 → **these are the 40 SCZ shotgun samples** (matches Table S1 raw 40).
  - 88 × AMPLICON (16S), single, HiSeq 2500, names `H#`/`S#`, collected 2017-10-02 → **exclude** (different sub-study, not shotgun).
- **Labels:** no disease field, and none needed, because Table S1 lists 0 controls and every WGS sample is SCZ. Flagged `disease_only: true` (PRD special case 2).
- **Fields present:** run/experiment/sample accessions, library strategy/layout, platform, instrument, file names, **MD5**. The MIxS sample sheet has host_age/host_sex/BMI columns, but they are **all empty**.
- **Size:** 80 WGS files = 59.3 GB (sizes taken from HEAD requests).
- **Filtering 40 → 39:** likely one sample failing depth/QC. To be checked after QC.

### 2.3 Zhu_2020A_SCZ & Zhu_2020B_SCZ — CNGB CNP0000119
- **URLs:** `https://db.cngb.org/data_resources/project/CNP0000119/` · files `https://ftp.cngb.org/pub/CNSA/data1/CNP0000119/…` · metadata `https://ftp.cngb.org/pub/CNSA/data7/public_info/CNP0000119/`. Title: "A causal role of the gut microbiome in schizophrenia". PMID listed by CNGB: 31391545. CNGB reports 2.34 TB for the whole project.
- **ENA mirror:** CNGB lists **PRJEB29127**. It contains only the **171 Illumina human samples** (sample `Submitter Id` = CNGB `CNS…` accession, so they link 1:1). The BGISEQ samples are **not mirrored**. Note: `PRJEB29415` ("Schizophrenia metagenome") turned up in an ENA search but is an empty shell with 0 runs, so it can be ignored.
- **Access:** open on both archives.
- **Content (357 CNGB samples, 1 run each):**

  | Platform | sample_title | Host | Layout | Year | n | Use |
  |---|---|---|---|---|---|---|
  | ILLUMINA HiSeq X Ten | (blank) | human | PE | 2016 | **171** | Zhu_2020A (81 HC + 90 SCZ) |
  | ILLUMINA HiSeq X Ten | `medication` | human | PE | 2016 | 38 | exclude (post-treatment follow-up) |
  | BGISEQ-500 | (blank) | human | PE | 2017 | **90** | Zhu_2020B (45 HC + 45 SCZ) |
  | BGISEQ-500 | `FMT mice` | mouse | SE | 2018 | 54 | exclude (not human) |
  | BGISEQ-500 | `donor` | human | SE | 2018 | 4 | exclude (FMT donors) |

  The platform split from special case 1 works as planned (Illumina → A, BGISEQ → B). The two groups don't overlap: each sample has exactly one run on one platform.
- **Layout correction:** the PRD (special case 5) assumes BGISEQ is single-end. For Zhu_2020B the **90 human cohort samples are paired-end**; only the excluded mice and donor samples are SE. QC should use fastp PE mode with BGI adapters.
- **Files are already host-depleted:** file names are `*.rmhost.1.fq.gz` / `*.rmhost.2.fq.gz`. FR-6 host removal should still run for consistency, but expect almost no reads removed. `raw_reads` for Zhu will mean "post-author host removal".
- **Labels: MISSING.** No disease or status field in CNGB sample metadata or in ENA BioSamples (checked SAMEA4968183). Sample names (`wHAXPI…`, `CL1000…`) don't encode group.
- **Fields present:** accessions, platform, instrument, layout, collection year, city, lat/lon, file names, **MD5** (CNGB); ENA adds `read_count`, `base_count`, `fastq_bytes`, `fastq_md5`. No age, sex or BMI.
- **Size:** Zhu A human = 977.0 GB on CNGB / 1,025.5 GB on ENA. Zhu B human = 1,000.9 GB on CNGB (180 files, from HEAD requests).
- **Plan:** fetch Zhu A from ENA (cleaner API, `read_count` available), and Zhu B from the CNGB FTP.

### 2.4 Thirion_2023A_SCZ — ENA PRJEB41217 (+ PRJEB41786, PRJEB41787)
- **URLs:** `https://www.ebi.ac.uk/ena/browser/view/PRJEB41217` · filereport `https://www.ebi.ac.uk/ena/portal/api/filereport?accession=PRJEB41217&result=read_run&fields=…`.
- **Paper:** "Alteration of gut microbiome in patients with schizophrenia indicates links between bacterial tyrosine biosynthesis and cognitive dysfunction". The study description says it compares 132 SCZ with 132 healthy controls (deposited in **PRJEB41786 and PRJEB41787**) and 132 metabolic-syndrome individuals.
- **Access:** open.
- **Content:**

  | Project | Role | Samples | Runs | Runs/sample | Size |
  |---|---|---|---|---|---|
  | PRJEB41217 | SCZ (aliases `Schizo_Change_####`) | **132** | 321 | 1–13 (top-up lanes) | 352.1 GB |
  | PRJEB41786 | Healthy Danish (`VG####`) | 150 | 272 | 1–4 | 390.9 GB |
  | PRJEB41787 | Healthy Danish, DanFunD (`VGDAN_####`) | 107 | 160 | 1–4 | 292.7 GB |

  All runs: WGS / METAGENOMIC / SINGLE / Ion Torrent Proton, with MD5 and `read_count` for every run. Every sample has ≥ 15.8 M reads, so the depth filter is unlikely to explain the heavy filtering.
- **Labels:** none in sample attributes (BioSamples only gives stool / human-gut / Denmark). The group comes from **which project** a sample belongs to: PRJEB41217 → SCZ, PRJEB41786/41787 → Healthy. Label maps will key on study accession.
- **Multiple runs per sample** are sequencing top-ups of the same sample accession (one alias per sample). They get merged per FR-4 step 3 and are not timepoints. The "Schizo_Change" alias refers to the CHANGE trial, but there's no timepoint field, and 132 unique samples = 132 SCZ in Table S1, so each sample appears to be baseline only.
- **Raw-count mismatch:** Table S1 raw HC = 174, but the two control projects hold 150 + 107 = **257**. Filtered counts (53 HC / 47 SCZ) are far below raw, and nothing in the metadata explains the gap: there are no age, sex, BMI or timepoint fields, and all samples pass depth. These look like matching/selection criteria from the source meta-analysis, so the per-sample list is needed (see §3).
- **Size:** 352 GB SCZ + 684 GB for all control candidates = 1,036 GB.

### 2.5 Vasileva_2024_SCZ — RDM
- Not a public accession. The pipeline will read `data/manual/Vasileva_2024_SCZ/metadata.csv` + FASTQs if present, and otherwise log `SKIPPED: awaiting access` (FR-2 manual path). No probing possible.

---

## 3. Decisions / files needed from you before Phase 1

1. **Zhu_2020 case/control labels.** *Update: resolved for both. Zhu A via Supp Data 1 (§3b), Zhu B via Supp Data 9 (§3c).* I need a per-sample table mapping CNGB sample accession (`CNS…`) or sample name (`wHAXPI…` / `CL1000…`) to HC/SCZ. Likely sources:
   - the supplementary data of the Zhu et al. paper (PMIDs listed by CNGB: 31391545 and two others), or
   - the per-sample metadata supplement of the meta-analysis that Table S1 comes from.
   Without it, Zhu A/B can be downloaded but not labelled.
2. **Thirion selection (blocking for exact counts).** *Update: the paper's supplements have no per-sample BMI (§3d). Author contact or fallback needed.* Which 174 of the 257 controls count as "raw", and which 53 HC / 47 SCZ count as "filtered"? The Table S1 paper's per-sample supplement would settle this. If it's not available, the fallback is to keep all 132 SCZ + 257 HC and report the mismatch (FR-4: "reported, not forced").
3. **Source of Table S1.** Which paper does `sTable1.xlsx` come from? Its supplement probably has a per-sample inclusion list for all six studies, which would answer 1 and 2 and the small Li/Xu/Zhu filtered-count gaps in one go.
4. **Disk/transfer budget.** About 3.5 TB of transfer, and about 2 TB for Zhu alone. OK to proceed on that basis, or should Phase 3 start with `--subset 5` only, as the PRD suggests?
5. **Vasileva access.** Has the UQ RDM request been sent?

## 3a. Update after reading the GutMIND paper (25 Oct 2026)

Table S1 comes from **Ju Y, …, Zhu F, Guo R. "GutMIND: A multi-cohort machine learning framework…" *Gut Microbes* 18:1, 2630563 (2026), doi:10.1080/19490976.2026.2630563**. The PDF is in the project root.

**Filtering criteria behind the "Filtered" counts** (Methods, "Sample filtering and species removal"):
1. Drop samples with **< 10 M reads**. The PRD default is 1 M, so it should be 10 M. The paper doesn't say whether this is before or after host removal; I'll assume after fastp + bowtie2 and make it configurable.
2. Drop samples with **> 30 % unclassified at species level** in MetaPhlAn 4 (v4.0.6, `mpa_vOct22_CHOCOPhlAnSGB_202212`).
3. Drop samples with **BMI > 30 kg/m²**.
4. Drop any study with < 10 samples left.
5. Their processing was fastp v0.23.2 → bowtie2 v2.5.3 vs GRCh38 → MetaPhlAn 4.0.6 / HUMAnN 3.9. These are the versions to pin in `environment.yml`.

**What this means for the PRD:**
- **Matching Table S1 counts needs MetaPhlAn 4.** Filter 2 depends on the profile, so FR-7 (MetaPhlAn) can't stay optional if FR-4 is meant to reproduce the counts. HUMAnN can stay optional.
- **Matching Table S1 counts needs per-sample BMI.** None of the archives has BMI for any SCZ study. GutMIND says metadata came from "manual curation of publications, database records, and author communications".
- **Thirion's heavy filtering is now explained.** The SCZ cohort was recruited for *increased waist circumference*, so the BMI > 30 filter plausibly accounts for 132 → 47 SCZ, and the same filter applies to the controls.

**Where per-sample labels / BMI can come from:**

| Source | What it has | Status |
|---|---|---|
| GutMIND figshare (`figshare.com/s/416eae4ed99b8787304b`) | sTable1–sTable10 (1.55 MB). Per the paper, S2–S10 are results tables (diversity, taxa, pathways, models, MGBA-HI) | Listed, not downloaded. Probably no per-sample list |
| GutMIND GitHub (`juyanmei/MetaClassifier`) | Code only, no data | Checked, nothing useful |
| Zhu et al. 2020, *Nat Commun* 11:1612 (doi:10.1038/s41467-020-15457-9) | Supplementary Data 1 = phenotypes of the **discovery cohort**. Supplementary Data 9 (`MOESM12_ESM.xlsx`, 26.4 kB) = the **validation cohort**, 45 SCZ (on antipsychotics) + 45 HC | **Zhu A and Zhu B resolved** (see §3b, §3c) |
| Thirion et al. 2023, *Biol Psychiatry Glob Open Sci* 3:283–291 (doi:10.1016/j.bpsgos.2022.01.009) | Supplement may have per-sample BMI | To check |
| Li et al. 2023, *Schizophr Res* 255:59–66 (doi:10.1016/j.schres.2023.03.005) | Labels already in GSA; supplement may have BMI | To check |
| Xu et al. 2020, *Brain Behav Immun* 85:120–127 (doi:10.1016/j.bbi.2019.06.039) | All SCZ; BMI possibly in supplement | To check |
| GutMIND corresponding authors (Feng Zhu, Ruijin Guo, who also wrote Zhu 2020) | Their curated per-sample inclusion list | Fallback: email request |

## 3b. Zhu_2020A labels — resolved (25 Oct 2026)

Source: Zhu 2020 Supplementary Data 1, "Phenotypes of baseline volunteers", saved as `data/supplements/Zhu2020_NatCommun_SuppData1.xlsx`. The header is on row 4; the key is `BGI ID`, which equals the CNGB `sample_name` (`wHAXPI…`).

- **171 rows, 171 unique IDs, all matching 1:1** to the 171 Illumina human cohort samples in CNP0000119. None are missing and none are extra.
- **Group:** `HC` 81 + `SCZ` 90, exactly Table S1's raw counts. `Diagnosis`: healthy 81, first-episode 49, relapse 41.
- **BMI:** present for all 171; **none is > 30**, so the GutMIND BMI filter removes no one. The 81 → 79 HC and 90 → 88 SCZ drops must come from the depth (< 10 M) or unclassified (> 30 %) filters, which get checked after QC/MetaPhlAn.
- Also available: age, gender (1 = male, 2 = female), height, weight, diet, smoking, serum metabolites.
- **Follow-up columns** (`BGI ID`/`BMI`/`Weight`/`Drugs`, cols 35–38) list 38 IDs. All 38 are exactly the CNGB samples titled `medication`, which confirms they are post-treatment follow-ups to exclude.
- The label map for Zhu_2020A will join on `sample_name` → `Group` (`HC` → Healthy, `SCZ` → SCZ).

**Zhu_2020B (BGISEQ, `CL1000…` names) isn't in this file.** The paper describes it as "an additional validation cohort consisting 45 patients taking antipsychotics and 45 controls (Supplementary Data 9)".

## 3c. Zhu_2020B labels — resolved (25 Oct 2026)

Source: Zhu 2020 Supplementary Data 9, saved as `data/supplements/Zhu2020_NatCommun_SuppData9.xlsx`. It holds one sheet with two stacked tables:
- **9a "Phenotypes of validation cohort"**: header on row 3, data in rows 4–93. The key is `Samples ID`, which equals the CNGB `sample_name` (`CL1000…_L0#_###`).
- **9b "Sequencing statistics"**: header on row 98. Columns are reads count, % human reads, high-quality reads and high-quality bases.

Findings:
- **90 rows, 90 unique IDs, all matching 1:1** to the 90 BGISEQ human cohort samples in CNP0000119. None are missing and none are extra. The mouse and donor samples aren't in the file, which confirms they should be excluded.
- **Group:** `HC` 45 + `SCZ` 45, exactly Table S1's raw counts. There's no first-episode/relapse split; the paper describes all patients as taking antipsychotics. A `BPRS` score is included.
- **BMI:**
  - 1 HC is over 30: `CL100089730_L02_558`, BMI 61.7 (160 cm, 158 kg). This may be a typo for 58 kg, but taken as recorded, the GutMIND filter drops it.
  - 2 SCZ have no BMI because weight is `NA` and the cell shows `#VALUE!`: `CL100095321_L02_508` and `CL100095322_L01_516`. These are kept, because NA isn't > 30.
- **Expected after the BMI filter:** HC 44, SCZ 45, against Table S1's 43 / 44. The remaining gap of −1 / −1 should come from the unclassified > 30 % filter. Depth can't explain it: per 9b, every sample has ≥ 76 M raw reads.
- Also available: age, gender, height, weight, waist/hip circumference, diet, smoking.

**Zhu A and Zhu B are now both fully labelled, with no overlap** (Illumina `wHAXPI…` vs BGISEQ `CL1000…` names, one run each).

## 3d. Thirion_2023A — what the paper says (25 Oct 2026)

Paper: Thirion et al., *Biol Psychiatry Glob Open Sci* 3:283–291 (2023). PMID 37124355, open access at PMC10140391. Read via the Europe PMC full-text XML.

- **Cohort:** 132 SCZ from the CHANGE lifestyle trial (Aarhus/Copenhagen, 2012–2014), recruited for *increased waist circumference*.
- **Healthy controls (n = 132):**
  - 74 age/sex-matched people from the Danish Study of Functional Disorders, which is PRJEB41787 (`VGDAN_…`, 107 public samples);
  - 58 from an unpublished NNF CBMR cohort, which is PRJEB41786 (`VG…`, 150 public samples).

  So the public control projects hold **more samples than the paper used** (257 vs 132).
- A third group of 132 metabolic-syndrome controls came from MetaHIT. It isn't part of GutMIND's SCZ dataset.
- **Table 1, mean BMI (SD):** SCZ 35 (6.2), HC 24 (3.8). Most SCZ patients therefore have BMI > 30, which fits GutMIND's 132 → 47 drop after the BMI filter.
- **Unexplained:** Table S1's raw HC count of 174 matches neither 132 (the paper) nor 257 (public).

**Supplementary files** (PMC gives no captions, only titles):

| File | Title | Size | URL | Likely content |
|---|---|---|---|---|
| `mmc1.pdf` | Supplement 1 | 1.5 MB | `https://pmc.ncbi.nlm.nih.gov/articles/instance/10140391/bin/mmc1.pdf` | Methods and "Table S1". The text cites Table S1 for cohort characteristics, ICD-10 diagnoses and contrasted MGSs, so probably **summary-level** |
| `mmc2.xlsx` | Supplement 2 | 673 KB | `https://pmc.ncbi.nlm.nih.gov/articles/instance/10140391/bin/mmc2.xlsx` | Not described in the text. The size fits per-sample data (e.g., samples × MGS, or per-sample metadata) — **best candidate** |
| `mmc3.xlsx` | Key Resources Table | 19 KB | `…/bin/mmc3.xlsx` | Reagents/software list, not useful |

**Supplement 2 checked (25 Oct 2026): no per-sample data.**
- **Download:** PMC served a bot-check page, so I fetched the same file from the publisher CDN (`https://ars.els-cdn.com/content/image/1-s2.0-S2667174322000143-mmc2.xlsx`, PII S2667174322000143). The MD5 `421871a0e11f7f190a9ef7c9d805d0c3` matches the PMC record, and the size is 689,434 bytes.
- **Sheets:** `Table S2. MGS` (600 species), `genus`, `family`, `phylum`, `Modules`. Each row is one taxon or module, with group means/SEM/prevalence for SCZ/HC/MS, Kruskal–Wallis and pairwise tests, Cliff's delta, symptom-score correlations, deconfounding results and RF variable importance.
- **No sample IDs anywhere:** there are no `Schizo_Change_`, `VG`, `VGDAN_`, `ERR` or `SAMEA` strings.
- **"BMI" appears only as `BMI_Y0`,** a confounder name in the deconfounding columns.
- I didn't keep it in `data/supplements/` because it isn't a label/metadata source.

Supplement 1 (`mmc1.pdf`) is described in the text as holding cohort-level characteristics and MGS lists, so it's unlikely to have per-sample BMI either. **Per-sample BMI for Thirion appears not to be published.** Options:
1. **Email the authors** (Thirion F / Le Chatelier E, INRAE MetaGenoPolis; or Speyer H for the CHANGE trial) for per-sample BMI, or for the GutMIND inclusion list via Feng Zhu.
2. **Fallback:** apply only the depth and unclassified filters to Thirion and report the gap against Table S1 (≈ 132 SCZ vs 47 expected), as FR-4 allows ("reported, not forced"). Thirion is in GutMIND's *platform-expanded* set (Ion Torrent), so it's secondary for the main high-quality analysis anyway.

## 4. PRD corrections found during discovery
- **FR-1:** in `sTable1.xlsx` the header is on **row 2** (row 1 is the title; there's no second title row). The parser will detect the header row by finding `StudyID` instead of hard-coding row 3.
- **Special case 5:** Zhu_2020B human samples are **paired-end** BGISEQ, not single-end.
- **Special case 3:** Thirion's controls live in **two separate ENA projects** (PRJEB41786, PRJEB41787). They aren't in PRJEB41217, so the study config needs a list of accessions per study, not a single one.
- **§6.4:** the full run needs about **3.5 TB** of transfer, not about 1 TB.
- **FR-6:** Zhu FASTQs are already host-removed by the submitters.
- **FR-4 step 4:** the depth threshold should be **10 M** reads, not 1 M (GutMIND Methods).
- **FR-4 / FR-7:** add the ">30 % unclassified (MetaPhlAn 4)" and "BMI > 30" filters. This makes MetaPhlAn 4 mandatory for count validation.
