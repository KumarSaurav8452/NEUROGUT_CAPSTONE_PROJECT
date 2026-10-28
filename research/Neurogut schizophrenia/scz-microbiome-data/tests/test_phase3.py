"""Phase 3 tests: resumable MD5 download, QC command building / log parsing, stream orchestration.

No real tools or archives are touched: files come from a local HTTP server and fastp/bowtie2 are faked.
"""

import gzip
import hashlib
import json
import shlex
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd
import pytest
import yaml

from scz_data import qc, stream
from scz_data.download import ChecksumError, build_manifest, fetch_file
from scz_data.settings import Settings

REPO = Path(__file__).resolve().parents[1]
DCFG = {"max_tries": 3, "chunk_mb": 1, "retry_base_s": 0}


# --- local HTTP server with Range support ---------------------------------------------------
class _Files:
    blobs: dict[str, bytes] = {}
    corrupt: set[str] = set()
    hits: dict[str, int] = {}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        name = self.path.lstrip("/")
        _Files.hits[name] = _Files.hits.get(name, 0) + 1
        if name not in _Files.blobs:
            self.send_response(404)
            self.end_headers()
            return
        data = _Files.blobs[name]
        if name in _Files.corrupt:
            data = b"X" + data[1:]
        start = 0
        rng = self.headers.get("Range")
        if rng:
            start = int(rng.split("=")[1].split("-")[0])
            self.send_response(206)
        else:
            self.send_response(200)
        body = data[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _blob(name: str, size: int = 50_000) -> tuple[str, str, int]:
    data = gzip.compress((name * (size // len(name) + 1)).encode()[:size])
    _Files.blobs[name] = data
    return name, hashlib.md5(data).hexdigest(), len(data)


# --- download ------------------------------------------------------------------------------
def test_fetch_file_download_present_and_resume(server, tmp_path):
    name, md5, size = _blob("a_1.fastq.gz")
    dest = tmp_path / "run" / name
    assert fetch_file(f"{server}/{name}", dest, md5, size, DCFG) == "downloaded"
    assert dest.read_bytes() == _Files.blobs[name]
    assert fetch_file(f"{server}/{name}", dest, md5, size, DCFG) == "present"

    # resume: a .part holding the first half is completed via a Range request
    dest.unlink()
    part = dest.with_name(dest.name + ".part")
    part.write_bytes(_Files.blobs[name][: size // 2])
    assert fetch_file(f"{server}/{name}", dest, md5, size, DCFG) == "downloaded"
    assert dest.read_bytes() == _Files.blobs[name] and not part.exists()


def test_fetch_file_md5_mismatch_retries_then_fails(server, tmp_path):
    name, md5, size = _blob("bad_1.fastq.gz")
    _Files.corrupt.add(name)
    _Files.hits.pop(name, None)
    with pytest.raises(ChecksumError):
        fetch_file(f"{server}/{name}", tmp_path / name, md5, size, DCFG)
    assert _Files.hits[name] == 3  # max_tries
    assert not (tmp_path / name).exists() and not (tmp_path / (name + ".part")).exists()
    _Files.corrupt.discard(name)


# --- QC commands -----------------------------------------------------------------------------
TCFG = yaml.safe_load((REPO / "config" / "config.yaml").read_text())["tools"]


@pytest.mark.parametrize(
    "paths, expected",
    [
        (["x/ERR1.fastq.gz", "x/ERR1_1.fastq.gz", "x/ERR1_2.fastq.gz"], ("x/ERR1_1.fastq.gz", "x/ERR1_2.fastq.gz")),
        (["CRR1_f1.fastq.gz", "CRR1_r2.fastq.gz"], ("CRR1_f1.fastq.gz", "CRR1_r2.fastq.gz")),
        (["w.rmhost.2.fq.gz", "w.rmhost.1.fq.gz"], ("w.rmhost.1.fq.gz", "w.rmhost.2.fq.gz")),
        (["wmb-1_combine_R1.fq.gz", "wmb-1_combine_R2.fq.gz"], ("wmb-1_combine_R1.fq.gz", "wmb-1_combine_R2.fq.gz")),
        (["ERR9.fastq.gz"], ("ERR9.fastq.gz", None)),
    ],
)
def test_pair_files(paths, expected):
    assert qc.pair_files(paths) == expected


def test_platform_aware_fastp_options():
    assert "--detect_adapter_for_pe" in qc.fastp_options("ILLUMINA", "PAIRED", TCFG)
    bgi = qc.fastp_options("BGISEQ", "PAIRED", TCFG)
    assert "--adapter_sequence AAGTCGGAGGCCAAGCGGTCTTAGGAAGACAA" in bgi and "--adapter_sequence_r2" in bgi
    ion = qc.fastp_options("ION_TORRENT", "SINGLE", TCFG)
    assert "--disable_trim_poly_g" in ion and "--length_required 50" in ion
    with pytest.raises(ValueError):
        qc.fastp_options("ION_TORRENT", "PAIRED", TCFG)


def test_build_run_script_paired_single_and_count_only(tmp_path):
    r = qc.Runner({**TCFG, "runner": "native"})
    pe = qc.build_run_script(r, TCFG, "BGISEQ", "PAIRED", [tmp_path / "s.1.fq.gz", tmp_path / "s.2.fq.gz"],
                             tmp_path / "qc" / "RUN", tmp_path / "clean" / "RUN.partial")
    assert "--stdout" in pe and "--interleaved -" in pe and "-S /dev/null" in pe
    # bowtie2 output goes through a space-free symlink (the wrapper breaks on spaces)
    assert '--un-conc-gz "$alias_dir/out/RUN.partial.R%.fq.gz"' in pe and "ln -s" in pe and "trap" in pe
    se = qc.build_run_script(r, TCFG, "ION_TORRENT", "SINGLE", [tmp_path / "s.fastq.gz"], tmp_path / "RUN", None)
    assert "-U -" in se and "--un" not in se and "--disable_trim_poly_g" in se
    assert '"$HOME/scz-ref/GRCh38_noalt_as"' in se
    with pytest.raises(ValueError):
        qc.build_run_script(r, TCFG, "ION_TORRENT", "SINGLE", [Path("a"), Path("b")], tmp_path / "RUN", None)


def test_wsl_path_conversion():
    r = qc.Runner({**TCFG, "runner": "wsl"})
    p = r.path(Path("C:/Neurogut schizophrenia/data/x.fq.gz"))
    assert p == "/mnt/c/Neurogut schizophrenia/data/x.fq.gz"
    assert r.q(Path("C:/a b/c")) == "'/mnt/c/a b/c'"


BT2_PE = """1000 reads; of these:
  1000 (100.00%) were paired; of these:
    900 (90.00%) aligned concordantly 0 times
    95 (9.50%) aligned concordantly exactly 1 time
    5 (0.50%) aligned concordantly >1 times
    ----
    900 pairs aligned concordantly 0 times; of these:
      10 (1.11%) aligned discordantly 1 time
    ----
    890 pairs aligned 0 times concordantly or discordantly; of these:
      1780 mates make up the pairs; of these:
        1700 (95.51%) aligned 0 times
10.50% overall alignment rate
"""
BT2_SE = """500 reads; of these:
  500 (100.00%) were unpaired; of these:
    480 (96.00%) aligned 0 times
    15 (3.00%) aligned exactly 1 time
    5 (1.00%) aligned >1 times
4.00% overall alignment rate
"""


def test_parse_bowtie2():
    assert qc.parse_bowtie2(BT2_PE, paired=True) == {"bowtie2_input_reads": 2000, "host_removed_reads": 1800}
    assert qc.parse_bowtie2(BT2_SE, paired=False) == {"bowtie2_input_reads": 500, "host_removed_reads": 480}
    with pytest.raises(qc.ToolError):
        qc.parse_bowtie2("garbage", paired=True)


# --- stream orchestration with a fake fastp|bowtie2 ----------------------------------------
class FakeRunner(qc.Runner):
    """Pretends to run fastp|bowtie2: writes the logs/outputs the real pipeline would."""

    def __init__(self, fail_runs=()):
        super().__init__({"runner": "native", "path_prepend": ""})
        self.fail_runs = set(fail_runs)
        self.calls = 0

    def run(self, body, script_path, timeout=None):
        self.calls += 1
        prefix = Path(str(script_path)[: -len(".sh")])
        if prefix.name in self.fail_runs:
            return type("R", (), {"returncode": 1, "stderr": "boom", "stdout": ""})()
        paired = "--interleaved" in body
        raw, clean = (2000, 1800) if paired else (1000, 900)
        Path(f"{prefix}.fastp.json").write_text(json.dumps(
            {"summary": {"before_filtering": {"total_reads": raw}, "after_filtering": {"total_reads": clean}}}))
        host_removed = 1700 if paired else 850
        log = (f"{clean // 2} reads; of these:\n  {clean // 2} (100.00%) were paired; of these:\n"
               f"    {host_removed // 2} (94.44%) aligned concordantly 0 times\n") if paired else (
               f"{clean} reads; of these:\n  {clean} (100.00%) were unpaired; of these:\n"
               f"    {host_removed} (94.44%) aligned 0 times\n")
        Path(f"{prefix}.bowtie2.log").write_text(log)
        words = shlex.split(body.replace("\\\n", " "))
        target = words[words.index("ln") + 2] if "ln" in words else None  # ln -s TARGET "$alias_dir/out"
        for flag in ("--un-conc-gz", "--un-gz"):
            if flag in words:
                pattern = words[words.index(flag) + 1].replace("$alias_dir/out", target)
                outs = [pattern.replace("%", "1"), pattern.replace("%", "2")] if "%" in pattern else [pattern]
                for o in outs:
                    Path(o).write_bytes(gzip.compress(f"{prefix.name}:{o[-8:]}".encode()))
        return type("R", (), {"returncode": 0, "stderr": "", "stdout": ""})()


def _settings(tmp_path, keep_clean=True) -> Settings:
    cfg = yaml.safe_load((REPO / "config" / "config.yaml").read_text())
    cfg["stream"]["keep_clean"] = keep_clean
    cfg["download"].update(DCFG)
    return Settings(root=tmp_path, cfg=cfg)


def _sample(server, layout="SINGLE", runs=("R1", "R2")):
    files, rows = [], []
    for run in runs:
        names = [f"{run}_1.fastq.gz", f"{run}_2.fastq.gz"] if layout == "PAIRED" else [f"{run}.fastq.gz"]
        blobs = [_blob(n) for n in names]
        rows.append({"run_accession": run, "fastq_urls": ";".join(f"{server}/{n}" for n, _, _ in blobs),
                     "fastq_md5": ";".join(m for _, m, _ in blobs), "fastq_bytes": ";".join(str(s) for _, _, s in blobs)})
        files += blobs
    sample = pd.Series({"sample_id": "T_SCZ__S1", "study_id": "T_SCZ", "group": "SCZ", "run_ids": ";".join(runs),
                        "instrument_platform": "ION_TORRENT" if layout == "SINGLE" else "ILLUMINA",
                        "library_layout": layout, "n_runs": len(runs), "total_bytes": sum(s for *_, s in files)})
    return sample, pd.DataFrame(rows)


@pytest.mark.parametrize("layout", ["SINGLE", "PAIRED"])
def test_process_sample_end_to_end(server, tmp_path, layout):
    settings = _settings(tmp_path)
    sample, runs = _sample(server, layout)
    manifest = build_manifest(sample.to_frame().T, runs, settings.path("raw_fastq"))
    import logging
    state = stream.process_sample(sample, manifest, settings, FakeRunner(), __import__("requests").Session(),
                                  logging.getLogger("t"))
    per_run_raw, per_run_left = (2000, 1700) if layout == "PAIRED" else (1000, 850)
    assert state["raw_reads"] == 2 * per_run_raw and state["host_removed_reads"] == 2 * per_run_left
    # raw deleted, one merged host-removed file (pair) kept, per-run partials gone
    assert not any(Path(d).exists() for d in manifest["dest"])
    clean = sorted(p.name for p in (tmp_path / "data" / "clean_fastq" / "T_SCZ" / "T_SCZ__S1").iterdir())
    assert clean == (["T_SCZ__S1_R1.fq.gz", "T_SCZ__S1_R2.fq.gz"] if layout == "PAIRED" else ["T_SCZ__S1.fq.gz"])
    merged = gzip.decompress((tmp_path / "data" / "clean_fastq" / "T_SCZ" / "T_SCZ__S1" / clean[0]).read_bytes())
    assert merged.startswith(b"R1:") and b"R2:" in merged  # both runs, in run order
    # read_counts.tsv feeds the FR-4 depth filter
    counts = pd.read_csv(stream.write_read_counts(settings), sep="\t")
    assert counts.loc[0, "host_removed_reads"] == state["host_removed_reads"]


def test_stream_run_skips_done_failed_keeps_raw_and_disk_guard(server, tmp_path, monkeypatch):
    settings = _settings(tmp_path, keep_clean=False)
    sample, runs = _sample(server, "SINGLE", runs=("F1",))
    manifest = build_manifest(sample.to_frame().T, runs, settings.path("raw_fastq"))
    todo = sample.to_frame().T
    monkeypatch.setattr(qc, "check_tools", lambda *a, **k: {})

    # a failing QC keeps the raw file for a retry and records the error
    monkeypatch.setattr(qc, "Runner", lambda cfg: FakeRunner(fail_runs={"F1"}))
    res = stream.run(settings, [], None, todo, manifest)
    assert res["T_SCZ__S1"].startswith("FAILED")
    assert Path(manifest["dest"].iloc[0]).exists()
    assert (tmp_path / "data" / "qc_state" / "T_SCZ__S1.failed.json").exists()

    # retry succeeds, reuses the already-downloaded file, clears the failure
    monkeypatch.setattr(qc, "Runner", lambda cfg: FakeRunner())
    res = stream.run(settings, [], None, todo, build_manifest(todo, runs, settings.path("raw_fastq")))
    assert res["T_SCZ__S1"].startswith("done")
    assert not (tmp_path / "data" / "qc_state" / "T_SCZ__S1.failed.json").exists()

    # disk guard: pretend the disk is almost full -> sample skipped before any download
    sample2, runs2 = _sample(server, "SINGLE", runs=("G1",))
    sample2["sample_id"] = "T_SCZ__S2"
    m2 = build_manifest(sample2.to_frame().T, runs2, settings.path("raw_fastq"))
    monkeypatch.setattr(stream.shutil, "disk_usage", lambda p: type("U", (), {"free": 10})())
    res = stream.run(settings, [], None, sample2.to_frame().T, m2)
    assert res["T_SCZ__S2"].startswith("SKIPPED")
    assert not Path(m2["dest"].iloc[0]).exists()


def test_bytes_needed():
    files = pd.DataFrame({"url": ["https://x/a", "https://x/b", "C:/local/c"], "bytes": [10e9, 5e9, 1e9],
                          "present": [False, True, True]})
    scfg = {"keep_clean": True, "clean_ratio": 1.0, "margin_gb": 3}
    assert stream.bytes_needed(files, scfg) == int(10e9 + 16e9 + 3e9)
    assert stream.bytes_needed(files, {**scfg, "keep_clean": False}) == int(10e9 + 3e9)
