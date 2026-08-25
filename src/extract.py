import os
import kagglehub
import requests
import pandas as pd
from datetime import datetime, timedelta

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


def download_retail_dataset():
    """Download Online Retail II dataset from Kaggle via kagglehub."""
    print("[1/3] Downloading Online Retail II dataset from Kaggle...")
    path = kagglehub.dataset_download("mashlyn/online-retail-ii-uci")
    print(f"  Downloaded to: {path}")

    csv_files = [f for f in os.listdir(path) if f.endswith(".csv")]
    if not csv_files:
        raise FileNotFoundError("No CSV files found in downloaded dataset")

    src = os.path.join(path, csv_files[0])
    dst = os.path.join(RAW_DIR, "online_retail.csv")
    df = pd.read_csv(src, encoding="latin1")
    df.to_csv(dst, index=False)
    print(f"  Saved {len(df):,} rows to {dst}")
    return dst


def fetch_fx_rates():
    """Fetch GBP/USD daily rates from frankfurter.app (free, no key needed)."""
    print("[2/3] Fetching GBP/USD exchange rates from frankfurter.app...")

    start_date = "2009-12-01"
    end_date = "2011-12-31"

    url = f"https://api.frankfurter.app/{start_date}..{end_date}"
    params = {"from": "GBP", "to": "USD"}

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "rates" not in data:
        raise ValueError(f"API returned unexpected format: {data}")

    rates = []
    for date_str, rate_dict in data["rates"].items():
        rates.append({"date": date_str, "gbp_to_usd": rate_dict["USD"]})

    df = pd.DataFrame(rates)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    dst = os.path.join(RAW_DIR, "gbp_usd_rates.csv")
    df.to_csv(dst, index=False)
    print(f"  Saved {len(df):,} daily rates to {dst}")
    return dst


def inspect_data(csv_path):
    """Quick inspection of the raw dataset."""
    print("[3/3] Inspecting raw data...")
    df = pd.read_csv(csv_path)
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {list(df.columns)}")
    print(f"  Missing values:\n{df.isnull().sum().to_string()}")
    print(f"  Sample rows:\n{df.head(3).to_string()}")
    return df


if __name__ == "__main__":
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    csv_path = download_retail_dataset()
    fetch_fx_rates()
    inspect_data(csv_path)
    print("\nExtraction complete. Files ready in data/raw/")
