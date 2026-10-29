"""Build the static JSON behind website v2 from the research outputs (PRD_Website_v2.md, FR-7).

python scripts/export_v2_data.py   ->  neurogut-frontend/src/data/v2/{scz,pd}.json
"""

import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "research" / "Neurogut schizophrenia"
SCZ_ML = RES / "scz-ml" / "results"
SCZ_DATA = RES / "scz-microbiome-data" / "results"
PD = RES / "external_repos" / "pd_repo" / "data" / "processed"
EXTRAS = SCZ_ML / "extras"  # SVM baseline + SHAP, from python -m sczml.extras
OUT = ROOT / "neurogut-frontend" / "src" / "data" / "v2"
FINAL = "E6 multi-level harmonised consistent"
ENS = "Ensemble (mean RF+XGB+Cat)"
METRICS = ["roc_auc", "pr_auc", "bal_acc", "f1"]


def r(x, n=3):
    return None if pd.isna(x) else round(float(x), n)


def per_model(df, metrics):
    g = df.groupby("model")[metrics].agg(["mean", "std"])
    return [{"model": m, **{f"{k}": r(g.loc[m, (k, "mean")]) for k in metrics},
             **{f"{k}_sd": r(g.loc[m, (k, "std")]) for k in metrics}} for m in g.index]


def auc_ci(y, score, fold, n_boot=1000, seed=42):
    """95% bootstrap CI of the mean fold ROC-AUC (the number shown): resample cases and controls within each
    fold, recompute every fold's AUC, average. Scores are never pooled across folds (different models)."""
    y, score, fold = np.asarray(y), np.asarray(score), np.asarray(fold)
    groups = [(np.flatnonzero((fold == f) & (y == 1)), np.flatnonzero((fold == f) & (y == 0))) for f in pd.unique(fold)]
    rng = np.random.default_rng(seed)
    aucs = [np.mean([roc_auc_score(y[i], score[i]) for i in
                     (np.concatenate([rng.choice(p, len(p)), rng.choice(n, len(n))]) for p, n in groups)])
            for _ in range(n_boot)]
    return [r(np.percentile(aucs, 2.5)), r(np.percentile(aucs, 97.5))]


def with_ci(rows, oof):
    """Attach the bootstrap CI to each per-model row, from that model's pooled out-of-fold predictions."""
    for row in rows:
        if row["model"] in oof.columns:
            row["roc_auc_ci95"] = auc_ci(oof.y, oof[row["model"]], oof.fold)
    return rows


def summary_lines():
    text = (SCZ_ML / "SUMMARY.md").read_text(encoding="utf-8")
    top = re.findall(r"^\| ([^|]+) \| ([0-9.]+) \| (SCZ|Healthy) \|$", text, re.M)
    grab = lambda pat: float(re.search(pat, text).group(1))
    return text, top, {
        "batch_auc": grab(r"Batch signal.*?\*\*([0-9.]+)\*\*"),
        "batch_auc_harmonised": grab(r"after harmonisation.*?\*\*([0-9.]+)\*\*"),
        "covariate_auc": grab(r"Covariate-only.*?\*\*([0-9.]+)\*\*"),
    }


def extras(disease):
    f = EXTRAS / f"{disease}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def scz():
    s = pd.read_csv(SCZ_DATA / "scz_samples.tsv", sep="\t")
    s = s[(s.included == True) & s.group.isin(["Healthy", "SCZ"])]  # noqa: E712
    cohort = (s.groupby("study_id").agg(country=("country", "first"), platform=("platform", "first"),
                                        healthy=("group", lambda g: int((g == "Healthy").sum())),
                                        scz=("group", lambda g: int((g == "SCZ").sum())))
              .reset_index().to_dict("records"))
    cv, lo = pd.read_csv(SCZ_ML / "cv_folds.csv"), pd.read_csv(SCZ_ML / "loso_folds.csv")
    oof = pd.read_csv(SCZ_ML / "oof_predictions.csv")
    oof = oof[oof.experiment == FINAL]
    lo_e = lo[lo.experiment == FINAL]
    per_study = lo_e.pivot_table(index="fold", columns="model", values="roc_auc")
    experiments = []
    for e in sorted(cv.experiment.unique()):
        ens_i = cv[(cv.experiment == e) & (cv.model == ENS)].roc_auc
        ens_l = lo[(lo.experiment == e) & (lo.model == ENS)]
        experiments.append({"experiment": e, "internal": r(ens_i.mean()), "external": r(ens_l.roc_auc.mean()),
                            "external_worst": r(ens_l.roc_auc.min())})
    _, top, checks = summary_lines()
    return {
        "generated": time.strftime("%d %b %Y %H:%M"), "source": "research/Neurogut schizophrenia/scz-ml/results",
        "final_experiment": FINAL, "ensemble": ENS,
        "n_samples": int(len(s[s.study_id != "Xu_2020_SCZ"])), "cohort": cohort,
        "internal": with_ci(per_model(cv[cv.experiment == FINAL], METRICS), oof[oof.design == "internal"]),
        "external": with_ci(per_model(lo_e, METRICS), oof[oof.design == "loso"]),
        "external_by_study": [{"study": st, **{m: r(per_study.loc[st, m]) for m in per_study.columns},
                               "n": int(lo_e[lo_e.fold == st].n_test.iloc[0])} for st in per_study.index],
        "experiments": experiments,
        "top_features": [{"feature": f.strip(), "importance": float(i), "higher_in": d} for f, i, d in top],
        "checks": checks,
        "extras": extras("scz"),
    }


def pd_arm():
    def load(name, metrics=("roc_auc",)):
        f = PD / name
        return per_model(pd.read_csv(f), list(metrics)) if f.exists() else []

    strat = pd.read_csv(PD / "constipation_stratified_fold_results.csv")
    strat = strat.groupby(["stratum", "model"]).roc_auc.mean().round(3).reset_index().to_dict("records")
    meta = pd.read_csv(PD / "labels_metadata.csv")
    return {
        "generated": time.strftime("%d %b %Y %H:%M"),
        "source": "research/Neurogut schizophrenia/external_repos/pd_repo (branch upload-pd-neurogut-files)",
        "n_samples": int(len(meta)), "n_pd": int(meta.Label.sum()), "n_control": int((meta.Label == 0).sum()),
        "nested_cv": load("nested_cv_fold_results_v5.csv", ("roc_auc", "pr_auc", "f1")),
        "ablations": {
            "Genus, full pipeline (v5)": load("nested_cv_fold_results_v5.csv"),
            "Covariates only": load("covariate_only_ablation_fold_results.csv"),
            "Constipation dropped": load("constipation_dropped_fold_results.csv"),
            "Species level": load("species_level_fold_results.csv"),
            "Pathways collapsed": load("pathway_collapsed_fold_results.csv"),
        },
        "constipation_strata": strat,
        # Final numbers as reported by the PD team (message of 28 Oct 2026); not in the repo's CSVs.
        "reported": {"internal_auc": 0.699, "external_auc": 0.619, "elasticnet_external_auc": 0.661,
                     "model": "frozen microbiome-only ensemble"},
        "extras": extras("pd"),
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("scz", scz), ("pd", pd_arm)):
        (OUT / f"{name}.json").write_text(json.dumps(fn(), indent=1, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)), encoding="utf-8")
        print("wrote", OUT / f"{name}.json")
