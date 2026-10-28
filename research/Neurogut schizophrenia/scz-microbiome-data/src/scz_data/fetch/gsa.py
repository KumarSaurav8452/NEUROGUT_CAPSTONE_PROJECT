"""NGDC GSA: the per-project metadata export (xlsx with Sample / Experiment / Run sheets)."""

from __future__ import annotations

import io
import re

import openpyxl
import pandas as pd

from scz_data.fetch.http import CachedHttp
from scz_data.fetch.schema import attr_name, norm_layout, platform_from_model

_SIZE = re.compile(r"^(?P<name>\S+)\s+\((?P<bytes>\d+) bytes\)$")


def _sheet(wb, name: str) -> pd.DataFrame:
    rows = list(wb[name].iter_rows(values_only=True))
    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    return pd.DataFrame([r for r in rows[1:] if any(v not in (None, "") for v in r)], columns=header)


def fetch_export(http: CachedHttp, cfg: dict, accession: str) -> dict[str, pd.DataFrame]:
    body = http.post(cfg["gsa"]["export_url"], data={"type": "3", "dlAcession": accession}, expect="xlsx")
    wb = openpyxl.load_workbook(io.BytesIO(body), data_only=True)  # not read_only: the export lacks sheet dimensions
    return {name: _sheet(wb, name) for name in ("Sample", "Experiment", "Run")}


def _https(url: str, cfg: dict) -> str:
    # The export lists ftp://download.big.ac.cn/gsa2/...; the same tree is served over HTTPS.
    return re.sub(r"^ftp://download\.big\.ac\.cn/gsa2", cfg["gsa"]["download_root"], url or "")


def to_schema(cfg: dict, study_id: str, accession: str, sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    s, e, r = sheets["Sample"], sheets["Experiment"], sheets["Run"]
    exp = e.set_index("Accession")
    smp = s.set_index("Accession")
    rows = []
    for _, run in r.iterrows():
        x = exp.loc[run["Experiment accession"]]
        sample_acc = x["BioSample accession"]
        names, sizes, md5s, urls = [], [], [], []
        for fname_col, md5_col, url_col in (
            ("Read filename 1", "Read file1 MD5", "DownLoad Read file1"),
            ("Read filename 2", "Read file2 MD5", "DownLoad  Read file2"),  # sic: double space in the export
        ):
            if run.get(fname_col):
                m = _SIZE.match(str(run[fname_col]).strip())
                names.append(m["name"] if m else run[fname_col])
                sizes.append(m["bytes"] if m else "")
                md5s.append(run[md5_col])
                urls.append(_https(run[url_col], cfg))
        row = {
            "study_id": study_id,
            "archive": "GSA",
            "source_accession": accession,
            "run_accession": run["Accession"],
            "experiment_accession": run["Experiment accession"],
            "sample_accession": sample_acc,
            "sample_name": smp.loc[sample_acc, "Sample name"],
            "sample_title": smp.loc[sample_acc, "Sample title"],
            "library_strategy": x["Strategy"],
            "library_source": x["Source"],
            "library_layout": norm_layout(x["Layout"]),
            "instrument_platform": platform_from_model(x["Platform"]),
            "instrument_model": x["Platform"],
            "fastq_urls": ";".join(urls),
            "fastq_md5": ";".join(md5s),
            "fastq_bytes": ";".join(sizes),
            "download_source": "GSA",
        }
        for col, val in smp.loc[sample_acc].items():
            if col not in ("Sample name", "Sample title", "ID") and val not in (None, ""):
                row[attr_name(col)] = val
        rows.append(row)
    return pd.DataFrame(rows)


def fetch_project(http: CachedHttp, cfg: dict, study_id: str, accession: str) -> pd.DataFrame:
    return to_schema(cfg, study_id, accession, fetch_export(http, cfg, accession))
