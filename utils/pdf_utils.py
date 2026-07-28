"""
PDF REPORT GENERATION
======================
Renders a real PDF from a pandas DataFrame using reportlab (already listed
in requirements.txt). Used by pages/reports.py's "Generate PDF Report"
button -- this used to be a simulated placeholder; it now returns real
PDF bytes suitable for st.download_button.
"""

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

STATUS_COLORS = {
    "Healthy": colors.HexColor("#22c55e"),
    "Warning": colors.HexColor("#f59e0b"),
    "Critical": colors.HexColor("#ef4444"),
}


def generate_pdf_report(df, title, subtitle=""):
    """Builds a landscape A4 PDF table report from a DataFrame and returns
    it as bytes. `df` columns become the table header row as-is."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("AegisTitle", parent=styles["Title"], textColor=colors.HexColor("#0f172a"))
    sub_style = ParagraphStyle("AegisSub", parent=styles["Normal"], textColor=colors.HexColor("#475569"))

    elements = [
        Paragraph("⚡ Aegis Watch — AI Powered Machine Health Guardian", title_style),
        Paragraph(title, styles["Heading2"]),
    ]
    if subtitle:
        elements.append(Paragraph(subtitle, sub_style))
    elements.append(Paragraph(
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", sub_style
    ))
    elements.append(Spacer(1, 0.5 * cm))

    header = list(df.columns)
    data = [header] + df.astype(str).values.tolist()
    table = Table(data, repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]

    # Color the Status column's text if one exists, matching the dashboard's badge colors.
    if "Status" in header:
        status_col = header.index("Status")
        for row_idx, row in enumerate(df.itertuples(index=False), start=1):
            status_val = getattr(row, "Status", None)
            color = STATUS_COLORS.get(status_val)
            if color:
                style_cmds.append(("TEXTCOLOR", (status_col, row_idx), (status_col, row_idx), color))
                style_cmds.append(("FONTNAME", (status_col, row_idx), (status_col, row_idx), "Helvetica-Bold"))

    table.setStyle(TableStyle(style_cmds))
    elements.append(table)

    doc.build(elements)
    return buf.getvalue()
