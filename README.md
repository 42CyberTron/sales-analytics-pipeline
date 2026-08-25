# Sales Analytics & Forecasting Pipeline

> End-to-end data pipeline that ingests 1M+ e-commerce transactions, normalizes them into a relational database, performs SQL revenue analysis with live FX rates, forecasts revenue with Holt-Winters exponential smoothing, and delivers automated Excel reports + LLM-generated client recommendations.

---

## Table of Contents

- [Results at a Glance](#results-at-a-glance)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Setup & Run](#setup--run)
- [Data & Methodology](#data--methodology)
- [Key Findings](#key-findings)
- [Project Structure](#project-structure)
- [Resume Bullets](#resume-bullets)

---

## Results at a Glance

| Metric | Value |
|--------|-------|
| **Dataset** | 1,067,371 invoice rows → 805,549 clean transactions |
| **Forecast Model** | Holt-Winters Exponential Smoothing (additive trend + seasonality) |
| **Baseline** | 3-month moving average |
| **Baseline RMSE** | £328,685.37 |
| **Model RMSE** | £266,645.82 |
| **Improvement** | **18.88% lower RMSE** |
| **Validation** | 3-month holdout (Oct–Dec 2011) |
| **Next Month Forecast** | £800,040.96 |
| **Total Revenue Analyzed** | £17,743,429.18 |

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Kaggle CSV │────▶│  Extract &   │────▶│  Normalized  │────▶│  8 SQL       │
│  + FX API   │     │  Clean       │     │  SQLite DB   │     │  Queries     │
└─────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                     │
                                     ┌───────────────────────────────┤
                                     ▼                               ▼
                              ┌──────────────┐               ┌──────────────┐
                              │  Holt-Winters│               │  Excel Report│
                              │  Forecast    │               │  (openpyxl)  │
                              └──────┬───────┘               └──────┬───────┘
                                     │                               │
                                     ▼                               ▼
                              ┌──────────────┐               ┌──────────────┐
                              │  LLM         │               │  Client PDF  │
                              │  Insights    │               │  Summary     │
                              └──────────────┘               └──────────────┘
```

---

## Tech Stack

**Languages:** Python 3.11, SQL
**Libraries:** pandas, numpy, statsmodels, openpyxl, matplotlib, reportlab, scikit-learn, python-dotenv
**Database:** SQLite (normalized 3NF schema)
**APIs:** KaggleHub (dataset), Frankfurter (FX rates), Groq (LLM inference)
**Output:** Excel (.xlsx) with native charts, PDF client summary

---

## Setup & Run

### Prerequisites
- Python 3.10+
- A free [Groq API key](https://console.groq.com/keys) (for LLM insights)

### 1. Clone & install
```bash
git clone https://github.com/yourusername/sales-analytics-pipeline.git
cd sales-analytics-pipeline
pip install -r requirements.txt
```

### 2. Add your API key
Create a `.env` file in the project root:
```
GROQ_API_KEY=gsk_your_key_here
```

### 3. Run the full pipeline
```bash
python src/extract.py        # Download dataset + fetch GBP/USD rates
python src/load_db.py        # Normalize into SQLite (3NF)
python src/model.py          # Train Holt-Winters, generate forecast
python src/excel_report.py   # Build multi-tab Excel report
python src/llm_insights.py   # Generate LLM recommendations
python src/client_summary.py # Build client-facing PDF
```

Each step is idempotent — outputs overwrite on re-run.

---

## Data & Methodology

### Data Sources
- **Primary:** [Online Retail II](https://www.kaggle.com/datasets/mashlyn/online-retail-ii-uci) — 1M+ invoice-level transactions from a UK e-commerce retailer (2009–2011)
- **Secondary:** [Frankfurter API](https://frankfurter.app) — daily GBP/USD exchange rates, joined at invoice-date granularity

### Normalization
Raw CSV → 3NF relational schema:
- `customers` (5,942 unique customers)
- `products` (4,950 unique products)
- `transactions` (805,549 clean rows, excluding cancelled/zero-value orders)
- `fx_rates` (537 daily rates)

### Forecasting
- **Model:** Holt-Winters Exponential Smoothing (additive trend + additive seasonality, damped)
- **Train/test split:** 22 months train / 3 months holdout
- **Baseline:** 3-month moving average (naive forecast)
- **Result:** 18.88% RMSE improvement — Holt-Winters captures trend and half-yearly seasonality that the flat baseline misses

### LLM Layer
- **Provider:** Groq (`openai/gpt-oss-120b`)
- **Validation:** Output checked against source KPIs to flag hallucinated numbers
- **Output:** 3 plain-English business recommendations with specific figures

---

## Key Findings

1. **UK dominates revenue** — £14.7M of £17.7M total (83%), followed by EIRE (3.5%) and Netherlands (3.1%)
2. **Sharp recent decline** — latest month-over-month growth was -55.40%, signaling a potential seasonal or operational issue
3. **Top product:** REGENCY CAKESTAND 3 TIER generated £286K in revenue across 2,000+ orders
4. **Top customer:** Customer ID 18102 (UK) with £608K lifetime value across 92 orders
5. **Seasonality is real** — Holt-Winters outperforms the moving-average baseline by 18.88% because it models the underlying trend and seasonal pattern

---

## Project Structure

```
sales-analytics-pipeline/
├── data/
│   ├── raw/                  # Original CSV + FX rates (gitignored)
│   └── processed/            # Cleaned data + forecast output (gitignored)
├── db/
│   ├── schema.sql            # Normalized 3NF schema (CREATE TABLE statements)
│   └── sales.db              # Populated SQLite database (gitignored)
├── src/
│   ├── extract.py            # Kaggle download + FX API fetch
│   ├── load_db.py            # CSV → normalized SQLite (INSERT INTO ... SELECT)
│   ├── queries.sql           # 8 analysis queries (revenue, cohort, MoM, etc.)
│   ├── model.py              # Holt-Winters forecast + baseline comparison
│   ├── excel_report.py       # 4-tab Excel report with native charts
│   ├── llm_insights.py       # Groq API → 3 business recommendations
│   └── client_summary.py     # PDF generation with reportlab
├── outputs/                  # Generated reports (gitignored)
│   ├── report.xlsx
│   ├── summary.pdf
│   ├── forecast_chart.png
│   ├── model_metrics.json
│   └── llm_recommendations.json
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Resume Bullets

Use these for your resume / LinkedIn. Pick the ones that match the role you're targeting.

**For Data Analyst roles:**
- Built an end-to-end sales analytics pipeline processing 1M+ e-commerce transactions — normalized raw CSV into a 3NF SQLite schema (customers, products, transactions), wrote 8 SQL queries for revenue/cohort analysis, and joined a live FX-rate API to produce GBP- and USD-normalized reporting.
- Forecasted monthly revenue using Holt-Winters exponential smoothing, achieving **18.88% lower RMSE** (£266,646 vs £328,685 baseline) validated on a 3-month holdout period (Oct–Dec 2011).
- Automated a multi-tab Excel report (KPIs, trend charts, forecast, raw data) and an LLM-generated client recommendation summary — replicating a business analyst's weekly reporting workflow end-to-end.

**For Data Engineer / Pipeline roles:**
- Designed and built a repeatable ETL pipeline: extracted 1M+ rows via KaggleHub, transformed and loaded into a normalized SQLite database (805K clean records from 5,942 customers and 4,950 products), and joined live FX rates from a REST API at invoice-date granularity.
- Engineered a forecasting module comparing Holt-Winters exponential smoothing against a moving-average baseline — documented model selection rationale, train/test split methodology, and RMSE/MAE metrics in a structured JSON deliverable.
- Implemented an LLM integration layer (Groq API) with hallucination detection — validates generated recommendations against source KPIs to ensure factual accuracy before client delivery.

**For ML / Forecasting roles:**
- Developed a time-series forecasting solution for monthly revenue using Holt-Winters exponential smoothing (additive trend + seasonality, damped), outperforming a 3-month moving-average baseline by **18.88% on RMSE** with a 3-month holdout validation strategy.
- Constructed a full analytics pipeline from raw ingestion through SQL aggregation to model input — ensuring the forecasting module consumed structured SQL output rather than raw data, maintaining reproducibility and auditability.
- Evaluated model performance with RMSE, MAE, and percentage improvement metrics; visualized actual vs. predicted values with confidence intervals for stakeholder communication.

---

## License

MIT
