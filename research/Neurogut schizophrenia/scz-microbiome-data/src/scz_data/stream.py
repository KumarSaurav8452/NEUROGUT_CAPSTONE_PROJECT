"""Phase 3 stream mode: for one sample at a time
     disk check -> download (resume + MD5) -> fastp | bowtie2 per run -> record counts -> delete raw.

Each finished sample leaves data/qc_state/<sample_id>.json, so reruns skip it (idempotent, Ctrl-C safe).
results/qc/read_counts.tsv is rebuilt from those files after every sample and feeds FR-4 step 5.
"""

from __future__ import annotations

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from scz_data import qc
from scz_data.download import build_manifest, fetch_file, load_included
from scz_data.settings import Settings, get_logger

COUNT_COLUMNS = [
    "sample_id", "study_id", "group", "instrument_platform", "library_layout", "n_runs",
    "raw_reads", "clean_reads", "host_removed_reads", "host_fraction", "clean_files", "finished_at",
]


def _gb(b: float) -> float:
    return round(b / 1e9, 1)


def free_bytes(path: Path) -> int:
    """Free space on the drive holding path (the folder need not exist yet)."""
    p = Path(path).resolve()
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free


def _is_local(url: str) -> bool:
    return not url.startswith(("http://", "https://", "ftp://"))


def bytes_needed(files: pd.DataFrame, scfg: dict) -> int:
    """Worst-case extra disk this sample needs: raw files still missing (+ host-removed output if kept)."""
    remote = files[~files["url"].map(_is_local)]
    missing = int(remote.loc[~remote["present"], "bytes"].fillna(0).sum())
    raw_total = int(files["bytes"].fillna(0).sum())
    clean = int(raw_total * scfg["clean_ratio"]) if scfg["keep_clean"] else 0
    return missing + clean + int(scfg["margin_gb"] * 1e9)


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    tmp.replace(path)


def _concat(parts: list[Path], dest: Path) -> None:
    """Concatenated gzip members are a valid gzip file: merge per-run outputs without recompressing."""
    tmp = dest.with_name(dest.name + ".tmp")
    with open(tmp, "wb") as out:
        for p in parts:
            with open(p, "rb") as fh:
                shutil.copyfileobj(fh, out, 16 << 20)
    tmp.replace(dest)
    for p in parts:
        p.unlink()


def process_sample(sample: pd.Series, files: pd.DataFrame, settings: Settings, runner: qc.Runner,
                   session: requests.Session, log) -> dict:
    cfg, scfg, tcfg = settings.cfg, settings.cfg["stream"], settings.cfg["tools"]
    sid, study = sample["sample_id"], sample["study_id"]
    platform, layout = sample["instrument_platform"], sample["library_layout"]
    qc_dir = settings.resolve(scfg["qc_dir"]) / study / sid
    clean_dir = settings.resolve(scfg["clean_dir"]) / study / sid

    # 1. download (local manual files are used in place)
    for _, f in files.iterrows():
        if _is_local(f["url"]):
            continue
        how = fetch_file(f["url"], Path(f["dest"]), f["md5"], None if pd.isna(f["bytes"]) else int(f["bytes"]),
                         cfg["download"], session=session, log=log)
        size = 0 if pd.isna(f["bytes"]) else f["bytes"]
        log.info(f"{Path(f['dest']).name}: {how} ({_gb(size)} GB, MD5 ok)")

    # 2. fastp | bowtie2 per run
    totals = {"raw_reads": 0, "clean_reads": 0, "host_removed_reads": 0}
    run_outputs: dict[str, list[Path]] = {"R1": [], "R2": [], "SE": []}
    for run, rf in files.groupby("run_accession", sort=True):
        inputs = [Path(u) if _is_local(u) else Path(d) for u, d in zip(rf["url"], rf["dest"])]
        prefix = qc_dir / run
        out_prefix = clean_dir / f"{run}.partial" if scfg["keep_clean"] else None
        if out_prefix:
            clean_dir.mkdir(parents=True, exist_ok=True)
        qc_dir.mkdir(parents=True, exist_ok=True)
        body = qc.build_run_script(runner, tcfg, platform, layout, inputs, prefix, out_prefix)
        t0 = time.time()
        res = runner.run(body, prefix.with_suffix(".sh"))
        if res.returncode != 0:
            tail = Path(f"{prefix}.bowtie2.log").read_text()[-500:] if Path(f"{prefix}.bowtie2.log").exists() else ""
            raise qc.ToolError(f"{run}: QC exited {res.returncode}: {res.stderr.strip()[-500:]} {tail}")
        fp = qc.parse_fastp(Path(f"{prefix}.fastp.json"))
        bt = qc.parse_bowtie2(Path(f"{prefix}.bowtie2.log").read_text(), paired=layout == "PAIRED")
        if bt["bowtie2_input_reads"] != fp["clean_reads"]:
            raise qc.ToolError(f"{run}: bowtie2 saw {bt['bowtie2_input_reads']} reads, fastp passed {fp['clean_reads']}")
        totals["raw_reads"] += fp["raw_reads"]
        totals["clean_reads"] += fp["clean_reads"]
        totals["host_removed_reads"] += bt["host_removed_reads"]
        log.info(f"{run}: raw {fp['raw_reads']:,} -> fastp {fp['clean_reads']:,} -> host-removed "
                 f"{bt['host_removed_reads']:,} reads ({time.time() - t0:.0f}s)")
        if out_prefix:
            if layout == "PAIRED":
                run_outputs["R1"].append(Path(f"{out_prefix}.R1.fq.gz"))
                run_outputs["R2"].append(Path(f"{out_prefix}.R2.fq.gz"))
            else:
                run_outputs["SE"].append(Path(f"{out_prefix}.fq.gz"))

    # 3. one host-removed file (pair) per sample
    clean_files = []
    for key, parts in run_outputs.items():
        if parts:
            dest = clean_dir / (f"{sid}_{key}.fq.gz" if key != "SE" else f"{sid}.fq.gz")
            _concat(parts, dest)
            clean_files.append(dest.relative_to(settings.root).as_posix())

    state = {
        "sample_id": sid, "study_id": study, "group": sample["group"], "instrument_platform": platform,
        "library_layout": layout, "n_runs": int(files["run_accession"].nunique()), **totals,
        "host_fraction": round(1 - totals["host_removed_reads"] / totals["clean_reads"], 6) if totals["clean_reads"] else None,
        "clean_files": ";".join(clean_files), "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "done",
    }

    # 4. delete raw (only after the state is safely written)
    state_dir = settings.resolve(scfg["state_dir"])
    _write_json(state_dir / f"{sid}.json", state)
    (state_dir / f"{sid}.failed.json").unlink(missing_ok=True)
    if not scfg["keep_raw"]:
        for _, f in files.iterrows():
            if not _is_local(f["url"]):
                Path(f["dest"]).unlink(missing_ok=True)
        for run_dir in {Path(d).parent for d in files["dest"]}:
            if run_dir.exists() and not any(run_dir.iterdir()):
                run_dir.rmdir()
    return state


def write_read_counts(settings: Settings) -> Path:
    scfg = settings.cfg["stream"]
    states = [json.loads(p.read_text()) for p in sorted(settings.resolve(scfg["state_dir"]).glob("*.json"))]
    done = [s for s in states if s.get("status") == "done"]
    out = settings.path("qc_read_counts")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(done, columns=COUNT_COLUMNS).to_csv(out, sep="\t", index=False)
    return out


def plan(settings: Settings, studies: list[dict], subset: int | None):
    """Samples still to process (not done), their file manifest, and a printable summary."""
    samples, runs, status = load_included(settings, studies, subset)
    if samples is None:
        return None, None, status, ""
    state_dir = settings.resolve(settings.cfg["stream"]["state_dir"])
    done = {p.stem for p in state_dir.glob("*.json") if json.loads(p.read_text()).get("status") == "done"}
    todo = samples[~samples["sample_id"].isin(done)].sort_values(["total_bytes", "sample_id"])
    manifest = build_manifest(todo, runs, settings.path("raw_fastq")) if len(todo) else None
    free = free_bytes(settings.path("raw_fastq"))
    scfg = settings.cfg["stream"]
    largest = int(todo["total_bytes"].max()) if len(todo) else 0
    lines = [
        f"Stream plan ({'--subset ' + str(subset) if subset else 'all included samples'}):",
        f"  samples to process : {len(todo)} (already done: {len(samples) - len(todo)})",
        f"  total download     : {_gb(todo['total_bytes'].sum())} GB over {0 if manifest is None else len(manifest)} files",
        f"  largest sample     : {_gb(largest)} GB",
        f"  free disk now      : {_gb(free)} GB (need per sample: raw"
        f"{' + host-removed output' if scfg['keep_clean'] else ''} + {scfg['margin_gb']} GB margin)",
        f"  keep_raw={scfg['keep_raw']}  keep_clean={scfg['keep_clean']}  parallel=1",
    ]
    if scfg["keep_clean"] and len(todo):
        lines.append(f"  NOTE: keep_clean accumulates ~{_gb(todo['total_bytes'].sum() * 0.9)} GB of host-removed reads; "
                     "samples are skipped once the disk check fails.")
    return todo, manifest, status, "\n".join(lines)


def run(settings: Settings, studies: list[dict], subset: int | None, todo: pd.DataFrame, manifest: pd.DataFrame) -> dict[str, str]:
    scfg = settings.cfg["stream"]
    runner = qc.Runner(settings.cfg["tools"])
    qc.check_tools(runner, settings.cfg["tools"], settings.resolve(scfg["qc_dir"]))
    session = requests.Session()
    results: dict[str, str] = {}
    for _, sample in todo.iterrows():
        sid = sample["sample_id"]
        log = get_logger(settings, "stream", sample["study_id"])
        files = manifest[manifest["sample_id"] == sid]
        need, free = bytes_needed(files, scfg), free_bytes(settings.path("raw_fastq"))
        if free < need:
            msg = f"SKIPPED {sid}: needs {_gb(need)} GB, {_gb(free)} GB free"
            log.warning(msg)
            results[sid] = msg
            continue
        try:
            log.info(f"{sid}: start ({_gb(sample['total_bytes'])} GB, {sample['n_runs']} run(s), {free / 1e9:.1f} GB free)")
            state = process_sample(sample, files, settings, runner, session, log)
            results[sid] = f"done: {state['host_removed_reads']:,} host-removed reads"
        except KeyboardInterrupt:
            log.warning(f"{sid}: interrupted - partial downloads are kept and resume on the next run")
            write_read_counts(settings)
            raise
        except Exception as e:  # one failing sample must not stop the rest; raw files kept for a retry
            log.exception(f"{sid}: FAILED: {e}")
            _write_json(settings.resolve(scfg["state_dir"]) / f"{sid}.failed.json",
                        {"sample_id": sid, "status": "failed", "error": str(e)[:2000]})
            results[sid] = f"FAILED: {e}"
        write_read_counts(settings)
    out = write_read_counts(settings)
    print(f"\nread counts: {out.relative_to(settings.root)} - rerun `python -m scz_data filter` to apply the depth filter")
    return results
