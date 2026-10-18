from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

from crisismap.models import Assessment


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=22,
            textColor=colors.HexColor("#1a73e8"), alignment=1, spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=11,
            textColor=colors.HexColor("#5f6368"), alignment=1, spaceAfter=2,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=14,
            textColor=colors.HexColor("#202124"), spaceBefore=14, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Helvetica", fontSize=10,
            textColor=colors.HexColor("#202124"), leading=14, spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontName="Helvetica", fontSize=8,
            textColor=colors.HexColor("#5f6368"), leading=10,
        ),
        "metric": ParagraphStyle(
            "metric", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10,
            textColor=colors.HexColor("#202124"), alignment=1,
        ),
        "metricval": ParagraphStyle(
            "metricval", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=16,
            textColor=colors.HexColor("#1a73e8"), alignment=1,
        ),
    }


def _risk_color(level: str) -> colors.Color:
    mapping = {
        "Low": colors.HexColor("#1e7d32"),
        "Moderate": colors.HexColor("#d4a017"),
        "High": colors.HexColor("#d9534f"),
        "Extreme": colors.HexColor("#b00020"),
    }
    color = mapping.get(level, colors.HexColor("#202124"))
    return color if isinstance(color, colors.Color) else colors.HexColor(color)


def export_pdf(assessment: Assessment, path: str | Path) -> None:
    """Export a CrisisMap assessment as a nicely formatted PDF report."""
    loc = assessment.location
    sc = assessment.scenario
    styles = _styles()
    story = []

    # Header
    story.append(Paragraph("CRISIS MAP", styles["title"]))
    story.append(Paragraph("Offline Disaster Impact Assessment Report", styles["subtitle"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dadce0")))
    story.append(Spacer(1, 8))

    # Info box
    info_data = [
        ["Location", f"{loc.name}"],
        ["Coordinates", f"{loc.latitude:.4f}°N, {loc.longitude:.4f}°E"],
        ["Elevation", f"{loc.elevation_m:.0f} m"],
        ["Disaster", sc.disaster.value],
        ["Intensity", f"{sc.intensity:.1f} / 10"],
        ["Duration", f"{sc.duration_hours:.1f} h"],
        ["Preparedness", f"{sc.preparedness:.0%}"],
        ["Time of Day", f"{loc.time_of_day}:00 hrs"],
        ["Season", loc.season.title()],
        ["Generated", datetime.now().strftime("%d %b %Y, %I:%M %p")],
    ]
    info_table = Table(info_data, colWidths=[40 * mm, 110 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#5f6368")),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#202124")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dadce0")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8f9fa")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # Risk score section
    story.append(Paragraph("Composite Risk Score", styles["h2"]))
    score_color = _risk_color(assessment.risk_level.value)
    score_table = Table(
        [[Paragraph(f"<b>{assessment.risk_level.value.upper()} RISK</b>", styles["metric"]),
          Paragraph(f"{assessment.overall_score:.0f}", styles["metricval"]),
          Paragraph("/100", styles["metricval"])]],
        colWidths=[70 * mm, 40 * mm, 20 * mm],
    )
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.Color(
            score_color.red, score_color.green, score_color.blue, alpha=0.15
        )),
        ("BOX", (0, 0), (-1, -1), 1.5, score_color),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 6))
    ci = int(assessment.confidence_interval * 100)
    story.append(Paragraph(
        f"{ci}% confidence interval: {assessment.confidence_lower:.0f} – {assessment.confidence_upper:.0f} "
        f"(σ={assessment.mc_std:.1f}, n={assessment.mc_samples} samples)",
        styles["small"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(assessment.summary, styles["body"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        f"Estimated affected radius: {assessment.affected_radius_km:.1f} km",
        styles["small"],
    ))
    story.append(Spacer(1, 12))

    # Metrics table
    story.append(Paragraph("Component Breakdown", styles["h2"]))
    metrics_data = [
        ["Component", "Score", "Weight"],
        ["Physical Hazard", f"{assessment.hazard_score:.1f}", f"{sc.weight_hazard:.0%}"],
        ["People Exposure", f"{assessment.exposure_score:.1f}", f"{sc.weight_exposure:.0%}"],
        ["Social Vulnerability", f"{assessment.vulnerability_score:.1f}", f"{sc.weight_vulnerability:.0%}"],
    ]
    metrics_table = Table(metrics_data, colWidths=[100 * mm, 40 * mm, 40 * mm])
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#202124")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#202124")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dadce0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 12))

    # Hazard factors
    if assessment.hazard_factors:
        story.append(Paragraph("Hazard Factors", styles["h2"]))
        hf_rows = [["Factor", "Value"]]
        for k, v in assessment.hazard_factors.items():
            label = k.replace("_", " ").title()
            hf_rows.append([label, f"{v}"])
        hf_table = Table(hf_rows, colWidths=[120 * mm, 60 * mm])
        hf_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#202124")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#202124")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dadce0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(hf_table)
        story.append(Spacer(1, 12))

    # Suggested actions
    story.append(Paragraph("Suggested Actions", styles["h2"]))
    for i, action in enumerate(assessment.recommendations, 1):
        story.append(Paragraph(f"{i}. {action}", styles["body"]))
    story.append(Spacer(1, 12))

    # Disclaimer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dadce0")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Disclaimer:</b> CrisisMap is an educational assessment tool, not a forecasting or "
        "emergency-response system. Results are deterministic simulations based on local GeoJSON data "
        "and should not be used for actual emergency decisions.",
        styles["small"],
    ))

    # Build PDF
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="CrisisMap Assessment Report",
        author="CrisisMap",
    )
    doc.build(story)
