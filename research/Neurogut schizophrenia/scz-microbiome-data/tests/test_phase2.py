"""Phase 2 tests: FR-4 filter steps and the FR-5 dry-run manifest."""

from pathlib import Path

import pandas as pd
import pytest

from scz_data.download import build_manifest, pick_subset
from scz_data.filter import count_comparison, filter_study, merge_runs

FCFG = {
    "shotgun_strategies": ["WGS"], "min_reads": 10_000_000, "max_unclassified_frac": 0.30, "max_bmi": 30,
    "count_tolerance": 2, "min_study_samples": 10,
}


def _runs():
    # s1: two top-up runs (merged); s2: BMI 35; s3: BMI NA; s4: 16S; s5: label-excluded follow-up; s6: healthy
    rows = [
        ("r1a", "s1", "SCZ", "WGS", 22.0), ("r1b", "s1", "SCZ", "WGS", 22.0),
        ("r2", "s2", "SCZ", "WGS", 35.0), ("r3", "s3", "SCZ", "WGS", None),
        ("r4", "s4", "Exclude", "AMPLICON", None), ("r5", "s5", "Exclude", "WGS", 20.0),
        ("r6", "s6", "Healthy", "WGS", 24.0),
    ]
    return pd.DataFrame(
        {
            "study_id": "T_SCZ", "archive": "ENA", "source_accession": "PRJEB1",
            "run_accession": [r[0] for r in rows], "sample_accession": [r[1] for r in rows],
            "sample_name": [r[1] for r in rows], "group": [r[2] for r in rows],
            "library_strategy": [r[3] for r in rows], "bmi": [r[4] for r in rows],
            "instrument_platform": "ILLUMINA", "library_layout": "PAIRED", "read_count": "20000000",
            "fastq_urls": [f"https://x/{r[0]}_1.fq.gz;https://x/{r[0]}_2.fq.gz" for r in rows],
            "fastq_md5": "a;b", "fastq_bytes": "100;200", "download_source": "ENA",
            "exclusion_reason": [None, None, None, None, "16S", "follow-up", None],
            "age": None, "sex": None, "diagnosis_detail": None,
        }
    )


def _study(**kw):
    s = {"study_id": "T_SCZ", "expected": {"healthy_filtered": 1, "scz_filtered": 2}}
    s.update(kw)
    return s


def test_merge_runs_one_row_per_sample():
    m = merge_runs(_runs()).set_index("sample_accession")
    assert len(m) == 6
    assert m.loc["s1", "run_ids"] == "r1a;r1b" and m.loc["s1", "n_runs"] == 2
    assert m.loc["s1", "total_bytes"] == 600 and m.loc["s1", "archive_read_count"] == 40_000_000
    assert m.loc["s1", "sample_id"] == "T_SCZ__s1"


def test_merge_runs_rejects_conflicting_labels():
    runs = _runs()
    runs.loc[1, "group"] = "Healthy"
    with pytest.raises(ValueError):
        merge_runs(runs)


def test_filter_steps_attribution():
    samples, waterfall = filter_study(_runs(), _study(), FCFG)
    s = samples.set_index("sample_accession")
    assert s.loc["s4", "exclusion_step"] == "1:shotgun"
    assert s.loc["s5", "exclusion_step"] == "3:baseline" and s.loc["s5", "exclusion_reason"] == "follow-up"
    assert s.loc["s2", "exclusion_step"] == "4:bmi"
    assert bool(s.loc["s3", "included"])  # BMI NA is kept
    assert sorted(samples.loc[samples["included"], "sample_accession"]) == ["s1", "s3", "s6"]
    assert {w["name"]: w["status"] for w in waterfall}["depth"] == "pending"
    assert s.loc["s1", "pending_filters"] == "depth;unclassified"
    # every removed sample is counted exactly once in the waterfall
    removed = sum(w["removed_healthy"] + w["removed_scz"] + w["removed_unlabelled"] for w in waterfall)
    assert removed == int((~samples["included"]).sum())


def test_bmi_filter_can_be_skipped():
    samples, waterfall = filter_study(_runs(), _study(bmi_filter=False), FCFG)
    assert bool(samples.set_index("sample_accession").loc["s2", "included"])
    assert {w["name"]: w["status"] for w in waterfall}["bmi"] == "skipped"


def test_depth_and_unclassified_applied_when_outputs_exist():
    clean = pd.Series({"T_SCZ__s1": 5_000_000, "T_SCZ__s3": 30_000_000, "T_SCZ__s6": 30_000_000})
    uncl = pd.Series({"T_SCZ__s1": 0.1, "T_SCZ__s3": 0.5, "T_SCZ__s6": 0.1})
    samples, waterfall = filter_study(_runs(), _study(), FCFG, clean, uncl)
    s = samples.set_index("sample_accession")
    assert s.loc["s1", "exclusion_step"] == "5:depth"
    assert s.loc["s3", "exclusion_step"] == "6:unclassified"
    assert list(samples.loc[samples["included"], "sample_accession"]) == ["s6"]
    assert {w["name"]: w["status"] for w in waterfall}["depth"] == "applied"


def test_unclassified_filter_can_be_switched_off():
    clean = pd.Series({"T_SCZ__s1": 30_000_000, "T_SCZ__s3": 30_000_000, "T_SCZ__s6": 30_000_000})
    uncl = pd.Series({"T_SCZ__s1": 0.1, "T_SCZ__s3": 0.5, "T_SCZ__s6": 0.1})
    samples, waterfall = filter_study(_runs(), _study(), {**FCFG, "apply_unclassified_filter": False}, clean, uncl)
    s = samples.set_index("sample_accession")
    assert bool(s.loc["s3", "included"]) and s.loc["s3", "unclassified_frac"] == 0.5  # kept, value still recorded
    assert {w["name"]: w["status"] for w in waterfall}["unclassified"] == "skipped"
    assert "unclassified" not in s.loc["s3", "pending_filters"]


def test_count_comparison_pending_vs_final():
    samples, waterfall = filter_study(_runs(), _study(), FCFG)
    rows = {r["group"]: r for r in count_comparison(_study(), samples, waterfall, FCFG)}
    assert rows["SCZ"]["obtained"] == 2 and rows["SCZ"]["status"] == "PASS"
    assert rows["Healthy"]["status"] == "PASS"
    many = _study(expected={"healthy_filtered": 1, "scz_filtered": 0})
    rows = {r["group"]: r for r in count_comparison(many, samples, waterfall, FCFG)}
    # surplus while filters are pending: no verdict yet, but it would be WARN (+2) if final
    assert rows["SCZ"]["status"] == "PENDING" and rows["SCZ"]["status_if_final"] == "WARN"
    few = _study(expected={"healthy_filtered": 5, "scz_filtered": 10})
    rows = {r["group"]: r for r in count_comparison(few, samples, waterfall, FCFG)}
    assert rows["SCZ"]["status"] == "FAIL"  # a deficit is final even with filters pending


def test_pick_subset_smallest_per_group():
    s = pd.DataFrame(
        {
            "study_id": "T", "group": ["SCZ", "SCZ", "SCZ", "Healthy", "Healthy"],
            "sample_id": ["a", "b", "c", "d", "e"], "total_bytes": [300, 100, 200, 50, 10],
        }
    )
    picked = pick_subset(s, 2)
    assert sorted(picked["sample_id"]) == ["b", "c", "d", "e"]
    assert pick_subset(s, None) is s


def test_build_manifest_paths_and_validation(tmp_path):
    runs = _runs()
    samples, _ = filter_study(runs, _study(), FCFG)
    kept = samples[samples["included"]]
    m = build_manifest(kept, runs, tmp_path / "raw_fastq")
    assert len(m) == 8  # s1 has 2 runs x 2 files, s3 and s6 have 1 run x 2 files
    assert m["dest"].iloc[0].endswith(str(Path("raw_fastq") / "T_SCZ" / "r1a" / "r1a_1.fq.gz"))
    assert not m["present"].any()
    dest = Path(m["dest"].iloc[0])
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"x" * 100)
    assert build_manifest(kept, runs, tmp_path / "raw_fastq")["present"].iloc[0]

    runs.loc[0, "fastq_md5"] = "only-one"
    with pytest.raises(RuntimeError):
        build_manifest(kept, runs, tmp_path / "raw_fastq")
