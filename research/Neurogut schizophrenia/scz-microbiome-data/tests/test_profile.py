"""Phase 3b tests: partial FASTQ streaming, subsample fetching, MetaPhlAn parsing, merged outputs."""

import gzip
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd
import pytest
import requests
import yaml

from scz_data import profile, qc
from scz_data.settings import Settings

REPO = Path(__file__).resolve().parents[1]


def _fq(names, mate=None):
    sfx = f"/{mate}" if mate else ""
    return "".join(f"@{n}{sfx} extra\nACGTACGTAA\n+\nIIIIIIIIII\n" for n in names).encode()


def test_partial_fastq_stops_early_and_handles_multimember():
    data = gzip.compress(_fq([f"r{i}" for i in range(50)])) + gzip.compress(_fq([f"s{i}" for i in range(50)]))
    pf = profile.PartialFastq(70)
    for i in range(0, len(data), 37):  # tiny chunks: records split across chunk and member borders
        pf.feed(data[i : i + 37])
        if pf.done:
            break
    recs = pf.records()
    assert len(recs) == 70 and recs[0][0].startswith(b"@r0") and recs[-1][0].startswith(b"@s19")
    assert pf.compressed <= len(data)


def test_partial_fastq_short_file_and_malformed():
    pf = profile.PartialFastq(1000)
    pf.feed(gzip.compress(_fq(["a", "b"])))
    assert len(pf.records()) == 2 and not pf.done
    bad = profile.PartialFastq(5)
    bad.feed(gzip.compress(b"@x\nACGT\n+\nII\n"))
    with pytest.raises(ValueError):
        bad.records()


def test_watchdog_aborts_trickling_connection(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(profile.time, "monotonic", lambda: clock[0])
    dog = profile._Watchdog(min_kbps=30, grace_s=120)
    for _ in range(12):  # fast: 1 MB every 10 s
        clock[0] += 10
        dog.tick(1 << 20)
    with pytest.raises(RuntimeError, match="stalled"):
        for _ in range(13):  # trickle: 10 KB every 10 s = 1 KB/s
            clock[0] += 10
            dog.tick(10 * 1024)


def test_read_name_strips_mate_suffix():
    assert profile.read_name(b"@ERR1.5/1 length=100") == b"ERR1.5"
    assert profile.read_name(b"@CL1:1:2/2") == b"CL1:1:2"


@pytest.fixture()
def www(tmp_path):
    d = tmp_path / "www"
    d.mkdir()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(d)))
    httpd.RequestHandlerClass.log_message = lambda *a: None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield d, f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _put(d, name, data):
    (d / name).write_bytes(data)
    return len(data)


def test_fetch_subsample_paired_and_estimate(www, tmp_path):
    d, base = www
    names = [f"p{i}" for i in range(400)]
    s1 = _put(d, "A_1.fastq.gz", gzip.compress(_fq(names, 1)))
    s2 = _put(d, "A_2.fastq.gz", gzip.compress(_fq(names, 2)))
    runs = pd.DataFrame([{"run_accession": "A", "fastq_urls": f"{base}/A_1.fastq.gz;{base}/A_2.fastq.gz",
                          "fastq_bytes": f"{s1};{s2}"}])
    sample = pd.Series({"sample_id": "T__S", "library_layout": "PAIRED", "run_ids": "A"})
    sub = profile.fetch_subsample(sample, runs, 100, tmp_path / "sub", requests.Session())
    r1 = gzip.decompress(sub["paths"]["R1"].read_bytes()).split(b"\n")
    assert sub["sub_reads"] == 200 and r1[0].startswith(b"@p0/1") and len(r1) == 401
    # the whole tiny file arrives in one chunk: only the share of compressed bytes behind the kept reads counts,
    # so the full-depth estimate is close to the true 2 x 400 (names grow longer later in the file: +2 %)
    assert abs(sub["size_estimated_reads"] - 800) <= 0.05 * 800


def test_fetch_subsample_continues_into_next_run_and_detects_desync(www, tmp_path):
    d, base = www
    s = {n: _put(d, n, gzip.compress(_fq([f"{n[0]}{i}" for i in range(k)]))) for n, k in (("a.fastq.gz", 30), ("b.fastq.gz", 50))}
    runs = pd.DataFrame([{"run_accession": r, "fastq_urls": f"{base}/{f}", "fastq_bytes": str(s[f])}
                         for r, f in (("RA", "a.fastq.gz"), ("RB", "b.fastq.gz"))])
    sample = pd.Series({"sample_id": "T__SE", "library_layout": "SINGLE", "run_ids": "RA;RB"})
    sub = profile.fetch_subsample(sample, runs, 40, tmp_path / "sub", requests.Session())
    assert sub["sub_reads"] == 40  # 30 from RA + 10 from RB

    _put(d, "X_1.fastq.gz", gzip.compress(_fq(["x0", "x1"], 1)))
    _put(d, "X_2.fastq.gz", gzip.compress(_fq(["x0", "WRONG"], 2)))
    runs = pd.DataFrame([{"run_accession": "X", "fastq_urls": f"{base}/X_1.fastq.gz;{base}/X_2.fastq.gz", "fastq_bytes": "1;1"}])
    with pytest.raises(ValueError, match="out of sync"):
        profile.fetch_subsample(pd.Series({"sample_id": "T__X", "library_layout": "PAIRED", "run_ids": "X"}),
                                runs, 10, tmp_path / "sub2", requests.Session())


def test_fetch_job_in_worker_process_and_marker_reuse(www, tmp_path):
    from concurrent.futures import ProcessPoolExecutor

    d, base = www
    size = _put(d, "W.fastq.gz", gzip.compress(_fq([f"w{i}" for i in range(60)])))
    runs = [{"run_accession": "W", "fastq_urls": f"{base}/W.fastq.gz", "fastq_bytes": str(size)}]
    sample = {"sample_id": "T__W", "library_layout": "SINGLE", "run_ids": "W"}
    with ProcessPoolExecutor(1, max_tasks_per_child=1) as pool:  # same setup as profile.run
        sub = pool.submit(profile.fetch_job, sample, runs, 50, str(tmp_path / "W")).result()
    assert sub["sub_reads"] == 50 and Path(sub["paths"]["SE"]).exists()
    (d / "W.fastq.gz").unlink()  # second call must not need the server: marker + files are reused
    again = profile.fetch_job(sample, runs, 50, str(tmp_path / "W"))
    assert again["sub_reads"] == 50


MPA3 = """#mpa_v30_CHOCOPhlAn_201901
#/usr/bin/metaphlan x.fq.gz
#SampleID\tMetaphlan_Analysis
#clade_name\tNCBI_tax_id\trelative_abundance\tadditional_species
UNKNOWN\t-1\t20.0\t
k__Bacteria\t2\t80.0\t
k__Bacteria|p__Firmicutes|c__Clostridia|o__Clostridiales|f__Ruminococcaceae|g__Faecalibacterium|s__Faecalibacterium_prausnitzii\t2|1239|186801|186802|216572|216851|853\t50.0\t
k__Bacteria|p__Bacteroidetes|c__Bacteroidia|o__Bacteroidales|f__Bacteroidaceae|g__Bacteroides|s__Bacteroides_vulgatus\t2|976|200643|171549|815|816|821\t30.0\t
"""


def test_parse_metaphlan_and_species_table():
    prof, unk = profile.parse_metaphlan(MPA3)
    assert unk == 0.2
    sp = profile.species_table(prof)
    assert len(sp) == 2 and abs(sp.sum() - 100) < 1e-9
    assert abs(sp.filter(like="prausnitzii").iloc[0] - 62.5) < 1e-9


def test_build_profile_script_uses_space_free_alias(tmp_path):
    cfg = yaml.safe_load((REPO / "config" / "config.yaml").read_text())
    r = qc.Runner({**cfg["tools"], "runner": "native"})
    body = profile.build_profile_script(r, cfg, "BGISEQ", "PAIRED", {"R1": tmp_path / "a b" / "s.R1.fq.gz",
                                        "R2": tmp_path / "a b" / "s.R2.fq.gz"}, tmp_path / "a b", "S1")
    assert '--un-conc-gz "$alias_dir/w/S1.hr.R%.fq.gz"' in body
    assert 'metaphlan "$alias_dir/w/S1.hr.R1.fq.gz,$alias_dir/w/S1.hr.R2.fq.gz"' in body
    assert "--index mpa_v30_CHOCOPhlAn_201901" in body and "--unknown_estimation" in body  # MetaPhlAn 3 flag
    assert "--sensitive" in body and "--very-sensitive" not in body


def test_write_outputs_merges_own_and_external_profiles(tmp_path):
    cfg = yaml.safe_load((REPO / "config" / "config.yaml").read_text())
    settings = Settings(root=tmp_path, cfg=cfg)
    pdir = tmp_path / "results" / "profiles" / "Li_2023_SCZ"
    pdir.mkdir(parents=True)
    (pdir / "Li__S1.profile.txt").write_text(MPA3)
    sd = tmp_path / "data" / "profile_state"
    sd.mkdir(parents=True)
    (sd / "Li__S1.json").write_text(json.dumps({
        "sample_id": "Li__S1", "study_id": "Li_2023_SCZ", "group": "SCZ", "status": "done", "unclassified_frac": 0.2,
        "profile": "results/profiles/Li_2023_SCZ/Li__S1.profile.txt", "est_total_reads": 4e7, "est_method": "size",
        "host_fraction": 0.01, "est_host_removed_reads": 3.9e7, "sub_raw_reads": 1e6}))
    # external (cMD-style) table for Zhu A, keyed by sample_name
    ext = tmp_path / "data" / "external" / "cmd"
    ext.mkdir(parents=True)
    clade = "k__Bacteria|p__Firmicutes|c__Clostridia|o__Clostridiales|f__Ruminococcaceae|g__Faecalibacterium|s__Faecalibacterium_prausnitzii"
    pd.DataFrame({"feature": [clade, "k__Bacteria"], "wHAX1": [40.0, 100.0]}).to_csv(ext / "ZhuF_2020.relative_abundance.tsv", sep="\t", index=False)
    (tmp_path / "data" / "filtered").mkdir(parents=True)
    pd.DataFrame({"sample_id": ["Zhu_2020A_SCZ__CNS1"], "sample_name": ["wHAX1"], "group": ["Healthy"], "included": ["True"],
                  "library_layout": ["PAIRED"], "archive_read_count": ["20000000"]}).to_csv(
        tmp_path / "data" / "filtered" / "Zhu_2020A_SCZ.samples.tsv", sep="\t", index=False)
    profile.write_outputs(settings)
    merged = pd.read_csv(tmp_path / "results" / "profiles" / "metaphlan_merged.tsv", sep="\t", index_col=0)
    assert set(merged.columns) == {"Li__S1", "Zhu_2020A_SCZ__CNS1"}
    assert merged.loc[clade, "Zhu_2020A_SCZ__CNS1"] == 100.0  # renormalised over species rows
    zhu = pd.read_csv(tmp_path / "results" / "profiles" / "by_study" / "Zhu_2020A_SCZ.species.tsv", sep="\t", index_col=0)
    assert list(zhu.columns) == ["Zhu_2020A_SCZ__CNS1"] and list(zhu.index) == [clade]  # only that study's species
    est = pd.read_csv(settings.path("read_estimates"), sep="\t").set_index("sample_id")
    assert est.loc["Zhu_2020A_SCZ__CNS1", "est_host_removed_reads"] == 40_000_000  # 2 mates x 20 M spots
    unc = pd.read_csv(settings.path("unclassified"), sep="\t")
    assert unc.set_index("sample_id").loc["Li__S1", "unclassified_frac"] == 0.2
    # all-levels table (merge_metaphlan_tables layout) and QC flags: 2 species < 10 -> flagged
    all_lv = pd.read_csv(tmp_path / "results" / "profiles" / "metaphlan_merged_all_levels.tsv", sep="\t", index_col=0)
    assert {"UNKNOWN", "k__Bacteria", clade} <= set(all_lv.index)
    q = pd.read_csv(tmp_path / "results" / "profiles" / "profile_qc.tsv", sep="\t", keep_default_na=False)
    assert q.loc[0, "n_species"] == 2 and "species<10" in q.loc[0, "flags"]


def test_profile_qc_flags_host_and_duplicates(tmp_path):
    cfg = yaml.safe_load((REPO / "config" / "config.yaml").read_text())
    settings = Settings(root=tmp_path, cfg=cfg)
    (tmp_path / "p.txt").write_text(MPA3)
    base = {"study_id": "T", "group": "SCZ", "profile": "p.txt", "unclassified_frac": 0.2,
            "sub_raw_reads": 1000, "sub_host_removed_reads": 300, "host_fraction": 0.4}
    rows = profile.profile_qc([{**base, "sample_id": "a"}, {**base, "sample_id": "b"}], settings)
    assert "host>5%" in rows[0]["flags"] and "kept<50%" in rows[0]["flags"]
    assert "identical_to:a" in rows[1]["flags"] and "identical_to" not in rows[0]["flags"]
