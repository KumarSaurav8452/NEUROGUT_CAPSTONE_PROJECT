"""FR-2: per-archive run-level metadata retrieval -> data/raw_metadata/<StudyID>.tsv."""

from __future__ import annotations

import pandas as pd

from scz_data.fetch import cngb, ena, gsa, manual
from scz_data.fetch.http import CachedHttp
from scz_data.fetch.schema import finalize
from scz_data.settings import Settings, get_logger


def fetch_study(http: CachedHttp, settings: Settings, study: dict, log) -> pd.DataFrame:
    cfg, sid = settings.cfg, study["study_id"]
    archive = study["archive"]
    if archive == "manual":
        return manual.fetch_project(sid, settings.path("manual") / sid)
    parts = []
    for acc in study["accessions"]:
        if archive == "ENA":
            part = ena.fetch_project(http, cfg, sid, acc)
        elif archive == "CNGB":
            part = cngb.fetch_project(http, cfg, study, acc, log)
        elif archive == "GSA":
            part = gsa.fetch_project(http, cfg, sid, acc)
        else:
            raise ValueError(f"unknown archive {archive!r}")
        log.info(f"{archive} {acc}: {len(part)} runs / {part['sample_accession'].nunique()} samples")
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def run(settings: Settings, studies: list[dict], refresh: bool = False) -> dict[str, str]:
    http = CachedHttp(settings.path("cache"), settings.cfg["http"], refresh=refresh)
    out_dir = settings.path("raw_metadata")
    out_dir.mkdir(parents=True, exist_ok=True)
    status = {}
    for study in studies:
        sid = study["study_id"]
        log = get_logger(settings, "metadata", sid)
        try:
            df = finalize(fetch_study(http, settings, study, log))
            if df["run_accession"].duplicated().any():
                raise RuntimeError("duplicate run_accession after fetch")
            out = out_dir / f"{sid}.tsv"
            tmp = out.with_suffix(".tmp")
            df.to_csv(tmp, sep="\t", index=False)
            tmp.replace(out)
            log.info(f"wrote {out.relative_to(settings.root)}: {len(df)} runs / {df['sample_accession'].nunique()} samples")
            status[sid] = "OK"
        except manual.AwaitingAccess as e:
            log.warning(str(e))
            status[sid] = "SKIPPED: awaiting access"
        except Exception as e:  # one failing study must not stop the others (PRD §6.2)
            log.exception(f"FAILED: {e}")
            status[sid] = f"FAILED: {e}"
    return status
