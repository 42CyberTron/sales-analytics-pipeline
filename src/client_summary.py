import os
import json
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "sales.db")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
METRICS_PATH = os.path.join(OUTPUTS_DIR, "model_metrics.json")
LLM_PATH = os.path.join(OUTPUTS_DIR, "llm_recommendations.json")
CHART_PATH = os.path.join(OUTPUTS_DIR, "forecast_chart.png")


def get_styles():
    """Build custom styles for the PDF."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        spaceAfter=6,
        textColor=HexColor("#1F3864"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=HexColor("#666666"),
        alignment=TA_CENTER,
        spaceAfter=20,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=HexColor("#2F5496"),
        spaceBefore=16,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="BodyTextCustom",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="BulletPoint",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        leftIndent=20,
        spaceAfter=8,
        bulletIndent=8,
    ))
    styles.add(ParagraphStyle(
        name="Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=HexColor("#888888"),
        alignment=TA_CENTER,
        spaceBefore=30,
    ))

    return styles


def get_kpis():
    """Gather key metrics for the PDF."""
    conn = sqlite3.connect(DB_PATH)

    total_revenue = pd.read_sql(
        "SELECT ROUND(SUM(revenue_gbp), 2) AS val FROM transactions", conn
    ).iloc[0]["val"]

    top_country = pd.read_sql("""
        SELECT c.country, ROUND(SUM(t.revenue_gbp), 2) AS rev
        FROM transactions t JOIN customers c ON t.customer_id = c.customer_id
        GROUP BY c.country ORDER BY rev DESC LIMIT 1
    """, conn)

    mom_data = pd.read_sql("""
        WITH monthly AS (
            SELECT substr(invoice_date, 1, 7) AS month, SUM(revenue_gbp) AS revenue
            FROM transactions GROUP BY month ORDER BY month
        )
        SELECT month, revenue, LAG(revenue) OVER (ORDER BY month) AS prev
        FROM monthly ORDER BY month
    """, conn)

    latest_mom = (
        (mom_data["revenue"].iloc[-1] - mom_data["prev"].iloc[-1])
        / mom_data["prev"].iloc[-1] if mom_data["prev"].iloc[-1] and mom_data["prev"].iloc[-1] > 0 else 0
    )
    conn.close()

    if os.path.exists(METRICS_PATH):
        with open(METRICS_PATH) as f:
            metrics = json.load(f)
        forecast_next = metrics.get("prophet_forecast_next_month", 0)
        improvement = metrics.get("improvement_pct", 0)
    else:
        forecast_next = 0
        improvement = 0

    return {
        "total_revenue": total_revenue,
        "top_country": top_country.iloc[0]["country"],
        "top_country_revenue": top_country.iloc[0]["rev"],
        "mom_growth": latest_mom * 100,
        "forecast_next": forecast_next,
        "improvement": improvement,
    }


def get_recommendations():
    """Load LLM recommendations."""
    if os.path.exists(LLM_PATH):
        with open(LLM_PATH) as f:
            data = json.load(f)
        return data.get("recommendations", "")
    return "Recommendations not available. Run llm_insights.py first."


def generate_chart():
    """Generate revenue trend chart if not already present."""
    if os.path.exists(CHART_PATH):
        return CHART_PATH

    conn = sqlite3.connect(DB_PATH)
    monthly = pd.read_sql("""
        SELECT substr(invoice_date, 1, 7) AS month, SUM(revenue_gbp) AS revenue
        FROM transactions GROUP BY month ORDER BY month
    """, conn)
    conn.close()

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(range(len(monthly)), monthly["revenue"], "b-o", markersize=3)
    ax.set_title("Monthly Revenue Trend", fontsize=12)
    ax.set_xlabel("Month Index")
    ax.set_ylabel("Revenue (GBP)")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)
    return CHART_PATH


def build_pdf():
    """Build the client-facing PDF summary."""
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    styles = get_styles()
    kpis = get_kpis()
    recommendations = get_recommendations()
    chart_path = generate_chart()

    out_path = os.path.join(OUTPUTS_DIR, "summary.pdf")
    doc = SimpleDocTemplate(
        out_path,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    story = []

    # Title
    story.append(Paragraph("Sales Analytics Summary", styles["ReportTitle"]))
    story.append(Paragraph(
        f"Prepared: {datetime.now().strftime('%B %d, %Y')} | Online Retail II Analysis",
        styles["ReportSubtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#2F5496")))
    story.append(Spacer(1, 12))

    # KPI Table
    story.append(Paragraph("Key Metrics", styles["SectionHeader"]))

    kpi_data = [
        ["Metric", "Value"],
        ["Total Revenue", f"£{kpis['total_revenue']:,.2f}"],
        ["Top Country", f"{kpis['top_country']} (£{kpis['top_country_revenue']:,.2f})"],
        ["Latest MoM Growth", f"{kpis['mom_growth']:.2f}%"],
        ["Next Month Forecast", f"£{kpis['forecast_next']:,.2f}"],
        ["Model Improvement", f"{kpis['improvement']:.2f}%"],
    ]

    table = Table(kpi_data, colWidths=[2.5 * inch, 3 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#2F5496")),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#F2F7FB")),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#F2F7FB"), white]),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))

    # Chart
    story.append(Paragraph("Revenue Trend & Forecast", styles["SectionHeader"]))
    story.append(Image(chart_path, width=6 * inch, height=3 * inch))
    story.append(Spacer(1, 12))

    # Recommendations
    story.append(Paragraph("Strategic Recommendations", styles["SectionHeader"]))

    bullets = [b.strip() for b in recommendations.strip().split("\n") if b.strip()]
    for bullet in bullets:
        if bullet.startswith("-"):
            bullet = bullet[1:].strip()
        story.append(Paragraph(f"• {bullet}", styles["BulletPoint"]))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#CCCCCC")))
    story.append(Spacer(1, 6))

    # Methodology footer
    story.append(Paragraph(
        "Methodology: Data source = Online Retail II (UCI/Kaggle), ~541K invoice records (2009-2011). "
        "Normalized into 3NF SQLite schema. FX rates via exchangerate.host. "
        "Forecast: Facebook Prophet with 3-month holdout validation.",
        styles["Footer"],
    ))

    doc.build(story)
    return out_path


if __name__ == "__main__":
    print("[PDF] Generating client-facing summary...")
    out_path = build_pdf()
    print(f"[PDF] Saved to: {out_path}")
