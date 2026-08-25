import os
import json
import re
import sqlite3
import pandas as pd
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "sales.db")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
METRICS_PATH = os.path.join(OUTPUTS_DIR, "model_metrics.json")


def gather_kpis():
    """Aggregate SQL + model outputs into a structured summary dict."""
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

    lowest_growth = pd.read_sql("""
        WITH country_monthly AS (
            SELECT c.country, substr(t.invoice_date, 1, 7) AS month,
                   SUM(t.revenue_gbp) AS revenue
            FROM transactions t JOIN customers c ON t.customer_id = c.customer_id
            GROUP BY c.country, month
        ),
        growth AS (
            SELECT country,
                   (MAX(revenue) - MIN(revenue)) / NULLIF(MIN(revenue), 0) AS growth_rate
            FROM country_monthly GROUP BY country HAVING COUNT(*) > 3
        )
        SELECT country, ROUND(growth_rate * 100, 2) AS growth_pct
        FROM growth ORDER BY growth_pct ASC LIMIT 1
    """, conn)

    conn.close()

    # Model metrics
    if os.path.exists(METRICS_PATH):
        with open(METRICS_PATH) as f:
            metrics = json.load(f)
        forecast_next = metrics.get("forecast_next_month", 0)
        improvement = metrics.get("improvement_pct", 0)
        prophet_rmse = metrics.get("hw_rmse", 0)
    else:
        forecast_next = 0
        improvement = 0
        prophet_rmse = 0

    summary = {
        "total_revenue_gbp": round(total_revenue, 2),
        "top_country": top_country.iloc[0]["country"],
        "top_country_revenue_gbp": round(top_country.iloc[0]["rev"], 2),
        "latest_mom_growth_pct": round(latest_mom * 100, 2),
        "underperforming_region": lowest_growth.iloc[0]["country"] if len(lowest_growth) > 0 else "N/A",
        "underperforming_region_growth_pct": float(lowest_growth.iloc[0]["growth_pct"]) if len(lowest_growth) > 0 else 0,
        "forecast_next_month_gbp": round(forecast_next, 2),
        "model_improvement_pct": improvement,
        "model_rmse": prophet_rmse,
    }

    return summary


def build_prompt(summary):
    """Build a tight system prompt for the LLM."""
    system_prompt = """You are a senior business analyst. Given these KPIs, write exactly 3 bullet-point recommendations for a client, in plain English, no jargon. Each bullet must be 1-2 sentences and reference specific numbers from the data."""

    user_prompt = f"""Data Summary:
- Total revenue: £{summary['total_revenue_gbp']:,.2f}
- Top country: {summary['top_country']} (£{summary['top_country_revenue_gbp']:,.2f})
- Latest month-over-month growth: {summary['latest_mom_growth_pct']:.2f}%
- Underperforming region: {summary['underperforming_region']} ({summary['underperforming_region_growth_pct']:.2f}% growth)
- Forecast next month: £{summary['forecast_next_month_gbp']:,.2f}
- Forecast model improvement over baseline: {summary['model_improvement_pct']:.2f}%

Write exactly 3 bullet-point recommendations:"""

    return system_prompt, user_prompt


def call_llm(system_prompt, user_prompt):
    """Call LLM via Groq (free tier) or OpenAI fallback."""
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
    # Or hardcode here (not recommended for shared repos):
    # api_key = "gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

    if not api_key:
        print("  [WARN] No GROQ_API_KEY or OPENAI_API_KEY found. Using template output.")
        return _template_output(system_prompt, user_prompt)

    if os.environ.get("GROQ_API_KEY"):
        return _call_groq(system_prompt, user_prompt, api_key)
    else:
        return _call_openai(system_prompt, user_prompt, api_key)


def _call_groq(system_prompt, user_prompt, api_key):
    """Call Groq API (free, fast)."""
    import requests

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code != 200:
        print(f"  [DEBUG] Status: {response.status_code}")
        print(f"  [DEBUG] Response: {response.text[:300]}")
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    # Strip reasoning tokens from models that output them
    if "<think>" in content:
        content = content.split("</think>")[-1].strip()
    return content


def _call_openai(system_prompt, user_prompt, api_key):
    """Call OpenAI API."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=500,
    )
    return response.choices[0].message.content


def _template_output(system_prompt, user_prompt):
    """Fallback template when no API key is available."""
    return """- Focus marketing investment in the top-performing country, which generated the majority of total revenue — expanding the customer base here has the highest ROI potential.
- Investigate the underperforming region's decline and consider targeted promotions or localized inventory adjustments to reverse the negative growth trend.
- With the forecast model showing strong accuracy over the baseline, use the projected next-month revenue to optimize inventory purchasing and cash flow planning."""


def validate_output(llm_output, summary):
    """Validate that LLM doesn't hallucinate numbers not in summary."""
    # Extract all numbers from LLM output
    numbers_in_output = re.findall(r"[\d,]+\.?\d*", llm_output)

    # Key numbers that should appear if referenced
    known_values = [
        str(int(summary["total_revenue_gbp"])),
        str(int(summary["top_country_revenue_gbp"])),
        f"{summary['latest_mom_growth_pct']:.1f}",
        f"{summary['latest_mom_growth_pct']:.2f}",
        str(int(summary["forecast_next_month_gbp"])),
        f"{summary['model_improvement_pct']:.1f}",
        f"{summary['model_improvement_pct']:.2f}",
    ]

    suspicious = []
    for num_str in numbers_in_output:
        clean = num_str.replace(",", "")
        if clean and clean not in known_values:
            try:
                val = float(clean)
                # Flag if it's a large round number not in known values (potential hallucination)
                if val > 1000 and val not in [summary["total_revenue_gbp"], summary["top_country_revenue_gbp"], summary["forecast_next_month_gbp"]]:
                    suspicious.append(num_str)
            except ValueError:
                pass

    if suspicious:
        print(f"  [VALIDATION WARNING] Potentially hallucinated numbers: {suspicious}")
    else:
        print("  [VALIDATION PASSED] No hallucinated numbers detected.")

    return len(suspicious) == 0


if __name__ == "__main__":
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    print("[LLM] Gathering KPIs from SQL + model outputs...")
    summary = gather_kpis()
    print(f"  Total Revenue: £{summary['total_revenue_gbp']:,.2f}")
    print(f"  Top Country: {summary['top_country']}")
    print(f"  MoM Growth: {summary['latest_mom_growth_pct']:.2f}%")
    print(f"  Forecast: £{summary['forecast_next_month_gbp']:,.2f}")

    system_prompt, user_prompt = build_prompt(summary)

    print("\n[LLM] Calling LLM for recommendations...")
    output = call_llm(system_prompt, user_prompt)

    print("\n  --- LLM Output ---")
    try:
        print(output)
    except UnicodeEncodeError:
        print(output.encode("ascii", errors="replace").decode())
    print("  ------------------\n")

    validate_output(output, summary)

    # Save
    out_path = os.path.join(OUTPUTS_DIR, "llm_recommendations.json")
    result = {"kpis": summary, "recommendations": output}
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[LLM] Saved to: {out_path}")
