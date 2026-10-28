"""Unit tests required by PRD §9: archive inference, label mapping, Zhu platform split, count validation."""

from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from scz_data.fetch.cngb import split_by_platform
from scz_data.fetch.schema import norm_layout, norm_platform, platform_from_model
from scz_data.label import apply_label_map, sample_counts
from scz_data.parse_table import build_studies, infer_archive
from scz_data.validate import compare_counts


# --- accession -> archive ------------------------------------------------------------
@pytest.mark.parametrize(
    "acc, archive",
    [
        ("PRJEB41217", "ENA"),
        ("PRJNA798058", "ENA"),
        ("PRJDB15956", "ENA"),
        ("CRA004772", "GSA"),
        ("CNP0000119", "CNGB"),
        ("RDM", "manual"),
        ("", "manual"),
        (" CNP0000401 ", "CNGB"),
    ],
)
def test_infer_archive(acc, archive):
    assert infer_archive(acc) == archive


def _rec(sid, project, abbr="SCZ", h=10, d=12):
    return {
        "StudyID": sid, "Project": project, "Country": "X", "Platform": "ILLUMINA", "Disease": "d",
        "Abbreviation": abbr, "CohortType": "High-Quality", "HealthCount": float(h), "DiseaseCount": float(d),
        "HealthCount_Filtered": float(h - 1), "DiseaseCount_Filtered": float(d - 1),
        "TotalCount_Filtered": float(h + d - 2), "Clinical Accessment": "DSM-IV",
    }


def test_build_studies_filters_and_overrides():
    recs = [_rec("A_SCZ", "PRJEB1"), _rec("B_AD", "PRJEB2", abbr="AD"), _rec("C_SCZ", "RDM")]
    studies = build_studies(recs, "SCZ", {"A_SCZ": {"accessions": ["PRJEB1", "PRJEB3"], "disease_only": True}})
    assert [s["study_id"] for s in studies] == ["A_SCZ", "C_SCZ"]
    a, c = studies
    assert a["accessions"] == ["PRJEB1", "PRJEB3"] and a["disease_only"] is True and a["archive"] == "ENA"
    assert c["archive"] == "manual" and c["accessions"] == ["RDM"]
    assert a["expected"] == {"healthy_raw": 10, "scz_raw": 12, "healthy_filtered": 9, "scz_filtered": 11, "total_filtered": 20}


# --- normalisation ------------------------------------------------------------------
def test_normalisers():
    assert norm_layout("paired") == "PAIRED" and norm_layout("fragment/single") == "SINGLE"
    assert norm_platform("BGISEQ") == "BGISEQ" and norm_platform("ION_TORRENT") == "ION_TORRENT"
    assert platform_from_model("Illumina NovaSeq 6000") == "ILLUMINA"
    assert platform_from_model("BGISEQ-500") == "BGISEQ"


# --- Zhu platform split --------------------------------------------------------------
def test_zhu_platform_split_is_disjoint_and_complete():
    df = pd.DataFrame(
        {
            "run_accession": [f"CNR{i}" for i in range(6)],
            "sample_accession": [f"CNS{i}" for i in range(6)],
            "instrument_platform": ["ILLUMINA", "BGISEQ", "ILLUMINA", "BGISEQ", "BGISEQ", "ILLUMINA"],
        }
    )
    a = split_by_platform(df, "ILLUMINA")
    b = split_by_platform(df, "BGISEQ")
    assert set(a["sample_accession"]).isdisjoint(b["sample_accession"])
    assert len(a) + len(b) == len(df)
    assert (a["instrument_platform"] == "ILLUMINA").all()
    assert split_by_platform(df, None) is df


# --- label mapping -------------------------------------------------------------------
def test_regex_rules_first_match_wins_and_default():
    df = pd.DataFrame(
        {"sample_accession": ["s1", "s2", "s3", "s4"], "sample_title": ["HC", "SZ/0w", "4w", "weird"]}
    )
    label_map = {
        "rules": [
            {"field": "sample_title", "match": "^HC$", "group": "Healthy"},
            {"field": "sample_title", "match": "^SZ/0w$", "group": "SCZ"},
            {"field": "sample_title", "match": "^(4w|8w)$", "group": "Exclude", "reason": "follow-up"},
            {"field": "sample_title", "match": ".*", "group": "SCZ"},  # never reached for s1..s3
        ],
        "default": {"group": "Exclude", "reason": "unmapped"},
    }
    out, _ = apply_label_map(df.iloc[:3], label_map, Path("."))
    assert out["group"].tolist() == ["Healthy", "SCZ", "Exclude"]
    assert out.loc[2, "exclusion_reason"] == "follow-up"

    label_map["rules"].pop()
    out, warnings = apply_label_map(df, label_map, Path("."))
    assert out.loc[3, "group"] == "Exclude" and out.loc[3, "exclusion_reason"] == "unmapped"
    assert any("default" in w for w in warnings)


def _write_supplement(path: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Supplementary Table X  Phenotypes"])
    ws.append([])
    ws.append(["Samples ID", "Gender\n(1:male, 2:female)", "Age", "Group", "BMI", "Samples ID"])  # dup header
    ws.append(["A1", 1, 30, "HC", 22.5, None])
    ws.append(["A2", 2, 41, "SCZ", "#VALUE!", None])
    ws.append(["A3", 1, 50, "SCZ", 31.0, None])
    ws.append([])
    ws.append(["Table 9b"])  # second table below - must be ignored via last_row
    ws.append(["A1", 999, 0, "junk", 0])
    wb.save(path)


def test_supplement_join(tmp_path):
    _write_supplement(tmp_path / "supp.xlsx")
    df = pd.DataFrame(
        {
            "sample_accession": ["c1", "c2", "c3", "c4"],
            "sample_name": ["A1", "A2", "A3", "MOUSE1"],
            "sample_title": ["", "", "", "FMT mice"],
        }
    )
    label_map = {
        "rules": [
            {"field": "sample_title", "match": "^FMT mice$", "group": "Exclude", "reason": "non-human"},
            {
                "supplement": {
                    "file": "supp.xlsx", "header_row": 3, "last_row": 6, "key": "Samples ID",
                    "join_on": "sample_name", "group_column": "Group", "groups": {"HC": "Healthy", "SCZ": "SCZ"},
                    "columns": {"age": "Age", "sex": "Gender (1:male, 2:female)", "bmi": "BMI"},
                    "sex_codes": {1: "male", 2: "female"},
                }
            },
        ],
    }
    out, warnings = apply_label_map(df, label_map, tmp_path)
    assert out["group"].tolist() == ["Healthy", "SCZ", "SCZ", "Exclude"]
    assert out["sex"].tolist()[:3] == ["male", "female", "male"]
    assert out.loc[0, "bmi"] == 22.5 and pd.isna(out.loc[1, "bmi"])  # '#VALUE!' -> NA
    assert out.loc[3, "exclusion_reason"] == "non-human"
    assert not warnings


def test_sample_counts_merges_runs_and_flags_conflicts():
    df = pd.DataFrame({"sample_accession": ["s1", "s1", "s2", "s3"], "group": ["SCZ", "SCZ", "Healthy", "SCZ"]})
    assert sample_counts(df) == {"SCZ": 2, "Healthy": 1}
    df.loc[1, "group"] = "Healthy"
    assert sample_counts(df)["CONFLICT"] == 1


# --- count validation ----------------------------------------------------------------
@pytest.mark.parametrize("exp, got, status", [(30, 30, "PASS"), (30, 28, "WARN"), (30, 32, "WARN"), (30, 27, "FAIL"), (0, 0, "PASS")])
def test_compare_counts(exp, got, status):
    assert compare_counts(exp, got, tolerance=2) == status
