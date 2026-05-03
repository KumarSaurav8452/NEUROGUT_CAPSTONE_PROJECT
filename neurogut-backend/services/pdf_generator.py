"""
NEUROGUT -- PDF Report Generator
==================================
Generates clinical PDF reports using ReportLab.
"""

import io
from datetime import datetime, timezone
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


def generate_report_pdf(
    patient_info: dict,
    prediction: dict,
    sample_data: dict,
) -> bytes:
    """Generate a clinical PDF report.

    Args:
        patient_info: {patient_code, age, sex, notes}
        prediction: {depression_prob, anxiety_prob, risk_tier, rf_importances, ...}
        sample_data: {collection_date, input_method, taxa values...}

    Returns:
        PDF as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "NGTitle", parent=styles["Title"],
        fontSize=22, textColor=colors.HexColor("#006D77"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "NGSubtitle", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#6B7280"),
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "NGSection", parent=styles["Heading2"],
        fontSize=14, textColor=colors.HexColor("#006D77"),
        spaceBefore=16, spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "NGBody", parent=styles["Normal"],
        fontSize=10, leading=14,
    )

    elements = []

    # ----- Header -----
    elements.append(Paragraph("NEUROGUT", title_style))
    elements.append(Paragraph("Gut-Brain Axis Diagnostic Report", subtitle_style))
    elements.append(HRFlowable(
        width="100%", thickness=2,
        color=colors.HexColor("#006D77"), spaceAfter=12,
    ))

    # ----- Patient Info -----
    elements.append(Paragraph("Patient Information", section_style))
    patient_table_data = [
        ["Patient Code", patient_info.get("patient_code", "N/A")],
        ["Age", str(patient_info.get("age", "N/A"))],
        ["Sex", patient_info.get("sex", "N/A").title()],
        ["Collection Date", sample_data.get("collection_date", "N/A")],
        ["Input Method", sample_data.get("input_method", "N/A").replace("_", " ").title()],
    ]
    pt = Table(patient_table_data, colWidths=[4 * cm, 12 * cm])
    pt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F4F5")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(pt)
    elements.append(Spacer(1, 12))

    # ----- Prediction Results -----
    elements.append(Paragraph("Prediction Results", section_style))

    risk = prediction.get("risk_tier", "unknown")
    risk_color_map = {
        "healthy": "#22C55E",
        "depression_only": "#F59E0B",
        "anxiety_only": "#F59E0B",
        "comorbid": "#EF4444",
    }
    risk_color = risk_color_map.get(risk, "#6B7280")

    dep_prob = prediction.get("depression_prob", 0) * 100
    anx_prob = prediction.get("anxiety_prob", 0) * 100

    pred_data = [
        ["Metric", "Value", "Status"],
        [
            "Depression Probability",
            f"{dep_prob:.1f}%",
            "POSITIVE" if prediction.get("depression_label") == 1 else "NEGATIVE",
        ],
        [
            "Anxiety Probability",
            f"{anx_prob:.1f}%",
            "POSITIVE" if prediction.get("anxiety_label") == 1 else "NEGATIVE",
        ],
        ["Risk Tier", risk.replace("_", " ").upper(), ""],
        ["Model Version", prediction.get("model_version", "v1.0"), ""],
    ]

    pred_table = Table(pred_data, colWidths=[5 * cm, 5 * cm, 5 * cm])
    pred_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#006D77")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(pred_table)
    elements.append(Spacer(1, 12))

    # ----- Biomarker Importances -----
    elements.append(Paragraph("Key Biomarkers", section_style))

    rf_imp = prediction.get("rf_importances", {})
    xgb_imp = prediction.get("xgb_importances", {})
    consensus = prediction.get("consensus_features", [])

    if rf_imp:
        bio_header = ["Taxon", "RF Importance", "XGB Importance", "Consensus"]
        bio_rows = [bio_header]
        # Sort by RF importance descending
        sorted_taxa = sorted(rf_imp.keys(), key=lambda k: rf_imp[k], reverse=True)
        for taxon in sorted_taxa[:8]:  # Top 8
            is_consensus = "YES" if taxon in consensus else ""
            bio_rows.append([
                taxon,
                f"{rf_imp.get(taxon, 0):.4f}",
                f"{xgb_imp.get(taxon, 0):.4f}",
                is_consensus,
            ])

        bio_table = Table(bio_rows, colWidths=[4.5 * cm, 3.5 * cm, 3.5 * cm, 3 * cm])
        bio_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#006D77")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(bio_table)
    elements.append(Spacer(1, 12))

    # ----- Clinical Recommendations -----
    elements.append(Paragraph("Clinical Recommendations", section_style))

    if risk == "healthy":
        rec_text = (
            "The microbiome profile indicates a <b>healthy</b> gut-brain axis composition. "
            "No significant dysbiosis markers detected. Continue monitoring as part of "
            "routine screening."
        )
    elif risk == "depression_only":
        rec_text = (
            "The microbiome profile indicates <b>elevated risk for Depression</b>. "
            "Key pathogenic taxa are elevated while protective butyrate-producing taxa are depleted. "
            "Consider: (1) Referral to psychiatry for PHQ-9 assessment, "
            "(2) Probiotic supplementation targeting SCFA production, "
            "(3) Follow-up microbiome sample in 3 months."
        )
    elif risk == "anxiety_only":
        rec_text = (
            "The microbiome profile indicates <b>elevated risk for Anxiety</b>. "
            "Inflammatory-associated taxa show increased abundance. "
            "Consider: (1) Referral for GAD-7 assessment, "
            "(2) Stress-reduction protocol, "
            "(3) Follow-up microbiome sample in 3 months."
        )
    else:  # comorbid
        rec_text = (
            "<b>ALERT: Comorbid Depression + Anxiety pattern detected.</b> "
            "Multiple pathogenic taxa are elevated with significant protective taxa depletion. "
            "This represents the highest risk category. "
            "Consider: (1) Urgent psychiatric referral, "
            "(2) Comprehensive treatment plan combining pharmacological and probiotic interventions, "
            "(3) Follow-up microbiome sample in 6-8 weeks."
        )
    elements.append(Paragraph(rec_text, body_style))
    elements.append(Spacer(1, 20))

    # ----- Footer -----
    elements.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#D1D5DB"), spaceAfter=8,
    ))
    footer_text = (
        f"<i>Generated by NEUROGUT v1.0 on "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. "
        f"This report is generated by an AI clinical decision support tool and should "
        f"be interpreted by a qualified healthcare professional. Not a standalone diagnosis.</i>"
    )
    elements.append(Paragraph(footer_text, ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor("#9CA3AF"),
    )))

    doc.build(elements)
    return buffer.getvalue()
