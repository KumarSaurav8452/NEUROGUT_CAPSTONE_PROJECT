"""Phase 3b profile mode: taxonomic profiles without downloading whole samples.

Per sample:
  1 stream the first N reads of each FASTQ straight from the archive (gzip is decompressed on the fly and the
    connection is closed once N reads are in, so only ~N x 100 bytes cross the network)
  2 fastp | bowtie2 (GRCh38) host removal | MetaPhlAn 3 (mpa_v30) on the subsample
  3 keep the profile + counts; delete the subsample
Full-depth totals for the FR-4 depth filter come from archive read counts (ENA, Zhu Supp 9b) or are estimated
from file size / compressed bytes per read measured on the subsample. Studies with published profiles
(curatedMetagenomicData: Zhu_2020A) are taken as-is and no reads are fetched.
"""

from __future__ import annotations

import gzip
import json
import re
import shlex
import shutil
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from scz_data import qc
from scz_data.download import load_included
from scz_data.settings import Settings, get_logger

CHUNK = 1 << 20


# --- 1. partial FASTQ streaming ------------------------------------------------------------
class PartialFastq:
    """Collect the first n FASTQ records from a gzip stream (multi-member gzip supported)."""

    def __init__(self, n: int):
        self.n, self.lines, self.buf = n, [], b""
        self.compressed = 0      # compressed bytes received
        self.decompressed = 0    # decompressed bytes produced
        self._z = zlib.decompressobj(31)

    @property
    def compressed_for_kept(self) -> float:
        """Compressed bytes attributable to the kept records (the last chunk usually overshoots them)."""
        used = sum(len(l) + 1 for l in self.lines)
        return self.compressed * min(1.0, used / self.decompressed) if self.decompressed else 0.0

    @property
    def done(self) -> bool:
        return len(self.lines) >= 4 * self.n

    def feed(self, chunk: bytes) -> None:
        self.compressed += len(chunk)
        data = b""
        while chunk:
            data += self._z.decompress(chunk)
            if self._z.eof:  # next gzip member (BGI/concatenated files)
                chunk = self._z.unused_data
                self._z = zlib.decompressobj(31)
            else:
                chunk = b""
        self.decompressed += len(data)
        self.buf += data
        *complete, self.buf = self.buf.split(b"\n")
        need = 4 * self.n - len(self.lines)
        self.lines.extend(complete[:need])

    def records(self) -> list[tuple[bytes, bytes, bytes, bytes]]:
        lines = self.lines[: 4 * (len(self.lines) // 4)]
        recs = [tuple(lines[i : i + 4]) for i in range(0, len(lines), 4)]
        for h, s, p, q in recs:
            if not h.startswith(b"@") or not p.startswith(b"+") or len(s) != len(q):
                raise ValueError(f"malformed FASTQ record near {h[:60]!r}")
        return recs


def read_name(header: bytes) -> bytes:
    name = header[1:].split()[0]
    return re.sub(rb"/[12]$", b"", name)


class _Enough(Exception):
    pass


class _Watchdog:
    """Abort a connection that trickles: below min_kbps for longer than grace_s (a fresh one is usually fast)."""

    def __init__(self, min_kbps: float = 30, grace_s: float = 120):
        self.min_bps, self.grace = min_kbps * 1024, grace_s
        self.t0 = self.win_t = time.monotonic()
        self.win_bytes = 0

    def tick(self, n: int) -> None:
        self.win_bytes += n
        now = time.monotonic()
        if now - self.win_t >= self.grace:
            rate = self.win_bytes / (now - self.win_t)
            if rate < self.min_bps:
                raise RuntimeError(f"stalled: {rate / 1024:.1f} KB/s over {now - self.win_t:.0f}s")
            self.win_t, self.win_bytes = now, 0


def _stream_http(url, pf, session, timeout, dog):
    with session.get(url, stream=True, timeout=timeout) as r:
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} for {url}")
        for chunk in r.iter_content(CHUNK):
            pf.feed(chunk)
            dog.tick(len(chunk))
            if pf.done:
                return


def _stream_ftp(url, pf, timeout, dog):
    from ftplib import FTP
    from urllib.parse import urlparse

    u = urlparse(url)
    ftp = FTP(u.hostname, timeout=timeout[1])
    try:
        ftp.login()
        ftp.voidcmd("TYPE I")

        def cb(chunk):
            pf.feed(chunk)
            dog.tick(len(chunk))
            if pf.done:
                raise _Enough

        try:
            ftp.retrbinary(f"RETR {u.path}", cb, blocksize=CHUNK)
        except _Enough:
            pass
    finally:
        try:
            ftp.close()  # no QUIT: the server would wait for the aborted transfer
        except OSError:
            pass


# GSA serves the same tree over HTTPS and FTP; its HTTPS front end sometimes times out on the TLS handshake.
MIRRORS = [("https://download.cncb.ac.cn/gsa2/", "ftp://download.big.ac.cn/gsa2/")]


def stream_head(url: str, n: int, session: requests.Session, timeout=(30, 120), tries: int = 4,
                wait: float = 5, min_kbps: float = 30, grace_s: float = 120) -> tuple[list, float, int, bool]:
    """(records, compressed bytes for those records, bytes actually transferred, reached EOF) for the first n reads.

    Retries transient failures and trickling connections, then falls back to a known mirror of the same file.
    """
    candidates = [url] + [url.replace(a, b) for a, b in MIRRORS if url.startswith(a)]
    last = None
    for u in candidates:
        for attempt in range(tries):
            pf = PartialFastq(n)
            dog = _Watchdog(min_kbps, grace_s)
            try:
                (_stream_ftp(u, pf, timeout, dog) if u.startswith("ftp://") else _stream_http(u, pf, session, timeout, dog))
                return pf.records(), pf.compressed_for_kept, pf.compressed, not pf.done
            # ValueError: a garbled transfer (27 Oct: one malformed record; the same file re-read cleanly)
            except (requests.RequestException, OSError, EOFError, RuntimeError, ValueError) as e:
                last = e
                time.sleep(wait * (attempt + 1))
    raise RuntimeError(f"could not stream {url} (incl. mirrors): {last}")


def sra_head(run: str, n: int, sra: dict, out_dir: Path) -> tuple[list, float, int, bool]:
    """stream_head's result for the first n reads of an SRA run, read with fastq-dump from NCBI's public AWS copy.

    fastq-dump fetches only the blobs holding those reads (measured: 39 MB for 300 k Thirion reads, as from ENA).
    The bucket is AWS Open Data: anonymous HTTPS, no account, nothing billed to the downloader.
    """
    runner = qc.Runner(sra["tools"])
    out = out_dir / f"{run}.sra.fq.gz"
    url = sra["url"].format(run=run)
    limit = float(sra.get("timeout_s", 240))
    # `timeout -s KILL` ends fastq-dump inside WSL: it ignores SIGTERM, and killing wsl.exe on the Windows side
    # left hung copies downloading hundreds of MB in the background (27 Oct)
    body = (f"timeout -s KILL {int(limit) - 20} {qc.sh_word(sra['bin'])} -X {int(n)} --stdout {shlex.quote(url)} 2> {runner.q(out_dir / (run + '.sra.log'))}"
            f" | gzip -1 > {runner.q(out)}\n")
    try:
        res = runner.run(body, out_dir / f"{run}.sra.sh", timeout=limit)
        if res.returncode != 0:
            raise RuntimeError(f"fastq-dump exit {res.returncode}: {(res.stderr or '')[-300:]}")
        pf = PartialFastq(n)
        pf.feed(out.read_bytes())
        if not pf.lines:
            raise RuntimeError(f"fastq-dump returned no reads for {run}")
        return pf.records(), pf.compressed_for_kept, pf.compressed, not pf.done
    finally:
        out.unlink(missing_ok=True)


def write_fastq(records, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with gzip.open(tmp, "wb", compresslevel=1) as fh:
        for rec in records:
            fh.write(b"\n".join(rec) + b"\n")
    tmp.replace(path)


def fetch_subsample(sample: pd.Series, runs: pd.DataFrame, n: int, out_dir: Path, session: requests.Session,
                    sra: dict | None = None) -> dict:
    """First n reads (pairs) of the sample, taking further runs only if the first is shorter than n.

    With `sra` (single-end studies listed in profile.sra_aws), reads come from NCBI's AWS copy first and the
    archive FASTQ is the fallback.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paired = sample["library_layout"] == "PAIRED"
    got: dict[str, list] = {"R1": [], "R2": []} if paired else {"SE": []}
    comp = {k: 0.0 for k in got}       # compressed bytes attributable to kept reads
    transferred = 0
    full_bytes = {k: 0 for k in got}
    sra_errors: list[str] = []
    sources: set[str] = set()
    for run in str(sample["run_ids"]).split(";"):
        r = runs.loc[runs["run_accession"] == run].iloc[0]
        urls = str(r["fastq_urls"]).split(";")
        sizes = [int(b) if b else 0 for b in str(r["fastq_bytes"]).split(";")]
        size_of = dict(zip(urls, sizes))
        if paired:
            r1, r2 = qc.pair_files(urls)
            files = {"R1": r1, "R2": r2}
        else:
            files = {"SE": urls[0]}
        need = n - len(next(iter(got.values())))
        for k, url in files.items():
            full_bytes[k] += size_of[url]
            if need > 0:
                recs = None
                # a run that hangs on AWS hangs again (27 Oct: every timeout repeated on the retry), so tries: 1
                use_aws = sra and not paired and run.startswith(tuple(sra.get("run_prefixes") or [""]))
                for attempt in range(int(sra.get("tries", 1)) if use_aws else 0):
                    try:
                        recs, c, sent, _ = sra_head(run, need, sra, out_dir)
                        break
                    except Exception as e:  # noqa: BLE001 - any failure falls back to the archive FASTQ
                        sra_errors.append(f"{run} (try {attempt + 1}): {e}"[:300])
                        time.sleep(10)
                if recs is None:
                    recs, c, sent, _ = stream_head(url, need, session)
                    sources.add("archive")
                else:
                    sources.add("sra_aws")
                got[k].extend(recs)
                comp[k] += c
                transferred += sent
    if paired:
        if len(got["R1"]) != len(got["R2"]):
            raise ValueError(f"R1/R2 subsample lengths differ: {len(got['R1'])} vs {len(got['R2'])}")
        bad = next((i for i, (a, b) in enumerate(zip(got["R1"], got["R2"])) if read_name(a[0]) != read_name(b[0])), None)
        if bad is not None:
            raise ValueError(f"R1/R2 out of sync at read {bad}: {got['R1'][bad][0][:50]!r} / {got['R2'][bad][0][:50]!r}")
    paths = {}
    for k, recs in got.items():
        paths[k] = out_dir / f"{sample['sample_id']}.sub.{k}.fq.gz"
        write_fastq(recs, paths[k])
    reads = sum(len(v) for v in got.values())
    first = next(iter(got))
    per_read = comp[first] / max(1, len(got[first]))
    # Full-depth estimate from file size: total compressed bytes / compressed bytes per read on this subsample.
    est = int(sum(full_bytes[k] / (comp[k] / len(got[k])) for k in got if got[k] and comp[k]))
    return {"paths": paths, "sub_reads": reads, "sub_bytes": transferred,
            "bytes_per_read": round(per_read, 1), "size_estimated_reads": est,
            "source": "+".join(sorted(sources)) or "archive", "sra_errors": sra_errors}


# --- 2. QC + host removal + MetaPhlAn --------------------------------------------------------
def build_profile_script(runner: qc.Runner, cfg: dict, platform: str, layout: str, paths: dict, work: Path,
                         sid: str) -> str:
    tcfg, pcfg = cfg["tools"], cfg["profile"]
    m = pcfg["metaphlan"]
    t = int(tcfg["threads"])
    q = runner.q
    opts = qc.fastp_options(platform, layout, tcfg)
    idx = qc.sh_word(tcfg["host_index"])
    head = (
        'alias_dir=$(mktemp -d)\n'
        'trap \'rm -rf "$alias_dir"\' EXIT\n'
        f'ln -s {q(work)} "$alias_dir/w"\n'   # bowtie2 / MetaPhlAn wrappers break on spaces in paths
        f'rm -f "$alias_dir/w/{sid}.bt2.bz2" "$alias_dir/w/{sid}.profile.txt"\n'
    )
    fp = f"fastp --stdout -w {min(t, 16)} {opts} -j \"$alias_dir/w/{sid}.fastp.json\" -h \"$alias_dir/w/{sid}.fastp.html\""
    bt2 = f"bowtie2 -p {t} {pcfg['bowtie2_args']} -x {idx}"
    if layout == "PAIRED":
        qcmd = (f'{fp} -i {q(paths["R1"])} -I {q(paths["R2"])} 2> "$alias_dir/w/{sid}.fastp.log" \\\n'
                f'  | {bt2} --interleaved - --un-conc-gz "$alias_dir/w/{sid}.hr.R%.fq.gz" -S /dev/null '
                f'2> "$alias_dir/w/{sid}.bowtie2.log"\n')
        mp_in = f'"$alias_dir/w/{sid}.hr.R1.fq.gz,$alias_dir/w/{sid}.hr.R2.fq.gz"'
    else:
        qcmd = (f'{fp} -i {q(paths["SE"])} 2> "$alias_dir/w/{sid}.fastp.log" \\\n'
                f'  | {bt2} -U - --un-gz "$alias_dir/w/{sid}.hr.fq.gz" -S /dev/null 2> "$alias_dir/w/{sid}.bowtie2.log"\n')
        mp_in = f'"$alias_dir/w/{sid}.hr.fq.gz"'
    mp = (f'PATH={qc.sh_word(m["path_prepend"])}:"$PATH" metaphlan {mp_in} --input_type fastq '
          f'--bowtie2db {qc.sh_word(m["bowtie2db"])} --index {m["index"]} --nproc {t} {m.get("args", "")} '
          f'--bowtie2out "$alias_dir/w/{sid}.bt2.bz2" -o "$alias_dir/w/{sid}.profile.txt" '
          f'2> "$alias_dir/w/{sid}.metaphlan.log"\n')
    return head + qcmd + mp


def parse_metaphlan(text: str) -> tuple[pd.DataFrame, float]:
    """(clade_name, relative_abundance) rows, and the unclassified fraction (0-1)."""
    rows = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        rows.append((parts[0], float(parts[2])))
    df = pd.DataFrame(rows, columns=["clade_name", "relative_abundance"])
    unk = df.loc[df["clade_name"].isin(["UNKNOWN", "UNCLASSIFIED", "unclassified"]), "relative_abundance"].sum()
    return df, round(unk / 100, 6)


def species_table(profile: pd.DataFrame) -> pd.Series:
    """Species-level rows (no strain level), renormalised to 100 over classified reads (cMD convention)."""
    sp = profile[profile["clade_name"].str.contains(r"\|s__", regex=True) & ~profile["clade_name"].str.contains(r"\|t__")]
    s = sp.set_index("clade_name")["relative_abundance"]
    return s * (100 / s.sum()) if s.sum() > 0 else s


# --- orchestration ---------------------------------------------------------------------------
def _n_for(cfg: dict, study: str) -> int:
    r = cfg["profile"]["reads_per_sample"]
    return int(r.get(study, r["default"]))


def plan(settings: Settings, studies: list[dict], subset: int | None):
    cfg = settings.cfg
    ext = cfg["profile"].get("external_profiles", {})
    wanted = [s for s in studies if s["study_id"] not in ext]
    samples, runs, status = load_included(settings, wanted, subset)
    for sid in ext:
        if any(s["study_id"] == sid for s in studies):
            status[sid] = f"external profiles: {ext[sid]['source']}"
    if samples is None:
        return None, None, status, ""
    order = {s: i for i, s in enumerate(cfg["profile"]["study_order"])}
    state_dir = settings.resolve(cfg["profile"]["state_dir"])
    done = {p.stem for p in state_dir.glob("*.json") if json.loads(p.read_text()).get("status") == "done"}
    samples = samples.assign(_o=samples["study_id"].map(order).fillna(99), _n=samples["study_id"].map(lambda s: _n_for(cfg, s)))
    todo = samples[~samples["sample_id"].isin(done)].sort_values(["_o", "group", "sample_id"])
    bpr = cfg["profile"]["bytes_per_read_guess"]
    files_per = todo["library_layout"].map({"PAIRED": 2}).fillna(1)
    est_gb = float((todo["_n"] * files_per * bpr).sum() / 1e9)
    by = todo.groupby("study_id", sort=False).agg(samples=("sample_id", "size"), reads_per_file=("_n", "first"))
    by["est_GB"] = (todo.groupby("study_id", sort=False).apply(
        lambda g: (g["_n"] * g["library_layout"].map({"PAIRED": 2}).fillna(1) * bpr).sum() / 1e9)).round(1)
    lines = [
        f"Profile plan ({'--subset ' + str(subset) if subset else 'all included samples'}):",
        by.to_string(),
        f"  samples to profile : {len(todo)} (already done: {len(samples) - len(todo)})",
        f"  estimated transfer : {est_gb:.1f} GB (~{est_gb / 0.25 * 1e3 / 3600:.0f} h at 0.25 MB/s)",
        f"  disk               : one subsample at a time (<1 GB); profiles kept, reads deleted",
        "  external           : " + ("; ".join(f"{k} <- {v['source']}" for k, v in ext.items()) or "none"),
    ]
    return todo.drop(columns=["_o", "_n"]), runs, status, "\n".join(lines)


def _known_total_reads(sample: pd.Series, settings: Settings) -> tuple[int | None, str]:
    """Full-depth single-read count from the archive (ENA spots x mates), else from the paper's supplement."""
    rc = pd.to_numeric(sample.get("archive_read_count"), errors="coerce")
    if pd.notna(rc):
        return int(rc) * (2 if sample["library_layout"] == "PAIRED" else 1), "archive read_count"
    pub = pd.to_numeric(sample.get("published_reads"), errors="coerce")
    if pd.notna(pub):
        return int(pub), "published read count (paper supplement)"
    return None, ""


def process_sample(sample, runs, settings: Settings, runner: qc.Runner, sub: dict, log) -> dict:
    cfg, pcfg = settings.cfg, settings.cfg["profile"]
    sid, study = sample["sample_id"], sample["study_id"]
    work = settings.resolve(pcfg["sub_dir"]) / sid
    pdir = settings.resolve(pcfg["profile_dir"]) / study
    pdir.mkdir(parents=True, exist_ok=True)
    body = build_profile_script(runner, cfg, sample["instrument_platform"], sample["library_layout"], sub["paths"], work, sid)
    t0 = time.time()
    res = runner.run(body, pdir / f"{sid}.sh")
    if res.returncode != 0:
        tails = [f.read_text()[-400:] for f in (work / f"{sid}.metaphlan.log", work / f"{sid}.fastp.log") if f.exists()]
        raise qc.ToolError(f"profile script exited {res.returncode}: {res.stderr.strip()[-400:]} {' | '.join(tails)}")
    fp = qc.parse_fastp(work / f"{sid}.fastp.json")
    bt = qc.parse_bowtie2((work / f"{sid}.bowtie2.log").read_text(), paired=sample["library_layout"] == "PAIRED")
    if bt["bowtie2_input_reads"] != fp["clean_reads"]:
        raise qc.ToolError(f"bowtie2 saw {bt['bowtie2_input_reads']} reads, fastp passed {fp['clean_reads']}")
    profile_txt = (work / f"{sid}.profile.txt").read_text()
    _, unclassified = parse_metaphlan(profile_txt)
    for f in ("profile.txt", "fastp.json", "bowtie2.log", "metaphlan.log"):
        shutil.copy2(work / f"{sid}.{f}", pdir / f"{sid}.{f}")
    keep_frac = bt["host_removed_reads"] / fp["raw_reads"] if fp["raw_reads"] else 0
    total, method = _known_total_reads(sample, settings)
    if total is None:
        total, method = sub["size_estimated_reads"], "file size / subsample bytes per read"
    state = {
        "sample_id": sid, "study_id": study, "group": sample["group"],
        "instrument_platform": sample["instrument_platform"], "library_layout": sample["library_layout"],
        "sub_raw_reads": fp["raw_reads"], "sub_clean_reads": fp["clean_reads"], "sub_host_removed_reads": bt["host_removed_reads"],
        "host_fraction": round(1 - bt["host_removed_reads"] / fp["clean_reads"], 6) if fp["clean_reads"] else None,
        "unclassified_frac": unclassified, "sub_bytes": sub["sub_bytes"], "bytes_per_read": sub["bytes_per_read"],
        "est_total_reads": int(total), "est_method": method,
        "est_host_removed_reads": int(total * keep_frac),
        "profile": (pdir / f"{sid}.profile.txt").relative_to(settings.root).as_posix(),
        "seconds_qc_profile": round(time.time() - t0), "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "done",
    }
    state_dir = settings.resolve(pcfg["state_dir"])
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{sid}.json").write_text(json.dumps(state, indent=1))
    (state_dir / f"{sid}.failed.json").unlink(missing_ok=True)
    shutil.rmtree(work, ignore_errors=True)
    return state


def profile_qc(done: list[dict], settings: Settings) -> list[dict]:
    """Per-sample plausibility checks (an exit code is not proof of a good result)."""
    f = settings.cfg["profile"]["qc_flags"]
    rows, seen = [], {}
    for s in done:
        prof, _ = parse_metaphlan((settings.root / s["profile"]).read_text())
        n_species = int(species_table(prof).gt(0).sum())
        kept = (s["sub_host_removed_reads"] / s["sub_raw_reads"]
                if s.get("sub_raw_reads") and s.get("sub_host_removed_reads") is not None else None)
        flags = []
        if n_species < f["min_species"]:
            flags.append(f"species<{f['min_species']}")
        if s.get("host_fraction") is not None and s["host_fraction"] > f["max_host_fraction"]:
            flags.append(f"host>{f['max_host_fraction']:.0%}")
        if kept is not None and kept < f["min_clean_frac_of_subsample"]:
            flags.append(f"kept<{f['min_clean_frac_of_subsample']:.0%}")
        # identical numbers in different samples -> a file is being reused
        fingerprint = (s.get("sub_raw_reads"), s.get("sub_host_removed_reads"), s.get("unclassified_frac"))
        if fingerprint in seen:
            flags.append(f"identical_to:{seen[fingerprint]}")
        seen.setdefault(fingerprint, s["sample_id"])
        rows.append({"sample_id": s["sample_id"], "study_id": s["study_id"], "group": s["group"],
                     "sub_raw_reads": s.get("sub_raw_reads"), "sub_host_removed_reads": s.get("sub_host_removed_reads"),
                     "host_fraction": s.get("host_fraction"), "unclassified_frac": s.get("unclassified_frac"),
                     "n_species": n_species, "seconds": s.get("seconds_qc_profile"), "flags": ";".join(flags)})
    return rows


def status(settings: Settings, studies: list[dict]) -> str:
    """done + failed + pending == total per study, plus flagged samples (runbook Phase 5 checks)."""
    cfg = settings.cfg
    ext = cfg["profile"].get("external_profiles", {})
    samples, _, _ = load_included(settings, [s for s in studies if s["study_id"] not in ext], None)
    state_dir = settings.resolve(cfg["profile"]["state_dir"])
    states = {}
    for p in state_dir.glob("*.json"):
        d = json.loads(p.read_text())
        if d["status"] == "done" or d["sample_id"] not in states:  # a later success outranks an old failure
            states[d["sample_id"]] = d["status"]
    if samples is None:
        return "nothing to profile"
    samples = samples.assign(state=samples["sample_id"].map(states).fillna("pending"))
    tab = samples.groupby(["study_id", "state"]).size().unstack(fill_value=0)
    for col in ("done", "failed", "pending"):
        if col not in tab:
            tab[col] = 0
    tab = tab[["done", "failed", "pending"]]
    tab["total"] = tab.sum(axis=1)
    lines = ["Profile status (done + failed + pending = total):", tab.to_string(),
             f"ALL: {int(tab['done'].sum())} done, {int(tab['failed'].sum())} failed, "
             f"{int(tab['pending'].sum())} pending of {int(tab['total'].sum())}"]
    for sid in ext:
        lines.append(f"{sid}: external profiles ({ext[sid]['source']})")
    qc_path = settings.resolve(cfg["profile"]["profile_dir"]) / "profile_qc.tsv"
    if qc_path.exists():
        q = pd.read_csv(qc_path, sep="\t", keep_default_na=False)
        flagged = q[q["flags"] != ""]
        lines.append(f"QC flags: {len(flagged)} of {len(q)} profiled samples flagged")
        if len(flagged):
            lines.append(flagged[["sample_id", "n_species", "host_fraction", "unclassified_frac", "flags"]].to_string(index=False))
        if len(q) and pd.to_numeric(q["seconds"], errors="coerce").notna().any():
            lines.append(f"median QC+MetaPhlAn time: {pd.to_numeric(q['seconds'], errors='coerce').median():.0f} s/sample; "
                         f"species per sample: median {q['n_species'].median():.0f}, min {q['n_species'].min()}")
    failed = [json.loads(p.read_text()) for p in state_dir.glob("*.failed.json")]
    for f in failed:
        lines.append(f"FAILED {f['sample_id']}: {f['error'][:160]}")
    return "\n".join(lines)


def write_outputs(settings: Settings) -> None:
    """Merged species table (+ external profiles), unclassified fractions and read estimates for FR-4."""
    cfg = settings.cfg
    pcfg = cfg["profile"]
    states = [json.loads(p.read_text()) for p in sorted(settings.resolve(pcfg["state_dir"]).glob("*.json"))]
    done = [s for s in states if s.get("status") == "done"]
    cols = {}
    for s in done:
        prof, _ = parse_metaphlan((settings.root / s["profile"]).read_text())
        cols[s["sample_id"]] = species_table(prof)
    ext_estimates = []
    for study, ext in pcfg.get("external_profiles", {}).items():
        fp = settings.path("filtered") / f"{study}.samples.tsv"
        ra = settings.resolve(ext["relative_abundance"])
        if not (fp.exists() and ra.exists()):
            continue
        samples = pd.read_csv(fp, sep="\t", dtype=str)
        key_to_id = dict(zip(samples[ext["key"]], samples["sample_id"]))
        # No reads processed here: depth from the archive count (Zhu files are host-removed by the submitters).
        for _, smp in samples[samples["included"].str.lower() == "true"].iterrows():
            total, method = _known_total_reads(smp, settings)
            if total is not None:
                ext_estimates.append({"sample_id": smp["sample_id"], "study_id": study, "group": smp["group"],
                                      "est_total_reads": total, "est_method": method + " (external profile)",
                                      "host_fraction": None, "est_host_removed_reads": total, "sub_raw_reads": None})
        tab = pd.read_csv(ra, sep="\t", index_col=0)
        tab = tab[tab.index.str.contains(r"\|s__", regex=True) & ~tab.index.str.contains(r"\|t__", regex=True)]
        for col in tab.columns:
            if col in key_to_id:
                v = tab[col]
                cols[key_to_id[col]] = v * (100 / v.sum()) if v.sum() > 0 else v
    out_dir = settings.resolve(pcfg["profile_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    if cols:
        merged = pd.DataFrame(cols).fillna(0.0)
        merged.index.name = "clade_name"
        merged.sort_index().to_csv(out_dir / "metaphlan_merged.tsv", sep="\t", float_format="%.6g")
        # One table per study as well (same layout; only species seen in that study are kept).
        by_study = out_dir / "by_study"
        by_study.mkdir(exist_ok=True)
        studies = merged.columns.str.split("__").str[0]
        for study in sorted(set(studies)):
            sub = merged.loc[:, studies == study]
            sub = sub[(sub > 0).any(axis=1)]
            sub.sort_index().to_csv(by_study / f"{study}.species.tsv", sep="\t", float_format="%.6g")

    # All taxonomic levels as MetaPhlAn reports them (same layout as merge_metaphlan_tables.py), our samples only.
    all_levels = {}
    for s in done:
        prof, _ = parse_metaphlan((settings.root / s["profile"]).read_text())
        all_levels[s["sample_id"]] = prof.set_index("clade_name")["relative_abundance"]
    if all_levels:
        tab = pd.DataFrame(all_levels).fillna(0.0)
        tab.index.name = "clade_name"
        tab.sort_index().to_csv(out_dir / "metaphlan_merged_all_levels.tsv", sep="\t", float_format="%.6g")

    # Counts published after a sample was profiled (e.g. Xu ST1, added 28 Oct) replace its file-size estimate:
    # full-depth total from the paper x the kept fraction measured on our subsample.
    published = {}
    for fp in settings.path("filtered").glob("*.samples.tsv"):
        f = pd.read_csv(fp, sep="\t")
        if "published_reads" in f:
            published.update(f.dropna(subset=["published_reads"]).set_index("sample_id")["published_reads"].to_dict())
    for s in done:
        if s["sample_id"] in published and s["est_method"].startswith("file size") and s.get("sub_raw_reads"):
            total = int(published[s["sample_id"]])
            s["est_total_reads"], s["est_method"] = total, "published read count (paper supplement)"
            s["est_host_removed_reads"] = int(total * s["sub_host_removed_reads"] / s["sub_raw_reads"])

    pd.DataFrame(profile_qc(done, settings)).to_csv(out_dir / "profile_qc.tsv", sep="\t", index=False)
    pd.DataFrame([{"sample_id": s["sample_id"], "unclassified_frac": s["unclassified_frac"]} for s in done],
                 columns=["sample_id", "unclassified_frac"]).to_csv(settings.path("unclassified"), sep="\t", index=False)
    est = pd.DataFrame([{k: s[k] for k in ("sample_id", "study_id", "group", "est_total_reads", "est_method",
                                           "host_fraction", "est_host_removed_reads", "sub_raw_reads")} for s in done]
                       + ext_estimates,
                       columns=["sample_id", "study_id", "group", "est_total_reads", "est_method", "host_fraction",
                                "est_host_removed_reads", "sub_raw_reads"])
    settings.path("read_estimates").parent.mkdir(parents=True, exist_ok=True)
    est.to_csv(settings.path("read_estimates"), sep="\t", index=False)


def check_metaphlan(runner: qc.Runner, cfg: dict, scratch: Path) -> str:
    m = cfg["profile"]["metaphlan"]
    db = qc.sh_word(m["bowtie2db"])
    body = (f'PATH={qc.sh_word(m["path_prepend"])}:"$PATH"\n'
            f'ls {db}/{m["index"]}.rev.2.bt2 {db}/{m["index"]}.pkl >/dev/null 2>&1 && echo index=ok || echo index=missing\n'
            'metaphlan --version 2>&1 | tail -1\n')
    res = runner.run(body, scratch / "check_metaphlan.sh", timeout=300)
    if "index=ok" not in res.stdout or "MetaPhlAn" not in res.stdout:
        raise qc.ToolError(f"MetaPhlAn not ready: {res.stdout.strip()} {res.stderr.strip()[-300:]}")
    return res.stdout.strip().splitlines()[-1]


def _wait_for_tools(runner, cfg, scratch, log) -> None:
    deadline = time.time() + 60 * cfg["profile"].get("wait_for_tools_min", 0)
    while True:
        try:
            qc.check_tools(runner, cfg["tools"], scratch)
            log.info(f"tools ready ({check_metaphlan(runner, cfg, scratch)})")
            return
        except qc.ToolError as e:
            if time.time() > deadline:
                raise
            log.info(f"waiting for tools (downloads continue meanwhile): {str(e)[:120]}")
            time.sleep(120)


def fetch_job(sample: dict, run_rows: list[dict], n: int, out_dir: str, sra: dict | None = None) -> dict:
    """Fetch one subsample (in a worker process). Reuses a complete subsample left by an earlier run."""
    d = Path(out_dir)
    marker = d / "subsample.json"
    if marker.exists():
        sub = json.loads(marker.read_text())
        sub["paths"] = {k: Path(v) for k, v in sub["paths"].items()}
        if all(p.exists() for p in sub["paths"].values()):
            return sub
    sub = fetch_subsample(pd.Series(sample), pd.DataFrame(run_rows), n, d, requests.Session(), sra)
    marker.write_text(json.dumps({**sub, "paths": {k: str(v) for k, v in sub["paths"].items()}}))
    return sub


def _sra_for(cfg: dict, study: str) -> dict | None:
    sra = cfg["profile"].get("sra_aws") or {}
    if study not in sra.get("studies", []):
        return None
    return {"tools": cfg["tools"], "url": sra["url"], "bin": sra["bin"], "timeout_s": sra.get("timeout_s", 240),
            "tries": sra.get("tries", 1), "run_prefixes": sra.get("run_prefixes")}


def run(settings: Settings, todo: pd.DataFrame, runs: pd.DataFrame) -> dict[str, str]:
    cfg = settings.cfg
    runner = qc.Runner(cfg["tools"])
    scratch = settings.resolve(cfg["profile"]["profile_dir"])
    scratch.mkdir(parents=True, exist_ok=True)
    sub_root = settings.resolve(cfg["profile"]["sub_dir"])
    results: dict[str, str] = {}
    rows = [r for _, r in todo.iterrows()]
    ahead = max(1, int(cfg["profile"].get("prefetch", 1)))
    workers = max(1, int(cfg["profile"].get("fetch_workers", 1)))

    def submit(pool, sample):
        mine = runs[runs["run_accession"].isin(str(sample["run_ids"]).split(";"))]
        return pool.submit(fetch_job, sample.to_dict(), mine.to_dict("records"), _n_for(cfg, sample["study_id"]),
                           str(sub_root / sample["sample_id"]), _sra_for(cfg, sample["study_id"]))

    # Downloads run up to `ahead` samples in front of QC/MetaPhlAn, `workers` at a time: the network is the
    # bottleneck, and the archives cap each connection (ENA: 0.30 MB/s for one, 0.58 MB/s for three together).
    # Each download runs in its own short-lived process: holding ~1 M reads per sample in one long-lived process
    # leaked committed memory on Windows (14 GB after ~100 samples, backed by a growing page file on C:).
    with ProcessPoolExecutor(workers, max_tasks_per_child=1) as pool:
        futures = [submit(pool, r) for r in rows[:ahead]]
        _wait_for_tools(runner, cfg, scratch, get_logger(settings, "profile", "_tools"))
        for i, sample in enumerate(rows):
            sid = sample["sample_id"]
            log = get_logger(settings, "profile", sample["study_id"])
            cur = futures[i]
            if i + ahead < len(rows):
                futures.append(submit(pool, rows[i + ahead]))
            try:
                t0 = time.time()
                sub = cur.result()
                log.info(f"{sid}: fetched {sub['sub_reads']:,} reads ({sub['sub_bytes'] / 1e6:.0f} MB, "
                         f"{sub['bytes_per_read']} B/read, {sub.get('source', 'archive')}) in {time.time() - t0:.0f}s wait")
                for err in sub.get("sra_errors", []):
                    log.warning(f"{sid}: AWS copy failed, used the archive FASTQ: {err}")
                st = process_sample(sample, runs, settings, runner, sub, log)
                msg = (f"{sid}: host {st['host_fraction']:.2%}, unclassified {st['unclassified_frac']:.1%}, "
                       f"est. {st['est_host_removed_reads'] / 1e6:.1f} M host-removed reads ({st['est_method']}), "
                       f"QC+MetaPhlAn {st['seconds_qc_profile']}s")
                log.info(msg)
                results[sid] = "done"
            except KeyboardInterrupt:
                pool.shutdown(wait=False, cancel_futures=True)  # don't sit through queued downloads
                write_outputs(settings)
                raise
            except Exception as e:
                log.exception(f"{sid}: FAILED: {e}")
                state_dir = settings.resolve(cfg["profile"]["state_dir"])
                state_dir.mkdir(parents=True, exist_ok=True)
                (state_dir / f"{sid}.failed.json").write_text(json.dumps({"sample_id": sid, "status": "failed", "error": str(e)[:2000]}))
                # keep the subsample + logs: a rerun reuses it (bandwidth is the scarce resource)
                results[sid] = f"FAILED: {e}"
            if (i + 1) % 5 == 0:
                write_outputs(settings)
    write_outputs(settings)
    return results
