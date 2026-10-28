# PRD: Schizophrenia gut-microbiome classifier (NEUROGUT, SCZ arm)

**Owner:** Yashvi B. Naik · **Date:** 28 Oct 2026 · **Code:** `scz-ml/` · **Run:** `scz-ml\run_all.bat`

## 1. Goal
Apply the method of the team's Parkinson's pipeline (milanAg08/NEUROGUT_CAPSTONE_PROJECT, branch `upload-pd-neurogut-files`, `PD_pipeline_v12.ipynb`) to the schizophrenia (SCZ) data we built in `scz-microbiome-data/`. Answer the same question as the PD arm: **does the gut microbiome separate SCZ from healthy controls, and does it generalise to a cohort the model never saw?**

## 2. Running it cheaply (the "batch file" approach)
Model training costs no Claude tokens. Tokens are spent only when Claude writes code or reads output, so the design keeps both small:
- All training runs as one Windows batch file, `run_all.bat`, with no notebook. It can run unattended (or by double-click) and logs to `scz-ml/logs/run_all.log`.
- Every stage writes small CSVs and one short `results/SUMMARY.md` (< 80 lines). Claude reads only that summary and the tail of the log, never notebooks, plots or per-fold dumps.
- Stages are cached (`results/*.done` markers), so rerunning `run_all.bat` after a crash resumes from where it stopped.
- `run_all.bat quick` runs a smoke test (2 folds, small grids, ~2 min) before the full run.

(The Anthropic "Message Batches API" is a different thing: it halves the price of LLM calls. This project makes no LLM calls, so it doesn't apply.)

## 3. Data (inputs, read-only)
| input | from |
|---|---|
| `scz-microbiome-data/results/scz_samples.tsv` | labels, study, `included` flag, age/sex/BMI |
| `scz-microbiome-data/results/profiles/by_study/*.species.tsv` (the 5 tables we retrieved: Li, Thirion, Xu, Zhu A, Zhu B) | species × sample, MetaPhlAn 3 (mpa_v30), full lineage per row; joined on lineage, absent = 0. No other abundance data is used. |

**Cohort:** `included == True`, 4 case-control studies, **704 samples (418 HC / 286 SCZ):**

| study | HC | SCZ | country | platform |
|---|---|---|---|---|
| Zhu 2020A | 81 | 90 | China | Illumina (full-depth cMD profiles) |
| Zhu 2020B | 44 | 45 | China | BGISEQ |
| Li 2023 | 36 | 19 | China | Illumina |
| Thirion 2023 | 257 | 132 | Denmark | Ion Torrent |

**Xu 2020 (38 SCZ, no controls) is left out of training.** A study with only one class would teach the model "Xu batch = SCZ". It is used only as an extra check: the share of Xu cases the frozen model calls SCZ (sensitivity).

## 4. Features (follows PD v12, adapted)
All are computed **inside each training fold** wherever they depend on labels or on the data distribution (no leakage):
1. **Species block (primary):** species with > 10 % prevalence in the training fold, CLR-transformed (pseudo-count 1e-6 on fractions). The PD arm found species better than genus.
2. **Genus block (comparison):** species summed to genus, same filter and CLR.
3. **Alpha diversity:** Shannon and Simpson on fractions (scale checked, PD v4 bug avoided).
4. **Bray-Curtis to the training fold's control centroid.**
5. **Co-occurrence network features:** Spearman, |ρ| > 0.3, BH q < 0.05 (relaxed to 0.2 / 0.10 if empty), on prevalence-filtered genera from the training fold only. Features: weighted degree, weighted eigenvector, hub load, top-5 community loads + "other". Edge counts are logged each fold.
6. **Taxonomy-informed UniFrac-style distance** to the training control centroid (lineage tree, unit branch lengths).

### 4a. Harmonising the studies (added 28 Oct 2026 at Yashvi's request: "train all the study batches on the same level and together")
The first run showed the studies are almost perfectly separable (study-prediction AUC 0.97), so a model can learn "which cohort" instead of "SCZ or not". Experiments E4/E5 put all four studies on one level before pooling them into one training set:
1. **Common detection floor:** abundances < 0.01 % are set to 0 and renormalised. Zhu A is full-depth; the others are 300–500 k-read subsamples, so they detect different rare species.
2. **Shared taxa only:** a species is kept if it is > 10 % prevalent in **at least half of the training studies**. Single-cohort taxa are pure batch markers.
3. **Per-study standardisation:** every feature (CLR and extras) is centred and scaled within its own study, as in the SIAMCAT / Wirbel et al. 2019 multi-cohort meta-analyses. This is **label-free**: it uses only each study's own samples, never labels, so a held-out study is standardised on itself exactly as a new cohort would be.

4. **Study × group balanced sample weights** in every model: each study, and Healthy/SCZ within each study, carries equal total weight. This way, cohort identity cannot stand in for the label.

Finding while building it: per-study standardisation does **not** hide which study a sample came from. Study-prediction AUC went 0.97 → 0.998, because a species absent in a sample takes a different standardised value in each study. That is why step 4 matters, and why leave-one-study-out (not the batch check) is the yardstick.

Limits:
- A cohort's case:control ratio shifts its mean slightly (Thirion is 2:1, the others ~1:1).
- A case-only cohort (Xu) cannot be scored by a harmonised model, because standardising it on itself removes the case signal. Its check is therefore reported as skipped.

The batch check is repeated on the harmonised features to show how much study signal is left.

**Frozen model choice (changed):** the ensemble with the best **leave-one-study-out** sample-weighted AUC. Generalising to unseen cohorts is the goal; internal AUC is inflated by study signal.

**Not used, with reasons (deviations from PD):**
- **Pathways:** HUMAnN was not run; only Zhu A has pathways, so this block would leak study identity.
- **Clinical covariates (age, sex, BMI, constipation, laxatives):** missing for Li and Thirion (half the cohort) and constipation is not recorded anywhere. The main model is **microbiome-only**, the same as the PD arm's frozen model. A covariate-only check (age + sex + BMI) is run on Zhu A + B, where they exist.
- **Oral-translocation block and the constipation interaction:** these are PD-specific (constipation). They are skipped.

## 5. Models
Same family as PD: **Random Forest, XGBoost, CatBoost, Elastic-Net logistic regression** and a **mean-probability ensemble** of RF + XGB + CatBoost. Feature selection is fold-local **Boruta → Elastic Net**, as in PD. Hyperparameters come from a small inner GridSearchCV (3-fold), using PD's grids.

## 6. Evaluation
| name | design | what it answers |
|---|---|---|
| **Internal** | 5-fold nested CV on all 704, stratified by study × group | discrimination when every study is seen in training (PD's "internal AUC") |
| **External (LOSO)** | leave-one-study-out over the 4 studies: train on 3, test on the 4th | generalisation to an unseen cohort, country and sequencer (PD's "external AUC") |
| **Frozen model** | ensemble refit on all 704 with the best feature set, saved to `models/` | the deliverable model; also scored on Xu (sensitivity) |
| **Batch check** | 5-fold AUC for predicting *study* (multi-class, macro OvR) from the same features | how much the study/batch signal outweighs the disease signal |
| **Covariate-only** | age + sex + BMI logistic regression on Zhu A + B | whether demographics alone separate the groups |

**Metrics:**
- ROC-AUC (primary), PR-AUC, balanced accuracy and F1 at 0.5;
- mean ± SD over folds;
- LOSO also reports a sample-weighted mean.

**Experiments, kept small for the time and token budget:**
- E1 genus + extras;
- E2 species only;
- E3 species + extras (network, UniFrac, diversity, Bray-Curtis).

Each of E1–E3 runs both internally and LOSO; this replaces PD's ablation chain. The best of E1–E3 by internal ensemble AUC becomes the frozen model.

## 7. Outputs (`scz-ml/results/`)
- `SUMMARY.md`: the only file Claude reads. It holds the tables of internal, LOSO, batch, covariate and Xu results, plus the top-20 frozen-model features.
- `cv_folds.csv`, `loso_folds.csv`: per fold × model × experiment.
- `selected_features.csv`: features chosen per fold, for stability.
- `network_stats.csv`: edges and communities per fold.
- `oof_predictions.csv`: out-of-fold probabilities, for later conformal or threshold work.
- `models/frozen_ensemble.joblib`: the frozen model, its feature list and the preprocessing state.

## 8. Acceptance
1. `run_all.bat` runs end-to-end with exit 0 from a clean checkout, and the `quick` mode runs in < 5 min.
2. No leakage: prevalence filter, CLR feature set, network, centroids and feature selection are all fit on training rows only (a unit test checks the network/centroid functions use train rows only).
3. Every number in SUMMARY.md is traceable to a CSV in `results/`.
4. Results are reported as they are; nothing is tuned to the test folds. Seeds are fixed (42).

## 9. Risks
- **Study confounding (high):**
  - Thirion is 55 % of samples, from a different country and sequencer;
  - its HC:SCZ ratio (2:1) differs from the others (~1:1);
  - so internal AUC can be inflated by the batch signal. LOSO and the batch check exist to expose this.
- **Depth differences:** Zhu A uses full-depth profiles; the others use 300–500 k-read subsamples. Rare species may be missed in subsamples. The CLR + prevalence filter dampens this, but it is noted as a limitation.
- **Runtime:** Boruta and CatBoost grids are the slow parts. Estimate: about 1–2 h on 12 cores.

## 10. Dependencies
- Already installed: Python 3.14, scikit-learn, xgboost, scipy, pandas, joblib.
- New, installed by `run_all.bat` via `pip install -r requirements.txt` if missing: **catboost, Boruta, networkx, statsmodels**.

### 4b. Further preprocessing (added 28 Oct 2026, E6–E8)
- **Multi-level features:** species + genus + family together, CLR within each rank.
- **Within-study percentile ranks** (E7), an alternative to z-scoring.
- **Cross-study consistent selection** replaces Boruta in E6–E8. On the training studies only, each feature gets a standardised SCZ–HC difference per study (z capped at 3). These are Stouffer-combined, and a feature is kept only if its direction agrees in every training study (all but one when there are 4). The 40 strongest are kept.

**Result:** E6 (multi-level, z-scored, consistent selection) is the most robust. Its ensemble scores leave-one-study-out mean 0.610, weighted 0.605, with the worst study at 0.567, compared with about 0.50 for E1–E5. Internal AUC is 0.717 (Random Forest 0.737).

Choosing the best of 8 experiments by LOSO is itself mildly optimistic, so read the LOSO numbers as an upper estimate.
