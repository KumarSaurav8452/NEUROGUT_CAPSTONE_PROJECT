"""Load the SCZ cohort from scz-microbiome-data outputs (read-only)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_ROOT = Path(__file__).resolve().parents[3] / "scz-microbiome-data"
SAMPLES = DATA_ROOT / "results/scz_samples.tsv"
# The five per-study species tables we retrieved and profiled (scz-microbiome-data); nothing else is used.
SPECIES = sorted((DATA_ROOT / "results/profiles/by_study").glob("*.species.tsv"))
CASE_ONLY = ["Xu_2020_SCZ"]  # no controls: kept out of training, used for a sensitivity check only


def load(samples=SAMPLES, species=SPECIES):
    """Return (meta, frac, xu_meta, xu_frac).

    meta: one row per included sample of the case-control studies (sample_id index, study_id, y, age, sex, bmi).
    frac: samples x species, fractions summing to 1, columns are full MetaPhlAn lineages.
    """
    meta = pd.read_csv(samples, sep="\t")
    meta = meta[(meta["included"] == True) & meta["group"].isin(["Healthy", "SCZ"])].copy()  # noqa: E712
    meta["y"] = (meta["group"] == "SCZ").astype(int)
    meta = meta.set_index("sample_id")[["study_id", "group", "y", "age", "sex", "bmi"]]

    if len(species) != 5:
        raise FileNotFoundError(f"expected the 5 per-study abundance tables, found {len(species)}")
    tab = pd.concat([pd.read_csv(f, sep="\t", index_col=0) for f in species], axis=1).fillna(0.0)
    tab = tab[tab.index.str.contains(r"\|s__")]
    frac = (tab.T / 100.0).reindex(meta.index)
    missing = frac.isna().all(axis=1)
    if missing.any():
        raise ValueError(f"{int(missing.sum())} included samples have no profile, e.g. {list(frac.index[missing][:3])}")
    frac = frac.fillna(0.0)
    frac = frac.loc[:, frac.sum() > 0]
    frac = frac.div(frac.sum(axis=1), axis=0)

    case_only = meta["study_id"].isin(CASE_ONLY)
    return meta[~case_only], frac[~case_only], meta[case_only], frac[case_only]


def to_level(frac: pd.DataFrame, rank: str = "g") -> pd.DataFrame:
    """Sum species to a higher rank ('g' genus, 'f' family); column = lineage down to that rank."""
    depth = "kpcofgs".index(rank) + 1
    up = frac.T.groupby(frac.columns.str.split("|").str[:depth].str.join("|")).sum().T
    return up[up.columns[up.columns.str.split("|").str[-1].str.startswith(f"{rank}__")]]


def to_genus(frac: pd.DataFrame) -> pd.DataFrame:
    return to_level(frac, "g")


def multi_level(frac: pd.DataFrame) -> pd.DataFrame:
    """Species + genus + family side by side (CLR is applied per rank in FoldFeaturizer)."""
    return pd.concat([frac, to_level(frac, "g"), to_level(frac, "f")], axis=1)


def short_name(lineage: str) -> str:
    return lineage.split("|")[-1]
