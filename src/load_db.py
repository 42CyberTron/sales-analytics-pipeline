import os
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "sales.db")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")


def load_raw_to_db(conn):
    """Load the raw CSV as a staging table."""
    df = pd.read_csv(os.path.join(RAW_DIR, "online_retail.csv"), encoding="latin1")
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = df.rename(columns={
        "invoicedate": "invoice_date",
        "price": "unit_price",
        "customer_id": "customer_id",
    })

    df["invoice_date"] = pd.to_datetime(df["invoice_date"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df["customer_id"] = pd.to_numeric(df["customer_id"], errors="coerce").astype("Int64")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")

    df.to_sql("raw_transactions", conn, if_exists="replace", index=False)
    print(f"  Loaded {len(df):,} rows into raw_transactions")


def load_fx_rates(conn):
    """Load FX rates into the fx_rates table."""
    fx = pd.read_csv(os.path.join(RAW_DIR, "gbp_usd_rates.csv"))
    fx.to_sql("fx_rates", conn, if_exists="replace", index=False)
    print(f"  Loaded {len(fx):,} FX rate rows")


def create_schema(conn):
    """Execute the normalized schema."""
    schema_path = os.path.join(BASE_DIR, "db", "schema.sql")
    with open(schema_path) as f:
        conn.executescript(f.read())
    print("  Schema created")


def normalize_data(conn):
    """Populate normalized tables from raw_transactions."""
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO customers (customer_id, country)
        SELECT DISTINCT CAST(customer_id AS INTEGER), country
        FROM raw_transactions
        WHERE customer_id IS NOT NULL
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO products (stock_code, description)
        SELECT DISTINCT stockcode, description
        FROM raw_transactions
        WHERE stockcode IS NOT NULL
          AND description IS NOT NULL
          AND description != ''
    """)

    cursor.execute("""
        INSERT INTO transactions (invoice_no, stock_code, customer_id, quantity, unit_price, invoice_date, revenue_gbp)
        SELECT invoice, stockcode, CAST(customer_id AS INTEGER), quantity, unit_price, invoice_date,
               quantity * unit_price AS revenue_gbp
        FROM raw_transactions
        WHERE quantity > 0 AND unit_price > 0
          AND customer_id IS NOT NULL
          AND stockcode IS NOT NULL
    """)

    conn.commit()
    print(f"  Normalized: {cursor.rowcount} rows in transactions")


def join_fx_rates(conn):
    """Join FX rates to transactions for USD-normalized revenue."""
    conn.execute("""
        UPDATE transactions
        SET revenue_usd = revenue_gbp * (
            SELECT gbp_to_usd FROM fx_rates
            WHERE fx_rates.date = substr(transactions.invoice_date, 1, 10)
        )
        WHERE substr(transactions.invoice_date, 1, 10) IN (SELECT date FROM fx_rates)
    """)
    conn.commit()
    print("  Joined FX rates -> revenue_usd column populated")


def clean_and_export(conn):
    """Export cleaned data for downstream use."""
    df = pd.read_sql("SELECT * FROM transactions", conn)
    df.to_csv(os.path.join(PROCESSED_DIR, "cleaned_transactions.csv"), index=False)
    print(f"  Exported {len(df):,} cleaned rows to data/processed/")


if __name__ == "__main__":
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    print("[DB] Building normalized schema...\n")

    load_raw_to_db(conn)
    load_fx_rates(conn)
    create_schema(conn)
    normalize_data(conn)
    join_fx_rates(conn)
    clean_and_export(conn)

    conn.close()
    print("\n[DB] Pipeline complete. Database ready at db/sales.db")
