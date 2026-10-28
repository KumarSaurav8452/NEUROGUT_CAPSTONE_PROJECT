"""Run every stage of the PRD and write results/SUMMARY.md.

python -m sczml.run            full run  -> results/
python -m sczml.run --quick    smoke test (2 folds, tiny grids) -> results_quick/

Each (experiment, design) is cached in results/parts/; delete a part to recompute it.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from sczml import data, models
from sczml.features import FoldFeaturizer, detection_floor, per_study_standardise, rank_within_study

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = {  # name: (taxonomic level, extras, harmonise studies: False/"z"/"rank"[, selection])
    "E1 genus+extras": ("genus", True, False),
    "E2 species": ("species", False, False),
    "E3 species+extras": ("species", True, False),
    # All studies brought to one level, then trained together: common detection floor, taxa shared by
    # >= half the training studies, every feature centred and scaled within its study (label-free),
    # and study x group balanced sample weights so cohort identity cannot stand in for the label.
    "E4 species harmonised": ("species", False, "z"),
    "E5 species+extras harmonised": ("species", True, "z"),
    # Further preprocessing (28 Oct 2026): species+genus+family together, within-study percentile ranks,
    # and cross-study consistent feature selection (meta-analysis on training studies) instead of Boruta.
    "E6 multi-level harmonised consistent": ("multi", False, "z", "meta"),
    "E7 multi-level rank consistent": ("multi", False, "rank", "meta"),
    "E8 genus harmonised consistent": ("genus", False, "z", "meta"),
}
ENS = "Ensemble (mean RF+XGB+Cat)"


def weights(exp, meta):
    """Harmonised experiments train with study x group balanced sample weights."""
    return models.balanced_weights(meta["y"], meta["study_id"]) if EXPERIMENTS[exp][2] else None


def featurise(exp, frac, meta, tr, te):
    """Fit on rows tr, return (x_tr, x_te, featurizer)."""
    _, extras, harmonise = EXPERIMENTS[exp][:3]
    y, study = meta["y"], meta["study_id"]
    if harmonise:
        frac = detection_floor(frac)
    fz = FoldFeaturizer(extras).fit(frac.iloc[tr], y.iloc[tr], study.iloc[tr] if harmonise else None)
    x_tr, x_te = fz.transform(frac.iloc[tr]), fz.transform(frac.iloc[te])
    if harmonise:
        norm = rank_within_study if harmonise == "rank" else per_study_standardise
        both = norm(pd.concat([x_tr, x_te]), pd.concat([study.iloc[tr], study.iloc[te]]))
        x_tr, x_te = both.iloc[: len(tr)], both.iloc[len(tr):]
    return x_tr, x_te, fz


def select(exp, x, meta, grids):
    if len(EXPERIMENTS[exp]) > 3 and EXPERIMENTS[exp][3] == "meta":
        return models.select_consistent(x, meta["y"], meta["study_id"])
    return models.select_features(x, meta["y"], grids)


T0 = time.time()


def log(msg: str):
    print(f"[{time.time() - T0:7.0f}s] {msg}", flush=True)


def metrics(y, p) -> dict:
    pred = (p >= 0.5).astype(int)
    return {"roc_auc": roc_auc_score(y, p), "pr_auc": average_precision_score(y, p),
            "bal_acc": balanced_accuracy_score(y, pred), "f1": f1_score(y, pred, zero_division=0)}


def splits(meta: pd.DataFrame, design: str, n_folds: int):
    if design == "internal":
        strata = meta["study_id"] + "/" + meta["y"].astype(str)
        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=models.SEED)
        for k, (tr, te) in enumerate(cv.split(meta, strata), 1):
            yield str(k), tr, te
    else:  # leave one study out
        for study in sorted(meta["study_id"].unique()):
            te = np.flatnonzero(meta["study_id"].values == study)
            yield study, np.flatnonzero(meta["study_id"].values != study), te


def run_design(exp, design, meta, tables, grids, n_folds, parts: Path):
    out = parts / f"{exp.split()[0]}_{design}.pkl"
    if out.exists():
        log(f"{exp} / {design}: cached")
        return joblib.load(out)
    level, extras, _ = EXPERIMENTS[exp][:3]
    frac = tables[level]
    rows, oof, sel, net = [], [], [], []
    for fold, tr, te in splits(meta, design, n_folds):
        y_tr, y_te = meta["y"].iloc[tr], meta["y"].iloc[te]
        x_tr, x_te, fz = featurise(exp, frac, meta, tr, te)
        feats = select(exp, x_tr, meta.iloc[tr], grids)
        fitted = models.fit_models(x_tr[feats], y_tr, grids, weights(exp, meta.iloc[tr]))
        probs = models.predict(fitted, x_te[feats])
        for name, p in probs.items():
            rows.append({"experiment": exp, "design": design, "fold": fold, "model": name, "n_test": len(te),
                         "n_features": len(feats), **metrics(y_te, p)})
        oof.append(pd.DataFrame({"sample_id": meta.index[te], "experiment": exp, "design": design, "fold": fold,
                                 "y": y_te.values, **probs}))
        sel.append({"experiment": exp, "design": design, "fold": fold, "n": len(feats), "features": ";".join(feats)})
        if extras:
            net.append({"experiment": exp, "design": design, "fold": fold, **fz.stats()})
        ens = rows[-1]
        log(f"{exp} / {design} / fold {fold}: {len(feats)} features, ensemble AUC {ens['roc_auc']:.3f}"
            + (f", network {fz.stats()['edges']} edges" if extras else ""))
    res = {"folds": pd.DataFrame(rows), "oof": pd.concat(oof), "selected": pd.DataFrame(sel), "network": pd.DataFrame(net)}
    joblib.dump(res, out)
    return res


def batch_check(meta, frac, n_folds, exp="E2 species"):
    """How well do the same features predict the *study*? (macro one-vs-rest AUC)"""
    study = meta["study_id"].values
    cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=models.SEED)
    prob = np.zeros((len(meta), len(np.unique(study))))
    for tr, te in cv.split(meta, study):
        x_tr, x_te, _ = featurise(exp, frac, meta, tr, te)
        rf = RandomForestClassifier(n_estimators=300, random_state=models.SEED, n_jobs=-1)
        rf.fit(x_tr, study[tr])
        prob[te] = rf.predict_proba(x_te)
    return roc_auc_score(study, prob, multi_class="ovr", average="macro")


def covariate_only(meta, n_folds):
    sub = meta[meta["study_id"].isin(["Zhu_2020A_SCZ", "Zhu_2020B_SCZ"])].copy()
    x = pd.DataFrame({"age": sub["age"], "sex": (sub["sex"] == "female").astype(float).where(sub["sex"].notna()),
                      "bmi": sub["bmi"]})
    pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=1000))
    cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=models.SEED)
    p = cross_val_predict(pipe, x, sub["y"], cv=cv, method="predict_proba")[:, 1]
    return len(sub), roc_auc_score(sub["y"], p)


def freeze(exp, meta, tables, xu_tables, grids, out_dir: Path):
    level, _, harmonise = EXPERIMENTS[exp][:3]
    everything = np.arange(len(meta))
    x, _, fz = featurise(exp, tables[level], meta, everything, everything[:0])
    feats = select(exp, x, meta, grids)
    fitted = models.fit_models(x[feats], meta["y"], grids, weights(exp, meta))
    joblib.dump({"experiment": exp, "harmonised": harmonise, "featurizer": fz, "features": feats, "models": fitted},
                out_dir / "models" / "frozen_ensemble.joblib")
    xu = None
    if harmonise:  # a case-only cohort standardised on itself loses its case signal: check not meaningful
        xu = {"skipped": "harmonised model standardises each cohort on itself; a case-only cohort has no controls"}
    elif len(xu_tables[level]):
        p = models.predict(fitted, fz.transform(xu_tables[level])[feats])["Ensemble (mean RF+XGB+Cat)"]
        xu = {"n": len(p), "called_scz": float((p >= 0.5).mean()), "mean_prob": float(p.mean())}
    imp = pd.Series(fitted["Random Forest"].feature_importances_, index=feats)
    scz, hc = x.loc[meta["y"] == 1, feats].mean(), x.loc[meta["y"] == 0, feats].mean()
    top = pd.DataFrame({"rf_importance": imp, "higher_in": np.where(scz > hc, "SCZ", "Healthy")}) \
        .sort_values("rf_importance", ascending=False).head(20)
    return feats, xu, top


def table(df: pd.DataFrame, floatfmt="{:.3f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(floatfmt.format(v) if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    grids, n_folds = (models.QUICK, 2) if a.quick else (models.FULL, 5)
    out = ROOT / ("results_quick" if a.quick else "results")
    for d in ("parts", "models"):
        (out / d).mkdir(parents=True, exist_ok=True)

    meta, frac, xu_meta, xu_frac = data.load()
    if a.quick:  # small, still covering every study
        meta = meta.loc[meta.groupby(["study_id", "y"]).sample(frac=1, random_state=1)
                        .groupby(["study_id", "y"]).head(15).index]
        frac = frac.loc[meta.index]
    tables = {"species": frac, "genus": data.to_genus(frac), "multi": data.multi_level(frac)}
    xu_tables = {"species": xu_frac, "genus": data.to_genus(xu_frac), "multi": data.multi_level(xu_frac)}
    log(f"cohort {len(meta)} ({int((meta.y == 0).sum())} HC / {int(meta.y.sum())} SCZ); "
        f"{tables['species'].shape[1]} species, {tables['genus'].shape[1]} genera; Xu case-only {len(xu_meta)}")

    results = [run_design(e, d, meta, tables, grids, n_folds, out / "parts")
               for d in ("internal", "loso") for e in EXPERIMENTS]
    folds = pd.concat([r["folds"] for r in results])
    folds[folds.design == "internal"].to_csv(out / "cv_folds.csv", index=False)
    folds[folds.design == "loso"].to_csv(out / "loso_folds.csv", index=False)
    pd.concat([r["oof"] for r in results]).to_csv(out / "oof_predictions.csv", index=False)
    pd.concat([r["selected"] for r in results]).to_csv(out / "selected_features.csv", index=False)
    pd.concat([r["network"] for r in results]).to_csv(out / "network_stats.csv", index=False)

    agg = folds.groupby(["design", "experiment", "model"]).agg(
        roc_auc=("roc_auc", "mean"), roc_sd=("roc_auc", "std"), pr_auc=("pr_auc", "mean"),
        bal_acc=("bal_acc", "mean"), f1=("f1", "mean"), n_features=("n_features", "mean")).reset_index()
    internal = agg[agg.design == "internal"].drop(columns="design")
    loso = folds[folds.design == "loso"]
    loso_study = loso.pivot_table(index=["experiment", "model"], columns="fold", values="roc_auc").reset_index()
    w = loso.groupby(["experiment", "model"]).apply(lambda g: np.average(g.roc_auc, weights=g.n_test), include_groups=False)
    loso_study["weighted_mean"] = loso_study.set_index(["experiment", "model"]).index.map(w)
    loso_study["mean"] = loso.groupby(["experiment", "model"])["roc_auc"].mean().reindex(
        loso_study.set_index(["experiment", "model"]).index).values

    # Frozen model = best ensemble on unseen studies (sample-weighted LOSO AUC): generalisation is the goal.
    best = loso_study[loso_study.model == ENS].sort_values("weighted_mean").iloc[-1]["experiment"]
    log("batch check / covariate-only / frozen model")
    batch_auc = batch_check(meta, frac, n_folds)
    batch_auc_h = batch_check(meta, frac, n_folds, "E4 species harmonised")
    n_cov, cov_auc = covariate_only(meta, n_folds)
    feats, xu, top = freeze(best, meta, tables, xu_tables, grids, out)
    top.index = [i.replace("taxon__", "") for i in top.index]
    pd.DataFrame({"feature": feats}).to_csv(out / "models" / "frozen_features.csv", index=False)

    net = pd.concat([r["network"] for r in results])
    md = [
        "# SCZ classifier: summary" + (" (QUICK SMOKE TEST, not results)" if a.quick else ""),
        f"Generated {time.strftime('%d %b %Y %H:%M')} by `python -m sczml.run`; spec `../PRD_SCZ_ML_Training.md`.",
        f"Cohort: {len(meta)} samples ({int((meta.y == 0).sum())} HC / {int(meta.y.sum())} SCZ) from "
        f"{meta.study_id.nunique()} studies; microbiome-only features. Xu 2020 (case-only) held out.",
        "", f"## Internal: {n_folds}-fold nested CV, stratified by study x group", "",
        table(internal.sort_values(["experiment", "model"])),
        "", "## External: leave-one-study-out ROC-AUC (column = held-out study)", "",
        table(loso_study.sort_values(["experiment", "model"])),
        "", "## Checks", "",
        f"- **Batch signal:** predicting the *study* from species CLR gives macro AUC **{batch_auc:.3f}** "
        f"(1.0 = studies perfectly separable); after harmonisation (E4 features) **{batch_auc_h:.3f}**.",
        f"- **Covariate-only** (age + sex + BMI, Zhu A + B, n={n_cov}): AUC **{cov_auc:.3f}**.",
        f"- **Network:** {int((net.edges > 0).sum())}/{len(net)} folds had edges "
        f"(median {net.edges.median():.0f}; relaxed threshold in {int(net.relaxed.sum())}).",
        f"- **Frozen model** = {best} ensemble (best leave-one-study-out weighted AUC), {len(feats)} features, "
        f"refit on all {len(meta)}.",
    ]
    if xu and "skipped" in xu:
        md.append(f"- **Xu 2020 case-only check:** skipped: {xu['skipped']}.")
    elif xu:
        md.append(f"- **Xu 2020 case-only check:** frozen model calls {xu['called_scz']:.0%} of {xu['n']} SCZ "
                  f"cases SCZ (mean probability {xu['mean_prob']:.2f}).")
    md += ["", "## Frozen model: top 20 features (RF importance)", "", table(top.reset_index(names="feature"), "{:.4f}")]
    (out / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log(f"done -> {out / 'SUMMARY.md'}")


if __name__ == "__main__":
    sys.exit(main())
