"""ENA: run metadata via the Portal API filereport, sample attributes via the Browser API XML."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET

import pandas as pd

from scz_data.fetch.http import CachedHttp
from scz_data.fetch.schema import attr_name, norm_layout, norm_platform

# ENA housekeeping attributes that carry no sample information.
_SKIP_ATTRS = {"ENA-CHECKLIST", "ENA-FIRST-PUBLIC", "ENA-LAST-UPDATE", "common name"}


def fetch_runs(http: CachedHttp, cfg: dict, project: str) -> pd.DataFrame:
    body = http.get(
        f"{cfg['ena']['portal']}/filereport",
        params={
            "accession": project,
            "result": "read_run",
            "fields": ",".join(cfg["ena"]["run_fields"]),
            "format": "tsv",
        },
    )
    df = pd.read_csv(io.BytesIO(body), sep="\t", dtype=str, keep_default_na=False)
    if df.empty:
        raise RuntimeError(f"ENA {project}: filereport returned no runs")
    return df


def fetch_sample_attributes(http: CachedHttp, cfg: dict, accessions: list[str]) -> pd.DataFrame:
    """One row per sample accession with attr_* columns."""
    rows = []
    batch = cfg["ena"]["sample_xml_batch"]
    accs = sorted(set(accessions))
    for i in range(0, len(accs), batch):
        chunk = accs[i : i + batch]
        body = http.get(f"{cfg['ena']['browser']}/xml/{','.join(chunk)}", expect="xml")
        root = ET.fromstring(body)
        for s in root.findall("SAMPLE"):
            row = {"sample_accession": s.get("accession")}
            title = s.findtext("TITLE")
            if title:
                row["attr_title"] = title
            for a in s.iter("SAMPLE_ATTRIBUTE"):
                tag, value = a.findtext("TAG"), a.findtext("VALUE")
                if tag and tag not in _SKIP_ATTRS and value not in (None, ""):
                    row.setdefault(attr_name(tag), value)
            rows.append(row)
    got = {r["sample_accession"] for r in rows}
    missing = set(accs) - got
    if missing:
        raise RuntimeError(f"ENA sample XML missing {len(missing)} samples, e.g. {sorted(missing)[:3]}")
    return pd.DataFrame(rows)


def to_schema(runs: pd.DataFrame, study_id: str, project: str) -> pd.DataFrame:
    def https(urls: str) -> str:
        return ";".join(f"https://{u}" if u and not u.startswith(("http", "ftp://")) else u for u in urls.split(";") if u)

    return pd.DataFrame(
        {
            "study_id": study_id,
            "archive": "ENA",
            "source_accession": project,
            "run_accession": runs["run_accession"],
            "experiment_accession": runs["experiment_accession"],
            "sample_accession": runs["sample_accession"],
            "sample_name": runs["sample_alias"],
            "sample_title": runs["sample_title"],
            "library_strategy": runs["library_strategy"],
            "library_source": runs["library_source"],
            "library_layout": runs["library_layout"].map(norm_layout),
            "instrument_platform": runs["instrument_platform"].map(norm_platform),
            "instrument_model": runs["instrument_model"],
            "read_count": pd.to_numeric(runs["read_count"], errors="coerce").astype("Int64"),
            "base_count": pd.to_numeric(runs["base_count"], errors="coerce").astype("Int64"),
            "fastq_urls": runs["fastq_ftp"].map(https),
            "fastq_md5": runs["fastq_md5"],
            "fastq_bytes": runs["fastq_bytes"],
            "download_source": "ENA",
        }
    )


def fetch_project(http: CachedHttp, cfg: dict, study_id: str, project: str) -> pd.DataFrame:
    runs = fetch_runs(http, cfg, project)
    df = to_schema(runs, study_id, project)
    attrs = fetch_sample_attributes(http, cfg, df["sample_accession"].tolist())
    return df.merge(attrs, on="sample_accession", how="left")
