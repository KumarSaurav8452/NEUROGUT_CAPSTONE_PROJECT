"""Leakage and shape checks for the fold-local features (PRD §8.2)."""

import numpy as np
import pandas as pd

from sczml.data import to_genus
from sczml.features import FoldFeaturizer, clr, taxonomy_matrix

LIN = ["k__B|p__A|c__A|o__A|f__A|g__G1|s__S1", "k__B|p__A|c__A|o__A|f__A|g__G1|s__S2",
       "k__B|p__A|c__A|o__A|f__B|g__G2|s__S3", "k__B|p__C|c__C|o__C|f__C|g__G3|s__S4"]


def _frac(n=40, seed=0):
    rng = np.random.default_rng(seed)
    a = rng.dirichlet(np.ones(len(LIN)), size=n)
    a[a < 0.05] = 0
    return pd.DataFrame(a / a.sum(1, keepdims=True), columns=LIN, index=[f"s{i}" for i in range(n)])


def test_clr_rows_sum_to_zero_and_genus_sums():
    f = _frac()
    assert np.allclose(clr(f).sum(axis=1), 0)
    g = to_genus(f)
    assert g.shape[1] == 3 and np.allclose(g.sum(axis=1), 1)


def test_taxonomy_tree_shares_ancestors():
    m = taxonomy_matrix(LIN)
    assert m.shape[0] == 4 and (m[0] @ m[1]) == 5 and (m[0] @ m[3]) == 0  # S1/S2 share p..g; S4 nothing


def test_featurizer_ignores_test_rows():
    f = _frac()
    y = pd.Series([0, 1] * 20, index=f.index)
    tr, te = f.iloc[:30], f.iloc[30:]
    a = FoldFeaturizer(True).fit(tr, y.iloc[:30]).transform(te)
    te2 = te * 0 + np.eye(len(LIN))[[0] * len(te)]  # test rows changed completely
    b = FoldFeaturizer(True).fit(tr, y.iloc[:30]).transform(f.iloc[30:])
    assert a.equals(b)                              # same train rows -> same fitted state
    c = FoldFeaturizer(True).fit(tr, y.iloc[:30])
    c.transform(te2)                                # transforming other rows does not refit
    assert c.transform(te).equals(a)
    assert {"diversity_bray_to_control", "phylo_unifrac_to_control", "net_hub_load"} <= set(a.columns)


def test_harmonisation_is_label_free_and_levels_studies():
    from sczml.features import detection_floor, per_study_standardise
    f = detection_floor(_frac(), floor=0.1)
    assert ((f == 0) | (f >= 0.1)).all().all() and np.allclose(f.sum(axis=1), 1)
    x = pd.DataFrame({"a": [1.0, 2, 3, 10, 20, 30]})
    z = per_study_standardise(x, pd.Series(list("AAABBB")))
    assert np.allclose(z.groupby([0, 0, 0, 1, 1, 1]).mean(), 0) and np.allclose(z["a"][:3], z["a"][3:])


def test_cross_study_prevalence_drops_single_cohort_taxa():
    f = _frac()
    f.iloc[:20, 3] = 0                                   # S4 absent in study A
    f = f.div(f.sum(axis=1), axis=0)
    study = pd.Series(["A"] * 20 + ["B"] * 20, index=f.index)
    y = pd.Series([0, 1] * 20, index=f.index)
    fz = FoldFeaturizer(False).fit(f, y, study)
    assert LIN[3] in fz.taxa                             # present in 1 of 2 studies = half: kept
    study3 = pd.Series(["A"] * 14 + ["B"] * 13 + ["C"] * 13, index=f.index)
    f.iloc[:27, 3] = 0
    assert LIN[3] not in FoldFeaturizer(False).fit(f, y, study3).taxa  # 1 of 3 < half: dropped


def test_balanced_weights_equal_per_cell():
    from sczml.models import balanced_weights
    y = pd.Series([0, 0, 0, 0, 1, 1, 0, 1])
    s = pd.Series(list("AAAAAABB"))
    w = pd.Series(balanced_weights(y, s))
    cells = w.groupby(s.values + y.astype(str).values).sum()
    assert np.allclose(cells, cells.iloc[0]) and np.isclose(w.mean(), 1)


def test_consistent_selection_prefers_replicated_signal():
    from sczml.models import select_consistent
    rng = np.random.default_rng(1)
    n = 90
    study = pd.Series(np.repeat(["A", "B", "C"], 30))
    y = pd.Series(np.tile([0, 1], 45))
    x = pd.DataFrame(rng.normal(size=(n, 6)), columns=[f"f{i}" for i in range(6)])
    x["f0"] += 1.5 * y                                    # replicates in every study
    x.loc[study == "A", "f1"] += 4 * y[study == "A"]      # huge, but only in study A
    picked = select_consistent(x, y, study, n_max=2)
    assert picked[0] == "f0" and "f1" not in picked


def test_multi_level_and_per_rank_clr():
    from sczml.data import multi_level
    m = multi_level(_frac())
    assert m.shape[1] == 4 + 3 + 3 and np.allclose(clr(m).sum(axis=1), 0)


def test_extras_summary_metrics_match_confusion_matrix():
    """SVM/SHAP report: accuracy, precision, recall and F1 come from one Youden-threshold confusion matrix."""
    from sczml.extras import summarise
    y = pd.Series([0, 0, 0, 0, 1, 1, 1, 1])
    score = np.array([0.1, 0.2, 0.3, 0.8, 0.4, 0.7, 0.9, 0.95])
    s = summarise(y, [0.9, 0.7], score, np.array(["a", "a", "b", "b", "a", "a", "b", "b"]))
    c = s["confusion"]
    assert c["tn"] + c["fp"] + c["fn"] + c["tp"] == len(y)
    assert s["accuracy"] == round((c["tp"] + c["tn"]) / len(y), 3)
    assert s["recall"] == round(c["tp"] / (c["tp"] + c["fn"]), 3)
    assert s["roc_auc"] == 0.8
    lo, hi = s["roc_auc_ci95"]
    assert 0.0 <= lo <= hi <= 1.0


def test_auc_ci_brackets_the_mean_fold_auc():
    """The CI is for the reported number (mean of per-fold AUCs), so it must contain it."""
    from sklearn.metrics import roc_auc_score
    from sczml.extras import auc_ci
    rng = np.random.default_rng(0)
    y = np.tile([0, 1], 150)
    fold = np.repeat(["a", "b", "c"], 100)
    score = y * 0.6 + rng.normal(size=300) + np.repeat([0.0, 5.0, -5.0], 100)  # folds on very different scales
    mean_auc = np.mean([roc_auc_score(y[fold == f], score[fold == f]) for f in "abc"])
    lo, hi = auc_ci(y, score, fold)
    assert lo <= mean_auc <= hi
