"""FR-5: FASTQ download: dry-run manifest, and resumable MD5-verified file transfer."""

from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

from scz_data.settings import Settings


class ChecksumError(RuntimeError):
    pass


def md5_of(path: Path, chunk: int = 8 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def fetch_file(url: str, dest: Path, md5: str, size: int | None, dcfg: dict, session: requests.Session | None = None,
               log=None) -> str:
    """Download url -> dest, resuming a partial '.part' file; verify MD5; retry on mismatch (PRD FR-5).

    Returns 'present' if dest already had the right checksum, else 'downloaded'.
    """
    dest = Path(dest)
    if dest.exists() and (size is None or dest.stat().st_size == size) and md5_of(dest) == md5:
        return "present"
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    session = session or requests.Session()
    chunk = dcfg.get("chunk_mb", 8) << 20
    last_err = None
    for attempt in range(1, dcfg["max_tries"] + 1):
        try:
            have = part.stat().st_size if part.exists() else 0
            if size is not None and have > size:
                part.unlink()
                have = 0
            headers = {"Range": f"bytes={have}-"} if have else {}
            if size is None or have < size:
                with session.get(url, headers=headers, stream=True, timeout=(30, 300)) as r:
                    if have and r.status_code == 200:  # server ignored Range: start over
                        have = 0
                    elif r.status_code not in (200, 206):
                        raise RuntimeError(f"HTTP {r.status_code}")
                    with open(part, "ab" if have else "wb") as fh:
                        for block in r.iter_content(chunk):
                            fh.write(block)
            got = md5_of(part)
            if got != md5:
                part.unlink()  # corrupt: next attempt starts from zero
                raise ChecksumError(f"MD5 mismatch for {dest.name}: expected {md5}, got {got}")
            part.replace(dest)
            return "downloaded"
        except (requests.RequestException, RuntimeError) as e:
            last_err = e
            if log:
                log.warning(f"{dest.name}: attempt {attempt}/{dcfg['max_tries']} failed: {e}")
            time.sleep(min(60, dcfg.get("retry_base_s", 2) ** attempt) if dcfg.get("retry_base_s", 2) else 0)
    raise ChecksumError(f"{dest.name}: giving up after {dcfg['max_tries']} attempts: {last_err}")

MANIFEST_COLUMNS = ["study_id", "sample_id", "group", "run_accession", "url", "md5", "bytes", "dest", "present"]


def pick_subset(samples: pd.DataFrame, n: int | None, strategy: str = "smallest") -> pd.DataFrame:
    """N samples per (study, group). 'smallest' = fewest bytes, ties broken by sample_id (deterministic)."""
    if not n:
        return samples
    if strategy == "smallest":
        ordered = samples.sort_values(["study_id", "group", "total_bytes", "sample_id"])
    elif strategy == "first":
        ordered = samples.sort_values(["study_id", "group", "sample_id"])
    else:
        raise ValueError(f"unknown subset_strategy {strategy!r}")
    return ordered.groupby(["study_id", "group"], sort=False).head(n)


def build_manifest(samples: pd.DataFrame, runs: pd.DataFrame, fastq_root: Path) -> pd.DataFrame:
    """One row per file, for the runs listed in each included sample's run_ids."""
    run_ids = samples.assign(run_accession=samples["run_ids"].str.split(";")).explode("run_accession")
    df = run_ids[["study_id", "sample_id", "group", "run_accession"]].merge(
        runs[["run_accession", "fastq_urls", "fastq_md5", "fastq_bytes"]], on="run_accession", how="left"
    )
    if df["fastq_urls"].isna().any():
        missing = df.loc[df["fastq_urls"].isna(), "run_accession"].tolist()
        raise RuntimeError(f"runs without file info: {missing[:5]}")
    rows = []
    for _, r in df.iterrows():
        urls = str(r["fastq_urls"]).split(";")
        md5s = str(r["fastq_md5"]).split(";")
        sizes = str(r["fastq_bytes"]).split(";")
        if not (len(urls) == len(md5s) == len(sizes)):
            raise RuntimeError(f"{r['run_accession']}: url/md5/bytes lists differ in length")
        for url, md5, size in zip(urls, md5s, sizes):
            dest = fastq_root / r["study_id"] / r["run_accession"] / Path(urlparse(url).path).name
            size = int(size) if size else None
            rows.append(
                {
                    "study_id": r["study_id"], "sample_id": r["sample_id"], "group": r["group"],
                    "run_accession": r["run_accession"], "url": url, "md5": md5, "bytes": size,
                    "dest": str(dest),
                    # Size match only; MD5 is verified by the real download step (Phase 3).
                    "present": bool(size is not None and dest.exists() and dest.stat().st_size == size),
                }
            )
    return pd.DataFrame(rows, columns=MANIFEST_COLUMNS)


def _gb(b) -> float:
    return round(float(b) / 1e9, 1)


def load_included(settings: Settings, studies: list[dict], subset: int | None):
    """Included samples (after FR-4) + the labelled run table, with the --subset choice applied."""
    frames, runs_frames, status = [], [], {}
    for study in studies:
        sid = study["study_id"]
        sp = settings.path("filtered") / f"{sid}.samples.tsv"
        lp = settings.path("labelled") / f"{sid}.tsv"
        if not sp.exists():
            status[sid] = "SKIPPED: not filtered yet"
            continue
        s = pd.read_csv(sp, sep="\t", dtype={"run_ids": str}, keep_default_na=False, na_values=[""])
        s["included"] = s["included"].astype(str).str.lower() == "true"
        frames.append(s[s["included"]])
        runs_frames.append(pd.read_csv(lp, sep="\t", dtype=str, keep_default_na=False, na_values=[""]))
        status[sid] = "OK"
    if not frames:
        return None, None, status
    samples = pick_subset(pd.concat(frames, ignore_index=True), subset, settings.cfg["download"]["subset_strategy"])
    return samples, pd.concat(runs_frames, ignore_index=True), status


def run(settings: Settings, studies: list[dict], dry_run: bool, subset: int | None) -> dict[str, str]:
    if not dry_run:
        raise SystemExit("Use `python -m scz_data stream` for real downloads (download + QC + delete raw per sample).")
    dcfg = settings.cfg["download"]
    samples, runs, status = load_included(settings, studies, subset)
    if samples is None:
        return status
    manifest = build_manifest(samples, runs, settings.path("raw_fastq"))

    out = settings.resolve(dcfg["manifest"])
    if subset:
        out = out.with_name(f"{out.stem}.subset{subset}{out.suffix}")
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(out, sep="\t", index=False)

    by_study = manifest.groupby("study_id").agg(
        samples=("sample_id", "nunique"), runs=("run_accession", "nunique"), files=("url", "size"),
        total_bytes=("bytes", "sum"),
        present_bytes=("bytes", lambda b: b[manifest.loc[b.index, "present"]].sum()),
    )
    groups = manifest.drop_duplicates("sample_id").groupby(["study_id", "group"]).size().unstack(fill_value=0)
    by_study = by_study.join(groups)
    by_study["GB"] = by_study.pop("total_bytes").map(_gb)
    by_study["to_fetch_GB"] = (by_study["GB"] - by_study.pop("present_bytes").map(_gb)).round(1)
    total = manifest["bytes"].sum()
    todo = manifest.loc[~manifest["present"], "bytes"].sum()
    data_dir = settings.path("raw_fastq").parent
    free = shutil.disk_usage(data_dir).free

    title = f"--subset {subset} ({dcfg['subset_strategy']} per group)" if subset else "full"
    print(f"\nDRY RUN ({title}): nothing downloaded.")
    print(by_study.to_string())
    print(f"\nTotal: {len(manifest)} files, {manifest['sample_id'].nunique()} samples, {_gb(total)} GB "
          f"({_gb(todo)} GB still to fetch)")
    print(f"Free disk at {data_dir}: {_gb(free)} GB -> {'OK' if free > todo else 'NOT ENOUGH SPACE'}")
    print(f"Manifest: {out.relative_to(settings.root)}")
    print("Real transfer: `python -m scz_data stream` (asks before downloading anything).")
    return status
