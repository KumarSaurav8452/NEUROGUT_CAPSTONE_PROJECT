# SCZ classifier: summary
Generated 28 Oct 2026 23:35 by `python -m sczml.run`; spec `../PRD_SCZ_ML_Training.md`.
Cohort: 704 samples (418 HC / 286 SCZ) from 4 studies; microbiome-only features. Xu 2020 (case-only) held out.

## Internal: 5-fold nested CV, stratified by study x group

| experiment | model | roc_auc | roc_sd | pr_auc | bal_acc | f1 | n_features |
|---|---|---|---|---|---|---|---|
| E1 genus+extras | CatBoost | 0.706 | 0.047 | 0.639 | 0.642 | 0.532 | 10.000 |
| E1 genus+extras | ElasticNet | 0.714 | 0.041 | 0.652 | 0.661 | 0.603 | 10.000 |
| E1 genus+extras | Ensemble (mean RF+XGB+Cat) | 0.703 | 0.045 | 0.639 | 0.652 | 0.548 | 10.000 |
| E1 genus+extras | Random Forest | 0.687 | 0.040 | 0.621 | 0.652 | 0.557 | 10.000 |
| E1 genus+extras | XGBoost | 0.700 | 0.034 | 0.626 | 0.615 | 0.454 | 10.000 |
| E2 species | CatBoost | 0.728 | 0.038 | 0.670 | 0.655 | 0.541 | 15.200 |
| E2 species | ElasticNet | 0.701 | 0.039 | 0.629 | 0.645 | 0.587 | 15.200 |
| E2 species | Ensemble (mean RF+XGB+Cat) | 0.723 | 0.031 | 0.653 | 0.660 | 0.568 | 15.200 |
| E2 species | Random Forest | 0.716 | 0.033 | 0.634 | 0.651 | 0.561 | 15.200 |
| E2 species | XGBoost | 0.713 | 0.026 | 0.640 | 0.662 | 0.572 | 15.200 |
| E3 species+extras | CatBoost | 0.719 | 0.022 | 0.649 | 0.663 | 0.576 | 16.000 |
| E3 species+extras | ElasticNet | 0.700 | 0.034 | 0.630 | 0.639 | 0.581 | 16.000 |
| E3 species+extras | Ensemble (mean RF+XGB+Cat) | 0.720 | 0.026 | 0.653 | 0.650 | 0.560 | 16.000 |
| E3 species+extras | Random Forest | 0.723 | 0.025 | 0.664 | 0.663 | 0.582 | 16.000 |
| E3 species+extras | XGBoost | 0.701 | 0.031 | 0.627 | 0.642 | 0.549 | 16.000 |
| E4 species harmonised | CatBoost | 0.693 | 0.027 | 0.645 | 0.639 | 0.557 | 13.800 |
| E4 species harmonised | ElasticNet | 0.668 | 0.045 | 0.608 | 0.621 | 0.568 | 13.800 |
| E4 species harmonised | Ensemble (mean RF+XGB+Cat) | 0.694 | 0.021 | 0.646 | 0.636 | 0.546 | 13.800 |
| E4 species harmonised | Random Forest | 0.707 | 0.026 | 0.650 | 0.639 | 0.535 | 13.800 |
| E4 species harmonised | XGBoost | 0.669 | 0.028 | 0.624 | 0.625 | 0.543 | 13.800 |
| E5 species+extras harmonised | CatBoost | 0.697 | 0.032 | 0.634 | 0.651 | 0.572 | 15.200 |
| E5 species+extras harmonised | ElasticNet | 0.666 | 0.050 | 0.606 | 0.618 | 0.565 | 15.200 |
| E5 species+extras harmonised | Ensemble (mean RF+XGB+Cat) | 0.700 | 0.030 | 0.651 | 0.650 | 0.567 | 15.200 |
| E5 species+extras harmonised | Random Forest | 0.705 | 0.037 | 0.647 | 0.655 | 0.561 | 15.200 |
| E5 species+extras harmonised | XGBoost | 0.680 | 0.027 | 0.641 | 0.641 | 0.564 | 15.200 |
| E6 multi-level harmonised consistent | CatBoost | 0.705 | 0.058 | 0.662 | 0.659 | 0.582 | 37.600 |
| E6 multi-level harmonised consistent | ElasticNet | 0.673 | 0.053 | 0.605 | 0.621 | 0.564 | 37.600 |
| E6 multi-level harmonised consistent | Ensemble (mean RF+XGB+Cat) | 0.717 | 0.056 | 0.681 | 0.668 | 0.585 | 37.600 |
| E6 multi-level harmonised consistent | Random Forest | 0.737 | 0.050 | 0.685 | 0.666 | 0.560 | 37.600 |
| E6 multi-level harmonised consistent | XGBoost | 0.691 | 0.046 | 0.663 | 0.654 | 0.577 | 37.600 |
| E7 multi-level rank consistent | CatBoost | 0.670 | 0.051 | 0.634 | 0.646 | 0.571 | 35.800 |
| E7 multi-level rank consistent | ElasticNet | 0.658 | 0.043 | 0.595 | 0.617 | 0.558 | 35.800 |
| E7 multi-level rank consistent | Ensemble (mean RF+XGB+Cat) | 0.680 | 0.055 | 0.657 | 0.637 | 0.551 | 35.800 |
| E7 multi-level rank consistent | Random Forest | 0.684 | 0.050 | 0.648 | 0.648 | 0.526 | 35.800 |
| E7 multi-level rank consistent | XGBoost | 0.671 | 0.061 | 0.646 | 0.642 | 0.569 | 35.800 |
| E8 genus harmonised consistent | CatBoost | 0.675 | 0.043 | 0.630 | 0.621 | 0.546 | 11.400 |
| E8 genus harmonised consistent | ElasticNet | 0.658 | 0.048 | 0.608 | 0.604 | 0.535 | 11.400 |
| E8 genus harmonised consistent | Ensemble (mean RF+XGB+Cat) | 0.681 | 0.058 | 0.647 | 0.628 | 0.542 | 11.400 |
| E8 genus harmonised consistent | Random Forest | 0.697 | 0.039 | 0.651 | 0.648 | 0.548 | 11.400 |
| E8 genus harmonised consistent | XGBoost | 0.655 | 0.069 | 0.596 | 0.630 | 0.554 | 11.400 |

## External: leave-one-study-out ROC-AUC (column = held-out study)

| experiment | model | Li_2023_SCZ | Thirion_2023A_SCZ | Zhu_2020A_SCZ | Zhu_2020B_SCZ | weighted_mean | mean |
|---|---|---|---|---|---|---|---|
| E1 genus+extras | CatBoost | 0.503 | 0.632 | 0.518 | 0.683 | 0.600 | 0.584 |
| E1 genus+extras | ElasticNet | 0.518 | 0.529 | 0.500 | 0.735 | 0.547 | 0.570 |
| E1 genus+extras | Ensemble (mean RF+XGB+Cat) | 0.507 | 0.630 | 0.529 | 0.666 | 0.601 | 0.583 |
| E1 genus+extras | Random Forest | 0.503 | 0.609 | 0.540 | 0.655 | 0.590 | 0.577 |
| E1 genus+extras | XGBoost | 0.493 | 0.626 | 0.526 | 0.665 | 0.596 | 0.577 |
| E2 species | CatBoost | 0.570 | 0.538 | 0.449 | 0.701 | 0.539 | 0.564 |
| E2 species | ElasticNet | 0.541 | 0.541 | 0.437 | 0.713 | 0.538 | 0.558 |
| E2 species | Ensemble (mean RF+XGB+Cat) | 0.545 | 0.536 | 0.448 | 0.650 | 0.530 | 0.545 |
| E2 species | Random Forest | 0.566 | 0.526 | 0.415 | 0.659 | 0.519 | 0.541 |
| E2 species | XGBoost | 0.513 | 0.539 | 0.491 | 0.598 | 0.533 | 0.535 |
| E3 species+extras | CatBoost | 0.516 | 0.539 | 0.453 | 0.720 | 0.539 | 0.557 |
| E3 species+extras | ElasticNet | 0.523 | 0.525 | 0.435 | 0.719 | 0.528 | 0.551 |
| E3 species+extras | Ensemble (mean RF+XGB+Cat) | 0.520 | 0.539 | 0.464 | 0.654 | 0.534 | 0.544 |
| E3 species+extras | Random Forest | 0.550 | 0.535 | 0.444 | 0.674 | 0.532 | 0.551 |
| E3 species+extras | XGBoost | 0.487 | 0.536 | 0.485 | 0.582 | 0.525 | 0.522 |
| E4 species harmonised | CatBoost | 0.614 | 0.615 | 0.477 | 0.567 | 0.576 | 0.568 |
| E4 species harmonised | ElasticNet | 0.575 | 0.657 | 0.472 | 0.653 | 0.605 | 0.589 |
| E4 species harmonised | Ensemble (mean RF+XGB+Cat) | 0.646 | 0.606 | 0.485 | 0.593 | 0.578 | 0.583 |
| E4 species harmonised | Random Forest | 0.670 | 0.619 | 0.524 | 0.621 | 0.600 | 0.608 |
| E4 species harmonised | XGBoost | 0.614 | 0.585 | 0.471 | 0.591 | 0.560 | 0.565 |
| E5 species+extras harmonised | CatBoost | 0.706 | 0.572 | 0.477 | 0.579 | 0.560 | 0.584 |
| E5 species+extras harmonised | ElasticNet | 0.577 | 0.662 | 0.472 | 0.681 | 0.612 | 0.598 |
| E5 species+extras harmonised | Ensemble (mean RF+XGB+Cat) | 0.640 | 0.560 | 0.485 | 0.581 | 0.551 | 0.567 |
| E5 species+extras harmonised | Random Forest | 0.639 | 0.562 | 0.524 | 0.588 | 0.562 | 0.578 |
| E5 species+extras harmonised | XGBoost | 0.573 | 0.540 | 0.471 | 0.586 | 0.532 | 0.543 |
| E6 multi-level harmonised consistent | CatBoost | 0.583 | 0.570 | 0.580 | 0.702 | 0.590 | 0.609 |
| E6 multi-level harmonised consistent | ElasticNet | 0.576 | 0.609 | 0.558 | 0.670 | 0.602 | 0.603 |
| E6 multi-level harmonised consistent | Ensemble (mean RF+XGB+Cat) | 0.567 | 0.599 | 0.588 | 0.686 | 0.605 | 0.610 |
| E6 multi-level harmonised consistent | Random Forest | 0.560 | 0.601 | 0.583 | 0.663 | 0.601 | 0.602 |
| E6 multi-level harmonised consistent | XGBoost | 0.531 | 0.609 | 0.564 | 0.559 | 0.586 | 0.566 |
| E7 multi-level rank consistent | CatBoost | 0.610 | 0.503 | 0.508 | 0.592 | 0.524 | 0.553 |
| E7 multi-level rank consistent | ElasticNet | 0.567 | 0.554 | 0.491 | 0.688 | 0.556 | 0.575 |
| E7 multi-level rank consistent | Ensemble (mean RF+XGB+Cat) | 0.654 | 0.500 | 0.505 | 0.618 | 0.528 | 0.569 |
| E7 multi-level rank consistent | Random Forest | 0.639 | 0.499 | 0.508 | 0.637 | 0.530 | 0.571 |
| E7 multi-level rank consistent | XGBoost | 0.654 | 0.491 | 0.492 | 0.598 | 0.518 | 0.559 |
| E8 genus harmonised consistent | CatBoost | 0.510 | 0.528 | 0.508 | 0.513 | 0.520 | 0.515 |
| E8 genus harmonised consistent | ElasticNet | 0.471 | 0.537 | 0.468 | 0.617 | 0.525 | 0.523 |
| E8 genus harmonised consistent | Ensemble (mean RF+XGB+Cat) | 0.490 | 0.572 | 0.507 | 0.537 | 0.545 | 0.526 |
| E8 genus harmonised consistent | Random Forest | 0.466 | 0.574 | 0.524 | 0.571 | 0.553 | 0.534 |
| E8 genus harmonised consistent | XGBoost | 0.491 | 0.585 | 0.494 | 0.548 | 0.551 | 0.530 |

## Checks

- **Batch signal:** predicting the *study* from species CLR gives macro AUC **0.972** (1.0 = studies perfectly separable); after harmonisation (E4 features) **0.998**.
- **Covariate-only** (age + sex + BMI, Zhu A + B, n=260): AUC **0.663**.
- **Network:** 27/27 folds had edges (median 455; relaxed threshold in 0).
- **Frozen model** = E6 multi-level harmonised consistent ensemble (best leave-one-study-out weighted AUC), 40 features, refit on all 704.
- **Xu 2020 case-only check:** skipped: harmonised model standardises each cohort on itself; a case-only cohort has no controls.

## Frozen model: top 20 features (RF importance)

| feature | rf_importance | higher_in |
|---|---|---|
| f__Coriobacteriaceae | 0.0435 | SCZ |
| g__Collinsella | 0.0398 | SCZ |
| s__Collinsella_aerofaciens | 0.0374 | SCZ |
| s__Bacteroides_xylanisolvens | 0.0336 | Healthy |
| s__Bacteroides_stercoris | 0.0327 | SCZ |
| s__Bacteroides_vulgatus | 0.0319 | Healthy |
| g__Blautia | 0.0305 | SCZ |
| g__Bifidobacterium | 0.0281 | SCZ |
| g__Dorea | 0.0279 | SCZ |
| s__Bifidobacterium_longum | 0.0276 | SCZ |
| s__Firmicutes_bacterium_CAG_83 | 0.0272 | SCZ |
| s__Bacteroides_plebeius | 0.0272 | SCZ |
| s__Bacteroides_uniformis | 0.0269 | Healthy |
| s__Ruminococcus_torques | 0.0263 | SCZ |
| s__Eubacterium_eligens | 0.0261 | Healthy |
| f__Bacteroidaceae | 0.0255 | Healthy |
| s__Dialister_sp_CAG_357 | 0.0255 | Healthy |
| s__Ruthenibacterium_lactatiformans | 0.0243 | SCZ |
| f__Tannerellaceae | 0.0243 | SCZ |
| s__Bacteroides_finegoldii | 0.0236 | Healthy |
