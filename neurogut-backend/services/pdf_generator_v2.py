"""
NEUROGUT v2.0 -- Enhanced PDF Report Generator (11 Sections)
===============================================================
Generates comprehensive clinical PDF reports using ReportLab.
"""

import io
import hashlib
from datetime import datetime, timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Clinical reference for taxa
TAXA_CLINICAL = {
    "Gardnerella": {"role": "Pathological", "notes": "Primary pathological driver. Elevated in Comorbid."},
    "Corynebacterium": {"role": "Pathological", "notes": "Core diagnostic driver — Depression and Comorbid."},
    "Veillonella": {"role": "Pathological", "notes": "Elevated in Comorbid. Inflammation-associated."},
    "Lachnospira": {"role": "Protective", "notes": "Butyrate producer. Depleted = risk signal."},
    "Pseudobutyrivibrio": {"role": "Protective", "notes": "Gut barrier function. Depleted in disease."},
    "Fructilactobacillus": {"role": "Comorbidity Marker", "notes": "Spikes in Comorbid only."},
    "Trueperella": {"role": "Differentiation", "notes": "Distinguishes Depression vs Comorbid."},
    "Lawsonella": {"role": "Pathological", "notes": "Co-elevates with Gardnerella in severe cases."},
    "Ruthenibacterium": {"role": "Emerging", "notes": "Secondary importance in XGB chain."},
    "Kocuria": {"role": "Context-dep.", "notes": "Moderate importance across conditions."},
    "Lancefieldella": {"role": "Secondary", "notes": "Lower importance — contextual signal."},
    "Lachnoanaerobaculum": {"role": "Secondary", "notes": "Oral-gut axis microbe."},
    "Raoultella": {"role": "Secondary", "notes": "Oxidative stress association."},
}

# Normal ranges (approximate healthy baselines)
TAXA_NORMAL_RANGE = {
    "Lachnospira": (4.0, 10.0), "Ruthenibacterium": (3.0, 8.0),
    "Veillonella": (-1.0, 3.0), "Gardnerella": (-6.0, -2.0),
    "Pseudobutyrivibrio": (0.5, 4.0), "Kocuria": (-5.0, -1.0),
    "Trueperella": (-1.0, 1.5), "Lancefieldella": (-5.0, -1.0),
    "Fructilactobacillus": (-5.0, -1.0), "Lachnoanaerobaculum": (0.0, 3.0),
    "Corynebacterium": (-1.0, 2.0), "Raoultella": (-5.0, -1.0),
    "Lawsonella": (-4.0, 0.0),
}

ICD10_SUGGESTIONS = {
    "healthy": [],
    "depression_only": ["F32.9 — Major depressive disorder, unspecified", "K59.1 — Functional diarrhea (if GI symptoms)"],
    "anxiety_only": ["F41.1 — Generalized anxiety disorder", "K58.0 — IBS with diarrhea (if GI symptoms)"],
    "comorbid": ["F41.8 — Mixed anxiety and depressive disorder", "F32.9 — MDD unspecified", "K58.9 — IBS unspecified"],
}


def _make_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("T", parent=styles["Title"], fontSize=24, textColor=colors.HexColor("#006D77"), spaceAfter=4),
        "subtitle": ParagraphStyle("ST", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#6B7280"), spaceAfter=10),
        "section": ParagraphStyle("S", parent=styles["Heading2"], fontSize=13, textColor=colors.HexColor("#006D77"), spaceBefore=14, spaceAfter=6),
        "body": ParagraphStyle("B", parent=styles["Normal"], fontSize=10, leading=14),
        "small": ParagraphStyle("SM", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#9CA3AF")),
        "bold": ParagraphStyle("BD", parent=styles["Normal"], fontSize=10, leading=14, fontName="Helvetica-Bold"),
        "alert": ParagraphStyle("AL", parent=styles["Normal"], fontSize=11, leading=15, textColor=colors.HexColor("#DC2626"), fontName="Helvetica-Bold"),
    }

TEAL = colors.HexColor("#006D77")
LIGHT_TEAL = colors.HexColor("#E8F4F5")
GRID_COLOR = colors.HexColor("#D1D5DB")
RISK_COLORS = {"healthy": "#22C55E", "depression_only": "#F59E0B", "anxiety_only": "#F59E0B", "comorbid": "#EF4444"}


def generate_report_pdf_v2(
    patient_info: dict, prediction: dict, sample_data: dict,
    clinician_name: str = "Clinical Staff",
    trend_data: list | None = None,
    benchmark_data: list | None = None,
) -> bytes:
    """Generate an 11-section clinical PDF report per PRD v2.0."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm, leftMargin=2*cm, rightMargin=2*cm)
    s = _make_styles()
    els = []
    risk = prediction.get("risk_tier", "unknown")
    rc = colors.HexColor(RISK_COLORS.get(risk, "#6B7280"))
    dep_prob = prediction.get("depression_prob", 0)
    anx_prob = prediction.get("anxiety_prob", 0)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # §1 — Report Header & Branding
    els.append(Paragraph("NEUROGUT", s["title"]))
    els.append(Paragraph("Gut-Brain Axis Diagnostic Report — v2.0", s["subtitle"]))
    els.append(HRFlowable(width="100%", thickness=2, color=TEAL, spaceAfter=8))
    meta = [["Report ID", prediction.get("prediction_id", "N/A")[:16] + "..."],
            ["Generated", now_str], ["Clinician", clinician_name],
            ["Model", prediction.get("model_version", "v2.0")]]
    mt = Table(meta, colWidths=[3.5*cm, 13*cm])
    mt.setStyle(TableStyle([("FONTSIZE", (0,0), (-1,-1), 9), ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
                            ("TEXTCOLOR", (0,0), (0,-1), TEAL), ("BOTTOMPADDING", (0,0), (-1,-1), 2)]))
    els.append(mt)
    els.append(Spacer(1, 10))

    # §2 — Patient Summary
    els.append(Paragraph("§2  Patient Summary", s["section"]))
    pd_rows = [["Patient Code", patient_info.get("patient_code", "N/A")],
               ["Age", str(patient_info.get("age", "N/A"))],
               ["Sex", patient_info.get("sex", "N/A").title()],
               ["Collection Date", sample_data.get("collection_date", "N/A")],
               ["Input Method", sample_data.get("input_method", "N/A").replace("_", " ").title()]]
    pt = Table(pd_rows, colWidths=[4*cm, 12.5*cm])
    pt.setStyle(TableStyle([("BACKGROUND", (0,0), (0,-1), LIGHT_TEAL), ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
                            ("FONTSIZE", (0,0), (-1,-1), 10), ("GRID", (0,0), (-1,-1), 0.5, GRID_COLOR),
                            ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    els.append(pt)
    els.append(Spacer(1, 10))

    # §3 — Executive Clinical Summary (NEW)
    els.append(Paragraph("§3  Executive Clinical Summary", s["section"]))
    narrative = _build_narrative(prediction, patient_info)
    els.append(Paragraph(narrative, s["body"]))
    els.append(Spacer(1, 10))

    # §4 — Prediction Results with Confidence (UPDATED)
    els.append(Paragraph("§4  Prediction Results with Confidence Intervals", s["section"]))
    ci_lo_d = prediction.get("depression_ci_low")
    ci_hi_d = prediction.get("depression_ci_high")
    ci_lo_a = prediction.get("anxiety_ci_low")
    ci_hi_a = prediction.get("anxiety_ci_high")
    ci_d_str = f" (95% CI: {ci_lo_d*100:.1f}%–{ci_hi_d*100:.1f}%)" if ci_lo_d is not None else ""
    ci_a_str = f" (95% CI: {ci_lo_a*100:.1f}%–{ci_hi_a*100:.1f}%)" if ci_lo_a is not None else ""

    pred_rows = [["Metric", "Value", "Status"],
                 ["Depression", f"{dep_prob*100:.1f}%{ci_d_str}", "POSITIVE" if prediction.get("depression_label") == 1 else "NEGATIVE"],
                 ["Anxiety", f"{anx_prob*100:.1f}%{ci_a_str}", "POSITIVE" if prediction.get("anxiety_label") == 1 else "NEGATIVE"],
                 ["Risk Tier", risk.replace("_", " ").upper(), ""],
                 ["Bootstrap Iterations", str(prediction.get("bootstrap_iterations", 100)), ""]]
    prt = Table(pred_rows, colWidths=[4*cm, 8*cm, 4.5*cm])
    prt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), TEAL), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                             ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 9),
                             ("GRID", (0,0), (-1,-1), 0.5, GRID_COLOR), ("ALIGN", (1,0), (-1,-1), "CENTER"),
                             ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    els.append(prt)
    els.append(Spacer(1, 10))

    # §5 — Biomarker Analysis Table (UPDATED — top drivers ranked)
    els.append(Paragraph("§5  Biomarker Analysis — Feature Importances", s["section"]))
    rf_imp = prediction.get("rf_importances", {})
    xgb_imp = prediction.get("xgb_importances", {})
    consensus = prediction.get("consensus_features", [])
    if rf_imp:
        bio_header = ["Rank", "Taxon", "RF Score", "XGB Score", "Consensus", "Role"]
        bio_rows = [bio_header]
        sorted_taxa = sorted(rf_imp.keys(), key=lambda k: rf_imp[k], reverse=True)
        for i, taxon in enumerate(sorted_taxa, 1):
            role = TAXA_CLINICAL.get(taxon, {}).get("role", "—")
            bio_rows.append([str(i), taxon, f"{rf_imp.get(taxon,0):.4f}", f"{xgb_imp.get(taxon,0):.4f}",
                            "✓" if taxon in consensus else "", role])
        bt = Table(bio_rows, colWidths=[1.2*cm, 3.8*cm, 2.5*cm, 2.5*cm, 2.2*cm, 3.5*cm])
        bt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), TEAL), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 8),
                                ("GRID", (0,0), (-1,-1), 0.5, GRID_COLOR), ("ALIGN", (0,0), (0,-1), "CENTER"),
                                ("ALIGN", (2,0), (4,-1), "CENTER"), ("TOPPADDING", (0,0), (-1,-1), 3),
                                ("BOTTOMPADDING", (0,0), (-1,-1), 3)]))
        els.append(bt)
    els.append(Spacer(1, 10))

    # §6 — Longitudinal Trend (NEW — conditional)
    if trend_data and len(trend_data) >= 2:
        els.append(Paragraph("§6  Longitudinal Trend Analysis", s["section"]))
        els.append(Paragraph(f"Patient has <b>{len(trend_data)}</b> prior analyses. Trend data shown below:", s["body"]))
        trend_header = ["Date", "Depression %", "Anxiety %", "Risk Tier"]
        trend_rows = [trend_header]
        for t in trend_data:
            trend_rows.append([t.get("sample_date", ""), f"{t.get('depression_prob',0)*100:.1f}%",
                              f"{t.get('anxiety_prob',0)*100:.1f}%", t.get("risk_tier", "").replace("_"," ").title()])
        tt = Table(trend_rows, colWidths=[4*cm, 4*cm, 4*cm, 4.5*cm])
        tt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), TEAL), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 9),
                                ("GRID", (0,0), (-1,-1), 0.5, GRID_COLOR), ("ALIGN", (1,0), (-1,-1), "CENTER"),
                                ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
        els.append(tt)
        els.append(Spacer(1, 10))

    # §7 — Cohort Benchmark (NEW — conditional)
    if benchmark_data:
        els.append(Paragraph("§7  Cohort Benchmark Comparison", s["section"]))
        els.append(Paragraph("Patient taxa values compared against de-identified hospital cohort (same risk tier):", s["body"]))
        bm_header = ["Taxon", "Patient", "Cohort Mean", "Cohort P50", "Cohort P25–P75"]
        bm_rows = [bm_header]
        for bm in benchmark_data[:10]:
            bm_rows.append([bm.get("taxon",""), f"{bm.get('patient_value',0):.2f}",
                           f"{bm.get('mean',0):.2f}", f"{bm.get('p50',0):.2f}",
                           f"{bm.get('p25',0):.2f}–{bm.get('p75',0):.2f}"])
        bmt = Table(bm_rows, colWidths=[3.5*cm, 2.5*cm, 3*cm, 2.5*cm, 4*cm])
        bmt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), TEAL), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                                 ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 8),
                                 ("GRID", (0,0), (-1,-1), 0.5, GRID_COLOR), ("ALIGN", (1,0), (-1,-1), "CENTER"),
                                 ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3)]))
        els.append(bmt)
        els.append(Spacer(1, 10))

    # §8 — Bacterial Taxa Reference Table (UPDATED)
    els.append(Paragraph("§8  Bacterial Taxa Reference Table", s["section"]))
    ref_header = ["Taxon", "Role", "Normal Range", "Clinical Notes"]
    ref_rows = [ref_header]
    for taxon, info in TAXA_CLINICAL.items():
        nr = TAXA_NORMAL_RANGE.get(taxon, (0, 0))
        ref_rows.append([taxon, info["role"], f"{nr[0]:.1f} to {nr[1]:.1f}", info["notes"]])
    reft = Table(ref_rows, colWidths=[3.5*cm, 2.8*cm, 3*cm, 7.2*cm])
    reft.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), TEAL), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                              ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 7.5),
                              ("GRID", (0,0), (-1,-1), 0.5, GRID_COLOR), ("VALIGN", (0,0), (-1,-1), "TOP"),
                              ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3)]))
    els.append(reft)
    els.append(Spacer(1, 10))

    # §9 — Clinical Recommendations (UPDATED — with ICD-10)
    els.append(Paragraph("§9  Clinical Recommendations", s["section"]))
    rec = _build_recommendations(risk)
    els.append(Paragraph(rec, s["body"]))
    icd = ICD10_SUGGESTIONS.get(risk, [])
    if icd:
        els.append(Spacer(1, 6))
        els.append(Paragraph("<b>Suggested ICD-10 Codes:</b>", s["body"]))
        for code in icd:
            els.append(Paragraph(f"  • {code}", s["body"]))
    els.append(Spacer(1, 10))

    # §10 — Model Metadata & Disclaimer
    els.append(Paragraph("§10  Model Metadata & Disclaimer", s["section"]))
    meta_text = (f"Model: GutMicrobiomeStacker (RF + XGB ClassifierChain + LR meta-learner) | "
                 f"Version: {prediction.get('model_version', 'v2.0')} | Features: 13 bacterial taxa | "
                 f"CI Method: Bootstrap perturbation (100 iterations, 95% confidence) | "
                 f"Training: 5-fold stratified CV | Depression AUC: 0.945 | Anxiety AUC: 0.893")
    els.append(Paragraph(meta_text, s["small"]))
    els.append(Spacer(1, 4))
    disclaimer = ("<i>DISCLAIMER: This report is generated by an AI clinical decision support tool (NEUROGUT) and "
                  "is intended to assist qualified healthcare professionals. It is NOT a standalone diagnosis. "
                  "Clinical decisions should incorporate patient history, physical examination, and other diagnostic tests. "
                  "Not FDA/CE cleared. For research and clinical decision support use only.</i>")
    els.append(Paragraph(disclaimer, s["small"]))
    els.append(Spacer(1, 10))

    # §11 — Digital Signature Block (NEW)
    els.append(HRFlowable(width="100%", thickness=1, color=GRID_COLOR, spaceAfter=8))
    els.append(Paragraph("§11  Digital Signature", s["section"]))
    sig_rows = [["Clinician Name", clinician_name], ["Designation", "Clinical Staff — NEUROGUT Platform"],
                ["Date", now_str], ["Signature", "________________________"]]
    st = Table(sig_rows, colWidths=[4*cm, 12.5*cm])
    st.setStyle(TableStyle([("FONTSIZE", (0,0), (-1,-1), 10), ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
                            ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
    els.append(st)

    doc.build(els)
    pdf_bytes = buffer.getvalue()
    return pdf_bytes


def compute_report_hash(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()


def _build_narrative(prediction: dict, patient: dict) -> str:
    risk = prediction.get("risk_tier", "unknown")
    dep = prediction.get("depression_prob", 0)
    anx = prediction.get("anxiety_prob", 0)
    consensus = prediction.get("consensus_features", [])
    top_biomarkers = ", ".join(consensus[:3]) if consensus else "multiple taxa"
    pc = patient.get("patient_code", "N/A")
    age = patient.get("age", "")
    age_str = f", age {age}" if age else ""

    if risk == "healthy":
        return (f"Patient {pc}{age_str} presents with a <b>Healthy</b> microbiome profile. "
                f"Depression probability is {dep*100:.1f}% and Anxiety probability is {anx*100:.1f}%, "
                f"both below clinical thresholds. No significant dysbiosis markers detected. "
                f"Routine monitoring recommended.")
    elif risk == "depression_only":
        return (f"Patient {pc}{age_str} presents with a <b>Depression-risk</b> profile. "
                f"Depression probability is elevated at {dep*100:.1f}%. Key drivers include {top_biomarkers}. "
                f"Protective butyrate-producing taxa appear depleted. "
                f"Psychiatric referral for PHQ-9 assessment is recommended.")
    elif risk == "anxiety_only":
        return (f"Patient {pc}{age_str} presents with an <b>Anxiety-risk</b> profile. "
                f"Anxiety probability is elevated at {anx*100:.1f}%. Key drivers include {top_biomarkers}. "
                f"Inflammatory-associated taxa show increased abundance. "
                f"GAD-7 assessment and stress-reduction protocol recommended.")
    else:
        return (f"<b>ALERT:</b> Patient {pc}{age_str} presents with a <b>Comorbid Depression + Anxiety</b> pattern. "
                f"Depression probability: {dep*100:.1f}%, Anxiety probability: {anx*100:.1f}%. "
                f"Key pathological drivers: {top_biomarkers}. Multiple pathogenic taxa elevated with "
                f"significant protective taxa depletion. This represents the highest risk category. "
                f"Urgent psychiatric referral recommended.")


def _build_recommendations(risk: str) -> str:
    recs = {
        "healthy": ("<b>Risk Level: LOW</b><br/>"
                    "• Continue routine microbiome screening as part of preventive care<br/>"
                    "• Maintain current dietary habits supporting gut microbiome diversity<br/>"
                    "• Follow-up: Standard screening interval (12 months)"),
        "depression_only": ("<b>Risk Level: MODERATE — Depression</b><br/>"
                           "• Referral to psychiatry for PHQ-9 assessment<br/>"
                           "• Consider probiotic supplementation targeting SCFA production (Lactobacillus, Bifidobacterium strains)<br/>"
                           "• Dietary intervention: increase fiber intake, fermented foods<br/>"
                           "• Follow-up microbiome sample in 3 months"),
        "anxiety_only": ("<b>Risk Level: MODERATE — Anxiety</b><br/>"
                        "• Referral for GAD-7 assessment<br/>"
                        "• Stress-reduction protocol (CBT, mindfulness)<br/>"
                        "• Anti-inflammatory dietary recommendations<br/>"
                        "• Follow-up microbiome sample in 3 months"),
        "comorbid": ("<b>Risk Level: HIGH — Comorbid Depression + Anxiety</b><br/>"
                    "• <b>Urgent psychiatric referral</b><br/>"
                    "• Comprehensive treatment: pharmacological + probiotic interventions<br/>"
                    "• GI consultation for gut barrier assessment<br/>"
                    "• High-fiber, anti-inflammatory diet protocol<br/>"
                    "• Follow-up microbiome sample in 6–8 weeks"),
    }
    return recs.get(risk, recs["healthy"])
