"""Smoke test of the stream pipeline through the real tool runner (WSL bash), with files from a local HTTP server.

  python scripts/smoke_stream.py          stub fastp/bowtie2 from tests/stubs (no tools needed)
  python scripts/smoke_stream.py --real   installed fastp + bowtie2 + GRCh38 index: synthetic pairs, part of
                                          them cut from human chr1, must be removed as host; the rest kept

No archive is contacted and nothing is downloaded from the internet.
"""
import functools
import gzip
import hashlib
import logging
import random
import shutil
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd
import requests
import yaml

from scz_data import qc, stream
from scz_data.download import build_manifest
from scz_data.settings import Settings

REAL = "--real" in sys.argv
repo = Path(__file__).resolve().parents[1]
root = repo / "tests" / "_smoke"
shutil.rmtree(root, ignore_errors=True)
(root / "www").mkdir(parents=True)

cfg = yaml.safe_load((repo / "config" / "config.yaml").read_text())
if not REAL:
    stub = qc.Runner({"runner": cfg["tools"]["runner"]}).path(repo / "tests" / "stubs")
    cfg["tools"].update(path_prepend=stub, host_index=f"{stub}/fakeidx")
settings = Settings(root=root, cfg=cfg)
runner = qc.Runner(cfg["tools"])
print("check_tools:", qc.check_tools(runner, cfg["tools"], root / "results" / "qc"))

rng = random.Random(42)
COMP = str.maketrans("ACGT", "TGCA")


def pairs(seq: str, n: int, tag: str, read_len=100, frag=300):
    out = []
    for i in range(n):
        s = rng.randrange(0, len(seq) - frag)
        f = seq[s : s + frag]
        out.append((f"{tag}{i}", f[:read_len], f[-read_len:].translate(COMP)[::-1]))
    return out


if REAL:
    # ~120 kb of chr1 from ~12 Mb in (past the leading N block), straight out of the bowtie2 index
    body = f"bowtie2-inspect {qc.sh_word(cfg['tools']['host_index'])} 2>/dev/null | head -n 200000 | tail -n 2000\n"
    res = runner.run(body, root / "inspect.sh", timeout=1800)
    human = "".join(l.strip() for l in res.stdout.splitlines() if not l.startswith(">")).upper()
    assert len(human) > 100_000 and human.count("N") < len(human) // 10, f"bad chr1 chunk ({len(human)} bp)"
    alien = "".join(rng.choice("ACGT") for _ in range(200_000))
    run_pairs = {"RUNA": pairs(human, 120, "human_a") + pairs(alien, 180, "alien_a"),
                 "RUNB": pairs(human, 80, "human_b") + pairs(alien, 120, "alien_b")}
    platform = "ILLUMINA"
else:
    run_pairs = {"RUNA": [(f"a{i}", "ACGTACGTAC" * 6, "TTGCATTGCA" * 6) for i in range(30)],
                 "RUNB": [(f"b{i}", "ACGTACGTAC" * 6, "TTGCATTGCA" * 6) for i in range(20)]}
    platform = "BGISEQ"


def fq(reads, mate):
    return gzip.compress("".join(f"@{n}/{mate}\n{r}\n+\n{'I' * len(r)}\n" for n, *rr in reads for r in [rr[mate - 1]]).encode())


files = {}
for run, rp in run_pairs.items():
    for mate in (1, 2):
        files[f"{run}_{mate}.fastq.gz"] = fq(rp, mate)
for n, b in files.items():
    (root / "www" / n).write_bytes(b)
httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(SimpleHTTPRequestHandler, directory=str(root / "www")))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{httpd.server_address[1]}"

runs = pd.DataFrame([{"run_accession": r, "fastq_urls": f"{base}/{r}_1.fastq.gz;{base}/{r}_2.fastq.gz",
                      "fastq_md5": ";".join(hashlib.md5(files[f"{r}_{i}.fastq.gz"]).hexdigest() for i in (1, 2)),
                      "fastq_bytes": ";".join(str(len(files[f"{r}_{i}.fastq.gz"])) for i in (1, 2))} for r in run_pairs])
sample = pd.Series({"sample_id": "Smoke__S1", "study_id": "Smoke", "group": "SCZ", "run_ids": ";".join(run_pairs),
                    "instrument_platform": platform, "library_layout": "PAIRED", "n_runs": len(run_pairs),
                    "total_bytes": sum(map(len, files.values()))})
manifest = build_manifest(sample.to_frame().T, runs, settings.path("raw_fastq"))
logging.basicConfig(level=logging.INFO, format="  %(message)s")
logging.getLogger("urllib3").setLevel(logging.WARNING)
state = stream.process_sample(sample, manifest, settings, runner, requests.Session(), logging.getLogger("smoke"))
print("state:", {k: state[k] for k in ("raw_reads", "clean_reads", "host_removed_reads", "host_fraction")})

r1 = gzip.decompress((root / state["clean_files"].split(";")[0]).read_bytes()).decode().splitlines()
kept = [l[1:].split("/")[0] for l in r1[::4]]
n_pairs = sum(len(v) for v in run_pairs.values())
assert state["raw_reads"] == 2 * n_pairs, state
assert not any(Path(d).exists() for d in manifest["dest"]), "raw not deleted"
if REAL:
    n_human = sum(1 for v in run_pairs.values() for p in v if p[0].startswith("human"))
    kept_human = sum(k.startswith("human") for k in kept)
    kept_alien = sum(k.startswith("alien") for k in kept)
    print(f"human pairs kept {kept_human}/{n_human}, non-human pairs kept {kept_alien}/{n_pairs - n_human}")
    assert kept_human <= 0.02 * n_human, "host reads were not removed"
    assert kept_alien >= 0.98 * (n_pairs - n_human), "non-host reads were lost"
else:
    assert state["host_removed_reads"] == 2 * n_pairs and kept[0] == "a0" and kept[-1] == "b19", kept[:3]
print("generated script:\n" + (root / "results/qc/Smoke/Smoke__S1/RUNA.sh").read_text())
print("SMOKE OK" + (" (real tools)" if REAL else " (stub tools)"))
httpd.shutdown()
shutil.rmtree(root, ignore_errors=True)
