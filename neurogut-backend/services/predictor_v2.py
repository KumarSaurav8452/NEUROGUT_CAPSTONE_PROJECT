"""NeuroGut v2 predictor: Parkinson's and schizophrenia deploy models (research/.../scz-ml/src/sczml/deploy.py).

Each bundle holds RF + XGBoost + Elastic Net trained on log10(relative abundance % + 0.01) of ~30 taxa, so a
single sample can be scored on its own, from typed values, a CSV of those taxa, or a full MetaPhlAn profile.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "v2"
DISEASES = ("scz", "pd")
RANK_NAME = {"s": "species", "g": "genus", "f": "family"}


def _key(name: str) -> str:
    """Normalise a taxon name: 's__Collinsella_aerofaciens', 'Collinsella aerofaciens', full lineage -> same key."""
    last = str(name).strip().split("|")[-1]
    return re.sub(r"^[a-z]__", "", last).replace(" ", "_").lower()


class PredictorV2:
    def __init__(self):
        self.bundles: dict[str, dict] = {}

    def load(self):
        for d in DISEASES:
            f = MODEL_DIR / f"{d}.joblib"
            if f.exists():
                self.bundles[d] = joblib.load(f)

    def get(self, disease: str) -> dict:
        if not self.bundles:
            self.load()
        if disease not in self.bundles:
            raise KeyError(disease)
        return self.bundles[disease]

    def info(self) -> list[dict]:
        if not self.bundles:
            self.load()
        out = []
        for d, b in self.bundles.items():
            out.append({
                "disease": d, "label": b["label"], "version": b["version"], "n_train": b["n_train"],
                "n_cases": b["n_cases"], "metrics": b["metrics"], "threshold": b["threshold"], "tiers": b["tiers"],
                "source": b["source"],
                "features": [{"name": b["display"][f], "lineage": f, "rank": b["display"][f][0],
                              "healthy_median_pct": round(b["reference"][f]["healthy_median_pct"], 4),
                              "higher_in": "disease" if b["reference"][f]["case_mean"] > b["reference"][f]["healthy_mean"] else "healthy"}
                             for f in b["features"]],
            })
        return out

    # -- input parsing -------------------------------------------------------
    def from_named(self, disease: str, values: dict[str, float]) -> tuple[dict[str, float], int]:
        """Typed or CSV values keyed by taxon name -> {model feature: %}; missing taxa count as 0 (not detected)."""
        b = self.get(disease)
        given = {_key(k): v for k, v in values.items()}
        out, missing = {}, 0
        for f in b["features"]:
            v = given.get(_key(f))
            if v is None or v == "" or (isinstance(v, float) and np.isnan(v)):
                missing += 1
                v = 0.0
            out[f] = v
        self.validate(disease, out)
        return {f: float(v) for f, v in out.items()}, missing

    def validate(self, disease: str, pct: dict) -> None:
        """Relative abundances must be numbers in 0-100 %, and taxa of one rank cannot add up to more than 100 %."""
        b = self.get(disease)
        problems, by_rank = [], {}
        for f, v in pct.items():
            name = b["display"][f]
            try:
                v = float(v)
            except (TypeError, ValueError):
                problems.append(f"{name}: '{v}' is not a number")
                continue
            if not np.isfinite(v) or v < 0 or v > 100:
                problems.append(f"{name}: {v:g} is outside 0-100 %")
            else:
                by_rank[name[0]] = by_rank.get(name[0], 0.0) + v
        for rank, total in by_rank.items():
            if total > 100.5:
                problems.append(f"{RANK_NAME.get(rank, rank)} values add up to {total:.1f} % (more than 100 %)")
        if problems:
            raise ValueError("; ".join(problems))

    def from_profile(self, disease: str, table: pd.DataFrame) -> dict[str, dict[str, float]]:
        """MetaPhlAn table (rows = clades with lineage, columns = samples, values in %) -> per-sample features.
        Genus/family values come from their own rows when present, else from summing the species below."""
        b = self.get(disease)
        table = table.apply(pd.to_numeric, errors="coerce").fillna(0.0)
        species = table[table.index.str.contains(r"\|s__") & ~table.index.str.contains(r"\|t__")]
        samples = {}
        for col in table.columns:
            feats = {}
            for f in b["features"]:
                if f in table.index:
                    feats[f] = float(table.at[f, col])
                else:
                    feats[f] = float(species.loc[species.index.str.startswith(f + "|"), col].sum())
            samples[str(col)] = feats
        return samples

    @staticmethod
    def read_upload(content: bytes) -> tuple[str, pd.DataFrame]:
        """Return ('profile', clades x samples) or ('rows', samples x taxa)."""
        text = content.decode("utf-8-sig")
        sep = "\t" if text.split("\n", 1)[0].count("\t") > text.split("\n", 1)[0].count(",") else ","
        lines = [ln for ln in text.splitlines() if ln.strip() and not (ln.startswith("#") and "clade" not in ln.lower())]
        df = pd.read_csv(io.StringIO("\n".join(lines)), sep=sep)
        first = df.columns[0]
        if df[first].astype(str).str.contains(r"k__|\|").mean() > 0.5:
            df = df.set_index(first)
            df = df[[c for c in df.columns if c.lower() not in ("ncbi_tax_id", "clade_taxid", "additional_species")]]
            return "profile", df
        return "rows", df

    # -- scoring -------------------------------------------------------------
    def predict(self, disease: str, pct: dict[str, float]) -> dict:
        b = self.get(disease)
        feats = b["features"]
        x = pd.DataFrame([[np.log10((pct[f] if pct[f] >= b["floor_pct"] else 0.0) + b["floor_pct"]) for f in feats]],
                         columns=feats)
        # Effect of each taxon on THIS score: re-score with that taxon set to the healthy average (one batch);
        # effect = score - score_without_it, in probability points (+ raises the disease score, - lowers it).
        swapped = pd.concat([x] * len(feats), ignore_index=True)
        for i, f in enumerate(feats):
            swapped.iat[i, i] = b["reference"][f]["healthy_mean"]
        both = pd.concat([x, swapped], ignore_index=True)
        per_model = {name: m.predict_proba(both)[:, 1] for name, m in b["models"].items()}
        ens = np.mean(list(per_model.values()), axis=0)
        p = float(ens[0])
        probs = {name: float(v[0]) for name, v in per_model.items()}
        tier = "high" if p >= b["tiers"]["high"] else "low" if p < b["tiers"]["low"] else "moderate"
        drivers = []
        for i, f in enumerate(feats):
            r = b["reference"][f]
            drivers.append({"taxon": b["display"][f], "value_pct": round(pct[f], 4),
                            "healthy_median_pct": round(r["healthy_median_pct"], 4),
                            "z": round(float((x.at[0, f] - r["healthy_mean"]) / (r["healthy_sd"] or 1.0)), 2),
                            "push": round(float(p - ens[i + 1]), 4)})
        drivers.sort(key=lambda d: -abs(d["push"]))
        return {"probability": round(p, 4), "label": int(p >= b["threshold"]), "risk_tier": tier,
                "model_probs": {k: round(v, 4) for k, v in probs.items()}, "drivers": drivers[:8],
                "threshold": b["threshold"], "model_version": b["version"]}


predictor_v2 = PredictorV2()
