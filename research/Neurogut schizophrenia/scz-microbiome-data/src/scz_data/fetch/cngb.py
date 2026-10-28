"""CNGBdb / CNSA: metadata TSVs from the public_info area, file sizes from HEAD requests on the FTP mirror."""

from __future__ import annotations

import io
import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from scz_data.fetch import ena
from scz_data.fetch.http import CachedHttp
from scz_data.fetch.schema import attr_name, norm_layout, norm_platform

_EMPTY = {"", "NA", "not collected", "无"}


def _public_info_listing(http: CachedHttp, cfg: dict, project: str) -> list[str]:
    html = http.get(f"{cfg['cngb']['public_info']}/{project}/").decode("utf-8", "replace")
    return sorted(set(re.findall(r'href="(metadata_[^"]+\.tsv)"', html)))


def fetch_tables(http: CachedHttp, cfg: dict, project: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    files = _public_info_listing(http, cfg, project)
    exp_file = next(f for f in files if f.endswith("_experiment.tsv"))
    sample_file = next(f for f in files if "_sample_" in f)
    base = f"{cfg['cngb']['public_info']}/{project}"
    read = lambda f: pd.read_csv(io.BytesIO(http.get(f"{base}/{f}")), sep="\t", dtype=str, keep_default_na=False)
    return read(exp_file), read(sample_file)


def file_urls(cfg: dict, project: str, row: pd.Series) -> list[tuple[str, str]]:
    out = []
    for name_col, md5_col in (("file_name", "file_md5"), ("file2_name", "file2_md5"), ("file3_name", "file3_md5")):
        if row.get(name_col):
            url = (
                f"{cfg['cngb']['ftp_root']}/{project}/{row['sample_accession']}/"
                f"{row['experiment_accession']}/{row['run_accession']}/{row[name_col]}"
            )
            out.append((url, row[md5_col]))
    return out


def to_schema(cfg: dict, study_id: str, project: str, exp: pd.DataFrame, samples: pd.DataFrame) -> pd.DataFrame:
    files = [file_urls(cfg, project, r) for _, r in exp.iterrows()]
    df = pd.DataFrame(
        {
            "study_id": study_id,
            "archive": "CNGB",
            "source_accession": project,
            "run_accession": exp["run_accession"],
            "experiment_accession": exp["experiment_accession"],
            "sample_accession": exp["sample_accession"],
            "sample_name": exp["sample_name"],
            "library_strategy": exp["library_strategy"],
            "library_source": exp["library_source"],
            "library_layout": exp["library_layout"].map(norm_layout),
            "instrument_platform": exp["platform"].map(norm_platform),
            "instrument_model": exp["instrument_model"],
            "fastq_urls": [";".join(u for u, _ in fl) for fl in files],
            "fastq_md5": [";".join(m for _, m in fl) for fl in files],
            "download_source": "CNGB",
            "attr_experiment_title": exp["experiment_title"],
        }
    )
    attrs = samples.drop(columns=["sample_name"]).copy()
    attrs = attrs.rename(columns={c: attr_name(c) for c in attrs.columns if c != "sample_accession"})
    keep = ["sample_accession"] + [c for c in attrs.columns if c != "sample_accession" and not attrs[c].isin(_EMPTY).all()]
    attrs = attrs[keep]
    df = df.merge(attrs, on="sample_accession", how="left")
    df["sample_title"] = df.pop("attr_sample_title") if "attr_sample_title" in df else ""
    return df


def add_file_sizes(http: CachedHttp, cfg: dict, df: pd.DataFrame) -> pd.DataFrame:
    """CNGB metadata has no sizes: HEAD each file (cached) and fill fastq_bytes."""
    urls = [u for fl in df["fastq_urls"] for u in fl.split(";") if u]
    with ThreadPoolExecutor(cfg["http"]["head_workers"]) as pool:
        sizes = dict(zip(urls, pool.map(http.head_size, urls)))
    df = df.copy()
    df["fastq_bytes"] = [
        ";".join("" if sizes[u] is None else str(sizes[u]) for u in fl.split(";") if u) for fl in df["fastq_urls"]
    ]
    return df


def split_by_platform(df: pd.DataFrame, platform: str | None) -> pd.DataFrame:
    """Zhu_2020A/B share CNP0000119: keep only runs on this study's platform (PRD special case 1)."""
    if not platform:
        return df
    return df[df["instrument_platform"] == platform].copy()


def attach_ena_mirror(http: CachedHttp, cfg: dict, df: pd.DataFrame, mirror: str) -> pd.DataFrame:
    """Point fastq_* at the ENA copy where one exists; ENA sample_alias == CNGB sample accession."""
    ena_runs = ena.to_schema(ena.fetch_runs(http, cfg, mirror), "", mirror)
    ena_runs = ena_runs.rename(columns={"sample_name": "cngb_sample_accession"})
    by_cns = ena_runs.set_index("cngb_sample_accession")
    if by_cns.index.duplicated().any():
        raise RuntimeError(f"ENA mirror {mirror}: more than one run per CNGB sample; join would be ambiguous")
    df = df.copy()
    hit = df["sample_accession"].isin(by_cns.index)
    m = by_cns.loc[df.loc[hit, "sample_accession"]]
    df.loc[hit, "alt_fastq_urls"] = df.loc[hit, "fastq_urls"].values
    for col in ("fastq_urls", "fastq_md5", "fastq_bytes", "read_count", "base_count"):
        df.loc[hit, col] = m[col].values
    df.loc[hit, "download_source"] = f"ENA:{mirror}"
    df.loc[hit, "attr_ena_run_accession"] = m["run_accession"].values
    df.loc[hit, "attr_ena_sample_accession"] = m["sample_accession"].values
    return df


def fetch_project(http: CachedHttp, cfg: dict, study: dict, project: str, log) -> pd.DataFrame:
    exp, samples = fetch_tables(http, cfg, project)
    log.info(f"CNGB {project}: {len(exp)} runs / {exp['sample_accession'].nunique()} samples in archive")
    df = split_by_platform(to_schema(cfg, study["study_id"], project, exp, samples), study.get("platform_split"))
    if study.get("platform_split"):
        log.info(f"platform split {study['platform_split']}: kept {len(df)} runs")
    df = add_file_sizes(http, cfg, df)
    if study.get("ena_mirror"):
        df = attach_ena_mirror(http, cfg, df, study["ena_mirror"])
        n = df["download_source"].str.startswith("ENA").sum()
        log.info(f"ENA mirror {study['ena_mirror']}: {n}/{len(df)} runs mapped (rest stay on CNGB)")
    return df
