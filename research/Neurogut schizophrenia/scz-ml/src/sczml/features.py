"""Fold-local features, after PD_pipeline_v12: CLR taxa, diversity, Bray-Curtis and UniFrac-style
distance to the training controls, co-occurrence network loads. Everything that depends on labels or on
the sample distribution is fit on the training rows only (FoldFeaturizer.fit), then applied to any rows."""

from __future__ import annotations

import warnings

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from statsmodels.stats.multitest import multipletests

from sczml.data import short_name

PSEUDO = 1e-6
PREVALENCE = 0.10
N_TOP_COMMUNITIES = 5
DETECTION_FLOOR = 1e-4  # 0.01 %: about 30 reads in a 300 k-read subsample


def clr(frac: pd.DataFrame) -> pd.DataFrame:
    """CLR within each taxonomic rank (a table holding several ranks is not one composition)."""
    rank = frac.columns.str.split("|").str[-1].str[0]
    parts = []
    for r in pd.unique(rank):
        log = np.log(frac.loc[:, rank == r] + PSEUDO)
        parts.append(log.sub(log.mean(axis=1), axis=0))
    return pd.concat(parts, axis=1)[frac.columns]


def shannon(frac: pd.DataFrame) -> np.ndarray:
    p = frac.values
    with np.errstate(divide="ignore", invalid="ignore"):
        return -np.nansum(np.where(p > 0, p * np.log(p), 0.0), axis=1)


def simpson(frac: pd.DataFrame) -> np.ndarray:
    return 1.0 - (frac.values ** 2).sum(axis=1)


def bray_curtis_to(frac: np.ndarray, centroid: np.ndarray) -> np.ndarray:
    return np.abs(frac - centroid).sum(axis=1) / ((frac + centroid).sum(axis=1) + 1e-12)


def taxonomy_matrix(lineages: list[str]) -> np.ndarray:
    """Taxa x tree-nodes membership (phylum..leaf), unit branch lengths, as PD v12 Phase 4b."""
    nodes, chains = {}, []
    for lin in lineages:
        parts = lin.split("|")[1:]  # drop kingdom
        chain = [nodes.setdefault(tuple(parts[: i + 1]), len(nodes)) for i in range(len(parts))]
        chains.append(chain)
    m = np.zeros((len(lineages), len(nodes)))
    for i, chain in enumerate(chains):
        m[i, chain] = 1.0
    return m


def fit_network(frac_train: pd.DataFrame, r_cut=0.30, q_cut=0.05, r_relaxed=0.20, q_relaxed=0.10):
    """Spearman co-occurrence graph on training rows; relax once if empty (PD v5 fix)."""
    rho, p = spearmanr(frac_train.values)
    iu = np.triu_indices(frac_train.shape[1], k=1)
    q = multipletests(np.nan_to_num(p[iu], nan=1.0), method="fdr_bh")[1]
    r = np.nan_to_num(rho[iu])
    names = list(frac_train.columns)
    relaxed = False
    for rc, qc in ((r_cut, q_cut), (r_relaxed, q_relaxed)):
        keep = (np.abs(r) > rc) & (q < qc)
        g = nx.Graph()
        g.add_nodes_from(names)
        g.add_weighted_edges_from((names[i], names[j], abs(w)) for i, j, w in zip(iu[0][keep], iu[1][keep], r[keep]))
        if g.number_of_edges():
            break
        relaxed = True
    deg = nx.degree_centrality(g)
    try:
        eig = nx.eigenvector_centrality(g, max_iter=1000, weight="weight")
    except (nx.PowerIterationFailedConvergence, nx.NetworkXError, ZeroDivisionError):
        eig = deg
    comms = sorted(nx.community.greedy_modularity_communities(g, weight="weight"), key=len, reverse=True) \
        if g.number_of_edges() else []
    rank = {t: k for k, c in enumerate(comms) for t in c if len(c) > 1}
    return {"deg": deg, "eig": eig, "rank": rank, "edges": g.number_of_edges(),
            "communities": sum(len(c) > 1 for c in comms), "relaxed": relaxed}


def network_features(frac: pd.DataFrame, net: dict) -> pd.DataFrame:
    taxa = list(frac.columns)
    a = frac.values
    deg = np.array([net["deg"].get(t, 0.0) for t in taxa])
    eig = np.array([net["eig"].get(t, 0.0) for t in taxa])
    hub = deg >= np.quantile(deg, 0.90) if deg.max() > 0 else np.zeros(len(taxa), bool)
    ranks = np.array([net["rank"].get(t, -1) for t in taxa])
    out = {"net_weighted_degree": a @ deg, "net_weighted_eigenvector": a @ eig, "net_hub_load": a[:, hub].sum(axis=1)}
    for k in range(N_TOP_COMMUNITIES):
        out[f"net_comm_{k + 1}"] = a[:, ranks == k].sum(axis=1)
    out["net_comm_other"] = a[:, (ranks == -1) | (ranks >= N_TOP_COMMUNITIES)].sum(axis=1)
    return pd.DataFrame(out, index=frac.index)


def detection_floor(frac: pd.DataFrame, floor=DETECTION_FLOOR) -> pd.DataFrame:
    """Zero abundances below a common floor and renormalise, so full-depth (Zhu A) and 300-500 k-read
    subsample profiles share one detection limit."""
    f = frac.where(frac >= floor, 0.0)
    return f.div(f.sum(axis=1).replace(0, 1), axis=0)


def per_study_standardise(x: pd.DataFrame, study: pd.Series) -> pd.DataFrame:
    """Centre and scale every feature within each study (label-free, as in SIAMCAT/Wirbel 2019 meta-analyses).
    Pass all rows of each study together (train + test of a fold) so the statistics never use labels."""
    g = x.groupby(study.values)
    sd = g.transform("std").replace(0, 1).fillna(1)
    return (x - g.transform("mean")) / sd


def rank_within_study(x: pd.DataFrame, study: pd.Series) -> pd.DataFrame:
    """Percentile rank of every feature within its study (label-free; robust to outliers and to
    study-specific scale)."""
    return x.groupby(study.values).rank(pct=True) - 0.5


class FoldFeaturizer:
    """fit(train fractions, train labels[, train studies]) -> transform(any fractions) -> feature DataFrame.

    With `study` given, a taxon is kept only if > 10 % prevalent in at least half of the training studies,
    so features present in only one cohort (pure batch markers) are dropped."""

    def __init__(self, extras: bool):
        self.extras = extras

    def fit(self, frac: pd.DataFrame, y: pd.Series, study: pd.Series | None = None):
        if study is None:
            self.taxa = frac.columns[(frac > 0).mean() > PREVALENCE]
        else:
            per_study = (frac > 0).groupby(study.values).mean() > PREVALENCE
            self.taxa = frac.columns[per_study.sum() >= np.ceil(per_study.shape[0] / 2)]
        self.all_taxa = frac.columns
        if self.extras:
            ctrl = frac.loc[y.values == 0] if (y == 0).any() else frac
            self.bc_centroid = ctrl.values.mean(axis=0)
            self.tree = taxonomy_matrix(list(self.all_taxa))
            self.uf_centroid = (ctrl.values @ self.tree).mean(axis=0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.net = fit_network(frac[self.taxa])
        return self

    def transform(self, frac: pd.DataFrame) -> pd.DataFrame:
        frac = frac.reindex(columns=self.all_taxa, fill_value=0.0)
        x = clr(frac[self.taxa])
        x.columns = [f"taxon__{short_name(c)}" for c in self.taxa]
        if not self.extras:
            return x
        nodes = frac.values @ self.tree
        extra = pd.DataFrame({
            "diversity_shannon": shannon(frac), "diversity_simpson": simpson(frac),
            "diversity_bray_to_control": bray_curtis_to(frac.values, self.bc_centroid),
            "phylo_unifrac_to_control": bray_curtis_to(nodes, self.uf_centroid),
        }, index=frac.index)
        return pd.concat([x, extra, network_features(frac[self.taxa], self.net)], axis=1)

    def stats(self) -> dict:
        if not self.extras:
            return {}
        return {k: self.net[k] for k in ("edges", "communities", "relaxed")}
