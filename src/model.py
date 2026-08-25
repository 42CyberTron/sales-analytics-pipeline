import os
import sqlite3
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.metrics import mean_squared_error, mean_absolute_error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "sales.db")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")


def load_monthly_revenue():
    """Aggregate transactions to monthly time series (from SQL, not raw CSV)."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT substr(invoice_date, 1, 7) AS month, SUM(revenue_gbp) AS revenue
        FROM transactions
        GROUP BY month
        ORDER BY month
    """, conn)
    conn.close()
    df["month"] = pd.to_datetime(df["month"])
    df = df.set_index("month")
    df.index.freq = "MS"
    return df


def baseline_forecast(train, test, window=3):
    """Naive moving-average baseline."""
    last_avg = train["revenue"].tail(window).mean()
    predictions = [last_avg] * len(test)
    return np.array(predictions)


def run_holtwinters(train, test_periods):
    """Fit Holt-Winters exponential smoothing (handles trend + seasonality)."""
    model = ExponentialSmoothing(
        train["revenue"],
        trend="add",
        seasonal="add",
        seasonal_periods=6,
        damped_trend=True,
    ).fit(optimized=True)

    forecast = model.forecast(test_periods)
    return model, forecast


def evaluate(actual, predicted):
    """Compute RMSE and MAE."""
    rmse = np.sqrt(mean_squared_error(actual, predicted))
    mae = mean_absolute_error(actual, predicted)
    return rmse, mae


def plot_results(train, test, forecast_values, baseline_preds, metrics):
    """Save actual vs predicted chart."""
    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(train.index, train["revenue"], "b-o", label="Train", markersize=4)
    ax.plot(test.index, test["revenue"], "g-o", label="Actual (Test)", markersize=5)
    ax.plot(test.index, baseline_preds, "r--s", label="Baseline (MA-3)", markersize=5)
    ax.plot(test.index, forecast_values, "m-D", label="Holt-Winters Forecast", markersize=5)

    ax.set_title("Monthly Revenue Forecast: Holt-Winters vs Baseline", fontsize=14)
    ax.set_xlabel("Month")
    ax.set_ylabel("Revenue (GBP)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    chart_path = os.path.join(OUTPUTS_DIR, "forecast_chart.png")
    fig.savefig(chart_path, dpi=150)
    plt.close(fig)
    return chart_path


def build_summary_metrics(metrics, output_path):
    """Write metrics JSON."""
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    return output_path


if __name__ == "__main__":
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    print("[MODEL] Loading monthly revenue from SQL...")
    df = load_monthly_revenue()
    print(f"  {len(df)} months of data from {df.index.min().date()} to {df.index.max().date()}")

    # Train/test split: last 3 months held out
    test_months = 3
    train = df.iloc[:-test_months].copy()
    test = df.iloc[-test_months:].copy()
    print(f"  Train: {len(train)} months, Test: {len(test)} months")

    # Baseline
    print("\n[MODEL] Running baseline (3-month moving average)...")
    baseline_preds = baseline_forecast(train, test, window=3)
    baseline_rmse, baseline_mae = evaluate(test["revenue"].values, baseline_preds)
    print(f"  Baseline RMSE: {baseline_rmse:,.2f} | MAE: {baseline_mae:,.2f}")

    # Holt-Winters
    print("\n[MODEL] Running Holt-Winters Exponential Smoothing...")
    model, forecast = run_holtwinters(train, test_periods=test_months)
    forecast_values = forecast.values
    hw_rmse, hw_mae = evaluate(test["revenue"].values, forecast_values)
    print(f"  Holt-Winters RMSE: {hw_rmse:,.2f} | MAE: {hw_mae:,.2f}")

    # Improvement
    improvement_pct = round((baseline_rmse - hw_rmse) / baseline_rmse * 100, 2)

    # Next month forecast (beyond available data)
    next_month_forecast = float(model.forecast(test_months + 1).iloc[-1])

    metrics = {
        "model": "Holt-Winters Exponential Smoothing",
        "baseline": "3-month moving average",
        "baseline_rmse": round(baseline_rmse, 2),
        "baseline_mae": round(baseline_mae, 2),
        "hw_rmse": round(hw_rmse, 2),
        "hw_mae": round(hw_mae, 2),
        "improvement_pct": improvement_pct,
        "train_months": len(train),
        "test_months": test_months,
        "test_periods": [str(d.date()) for d in test.index],
        "actual": [round(v, 2) for v in test["revenue"].values],
        "baseline_predicted": [round(v, 2) for v in baseline_preds],
        "hw_predicted": [round(v, 2) for v in forecast_values],
        "forecast_next_month": round(next_month_forecast, 2),
        "model_params": {
            "trend": "additive",
            "seasonal": "additive",
            "seasonal_periods": 6,
            "damped_trend": True,
        },
    }

    print(f"\n  Improvement: {improvement_pct}% lower RMSE than baseline")

    # Save forecast dataframe
    forecast_df = pd.DataFrame({
        "month": list(test.index) + [test.index[-1] + pd.DateOffset(months=1)],
        "forecast_gbp": list(forecast_values) + [next_month_forecast],
        "is_future": [False] * test_months + [True],
    })
    forecast_df.to_csv(os.path.join(PROCESSED_DIR, "forecast_output.csv"), index=False)

    # Plot
    chart_path = plot_results(train, test, forecast_values, baseline_preds, metrics)
    print(f"\n  Chart saved to: {chart_path}")

    # Save metrics
    metrics_path = os.path.join(OUTPUTS_DIR, "model_metrics.json")
    build_summary_metrics(metrics, metrics_path)
    print(f"  Metrics saved to: {metrics_path}")

    print("\n[MODEL] Complete.")
    print(f"  Forecast next month: {metrics['forecast_next_month']:,.2f} GBP")
    print(f"  Holt-Winters params: trend={model.model.trend}, seasonal={model.model.seasonal}, "
          f"damped={model.model.damped_trend}")
