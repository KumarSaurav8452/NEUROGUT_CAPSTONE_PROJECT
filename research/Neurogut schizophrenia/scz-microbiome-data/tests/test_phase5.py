"""Phase 5 tests: FR-8 harmonised table and FR-9 report on a tiny two-study fixture."""

import json

import pandas as pd
import pytest

from scz_data import harmonize, report
from scz_data.settings import Settings

CFG = {
    "paths": {"filtered": "data/filtered", "results": "results", "qc_read_counts": "results/qc/read_counts.tsv",
              "read_estimates": "results/qc/read_estimates.tsv", "raw_metadata": "data/raw_metadata",
              "logs": "logs"},
    "profile": {"reads_per_sample": {"default": 500000}, "state_dir": "data/profile_state",
                "external_profiles": {"B": {"source": "cMD full depth"}}},
    "report": {"count_notes": {"A": "documented"}, "skipped_studies": {"M": "awaiting access"}},
}
STUDIES = [
    {"study_id": "A", "accession": "PRJA", "archive": "ENA", "country": "DK", "diagnosis_criteria": "ICD-10"},
    {"study_id": "B", "accession": "PRJB", "archive": "CNGB", "country": "CN", "diagnosis_criteria": "DSM-IV"},
]


def _samples(study, ids, groups, included, extra=None):
    df = pd.DataFrame({
        "sample_id": [f"{study}__{i}" for i in ids], "study_id": study, "archive": "ENA", "source_accession": "P",
        "sample_accession": ids, "sample_name": ids, "group": groups, "run_ids": [f"R{i}" for i in ids],
        "instrument_platform": "ILLUMINA", "library_layout": "PAIRED", "age": None, "sex": None, "bmi": None,
        "included": included, "exclusion_step": [None if k else "1:shotgun" for k in included],
        "exclusion_reason": [None if k else "16S" for k in included], "unclassified_frac": 0.2,
    })
    return df.assign(**(extra or {}))


@pytest.fixture
def root(tmp_path):
    (tmp_path / "data/filtered").mkdir(parents=True)
    (tmp_path / "results/qc").mkdir(parents=True)
    (tmp_path / "results/profiles").mkdir(parents=True)
    _samples("A", ["s1", "s2", "s3"], ["Healthy", "SCZ", None], [True, True, False]).to_csv(
        tmp_path / "data/filtered/A.samples.tsv", sep="\t", index=False)
    _samples("B", ["s1", "t2"], ["Healthy", "SCZ"], [True, True], {"sample_name": ["1", "x2"]}).to_csv(
        tmp_path / "data/filtered/B.samples.tsv", sep="\t", index=False)
    pd.DataFrame({"sample_id": ["A__s1", "A__s2", "B__s1", "B__t2"], "est_total_reads": [2e7, 3e7, 4e7, 5e7],
                  "est_host_removed_reads": [1.9e7, 2.9e7, 3.9e7, 4.9e7], "est_method": "archive read_count"}) \
        .to_csv(tmp_path / "results/qc/read_estimates.tsv", sep="\t", index=False)
    pd.DataFrame({"sample_id": ["A__s1"], "raw_reads": [21_000_000], "clean_reads": [20_000_000],
                  "host_removed_reads": [19_500_000]}).to_csv(tmp_path / "results/qc/read_counts.tsv", sep="\t", index=False)
    pd.DataFrame({"clade_name": ["k__B|s__x", "k__B|s__y"], "A__s1": [60, 40], "A__s2": [100, 0],
                  "B__s1": [50, 50], "B__t2": [10, 90]}) \
        .to_csv(tmp_path / "results/profiles/metaphlan_merged.tsv", sep="\t", index=False)
    pd.DataFrame({"sample_id": ["A__s1", "A__s2"], "group": ["Healthy", "SCZ"], "sub_raw_reads": [1e6, 1e6],
                  "host_fraction": [0.001, 0.002], "unclassified_frac": [0.2, 0.3], "n_species": [2, 1],
                  "flags": [None, "species<10"]}).to_csv(tmp_path / "results/profiles/profile_qc.tsv", sep="\t", index=False)
    return tmp_path


def test_harmonize_schema_counts_and_sources(root):
    df = harmonize.build(Settings(root, CFG), STUDIES)
    assert list(df.columns[:18]) == harmonize.COLUMNS[:18]
    assert not df["sample_id"].duplicated().any() and len(df) == 5  # same accession in two studies stays distinct
    r = df.set_index("sample_id")
    assert r.loc["A__s1", "raw_reads"] == 21_000_000 and r.loc["A__s1", "reads_source"].startswith("stream")
    assert r.loc["A__s2", "host_removed_reads"] == 29_000_000 and pd.isna(r.loc["A__s2", "clean_reads"])
    assert r.loc["A__s2", "n_species"] == 1 and r.loc["A__s2", "profile_qc_flags"] == "species<10"
    assert r.loc["B__t2", "profile_source"] == "cMD full depth" and r.loc["A__s1", "profile_source"].startswith("subsample")
    assert r.loc["A__s3", "exclusion_reason"] == "16S" and not r.loc["A__s3", "profiled"]
    assert r.loc["B__s1", "country"] == "CN" and r.loc["A__s1", "diagnosis_criteria"] == "ICD-10"


def test_harmonize_run_writes_parquet_and_dictionary(root):
    harmonize.run(Settings(root, CFG), STUDIES)
    back = pd.read_parquet(root / "results/scz_samples.parquet")
    assert len(back) == 5 and back["raw_reads"].dtype.name == "Int64"
    assert all(f"| {c} |" in (root / "results/DATA_DICTIONARY.md").read_text() for c in harmonize.COLUMNS)


def test_report_sections_and_acceptance(root):
    s = Settings(root, CFG)
    harmonize.run(s, STUDIES)
    pd.DataFrame({"study_id": ["A", "A"], "group": ["Healthy", "SCZ"], "expected_raw": [1, 1], "labelled": [1, 1],
                  "status": "PASS"}).to_csv(root / "results/label_counts_vs_table_s1.tsv", sep="\t", index=False)
    pd.DataFrame({"study_id": ["A", "A"], "group": ["Healthy", "SCZ"], "expected_filtered": [1, 5], "obtained": [1, 1],
                  "status": ["PASS", "FAIL"], "skipped_filters": ""}) \
        .to_csv(root / "results/filter_counts_vs_table_s1.tsv", sep="\t", index=False)
    (root / "logs/stream").mkdir(parents=True)
    (root / "logs/stream/A.log").write_text("x INFO [s] f1.fq.gz: downloaded (1 GB, MD5 ok)\n"
                                            "x WARNING [s] f2.fq.gz: attempt 1/3 failed: MD5 mismatch for f2.fq.gz: e\n")
    (root / "data/profile_state").mkdir(parents=True)
    (root / "data/profile_state/A__s1.json").write_text(json.dumps({"sample_id": "A__s1", "status": "done"}))
    text = report.build(s, STUDIES)
    for head in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6.", "## 8."):
        assert head in text
    assert "**A** (PASS/FAIL): documented" in text and "**M**: awaiting access" in text
    assert "f2.fq.gz" in text and "| A__s3 | " in text  # abandoned download and excluded sample listed
    md5 = report.md5_summary(root / "logs/stream")
    assert md5["ok"] == 1 and md5["abandoned"] == ["f2.fq.gz"] and not md5["unresolved"]


def test_supplement_filter_and_key_transform(tmp_path):
    import openpyxl
    from scz_data.label import apply_label_map, transform_keys

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ST1"
    ws.append(["Name", "Group", "Sequencing method", "raw reads", "Age", "Gender", "BMI"])
    ws.append(["SCZ01", "SCZ", "shotgun", 15906086, 48, "M", "NA"])
    ws.append(["SCZ02", "SCZ", "shotgun", 15366240, 43, "F", "NA"])
    ws.append(["SCZ01", "SCZ", "16S", 1, 1, "M", "NA"])       # same name in another sub-study: filtered out
    wb.save(tmp_path / "st.xlsx")
    spec = {"file": "st.xlsx", "sheet": "ST1", "header_row": 1, "filter": {"Sequencing method": "shotgun"},
            "key": "Name", "join_on": "sample_name",
            "key_transform": {"regex": "^wmb-([0-9]+)$", "format": "SCZ{:02d}", "offset": -62},
            "group_column": "Group", "groups": {"SCZ": "SCZ"},
            "columns": {"age": "Age", "sex": "Gender", "bmi": "BMI", "published_reads": "raw reads"},
            "sex_codes": {"M": "male", "F": "female"}}
    assert list(transform_keys(pd.Series(["wmb-63", "wmb-101", "x"]), spec["key_transform"])) == ["SCZ01", "SCZ39", "x"]
    df = pd.DataFrame({"sample_name": ["wmb-63", "wmb-64"]})
    out, warnings = apply_label_map(df, {"rules": [{"supplement": spec}]}, tmp_path)
    assert list(out["group"]) == ["SCZ", "SCZ"] and list(out["sex"]) == ["male", "female"]
    assert list(out["published_reads"]) == [15906086, 15366240] and out["bmi"].isna().all()
    assert not warnings
