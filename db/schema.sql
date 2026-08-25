CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    country    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    stock_code TEXT PRIMARY KEY,
    description TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    invoice_no   TEXT NOT NULL,
    stock_code   TEXT NOT NULL,
    customer_id  INTEGER,
    quantity     INTEGER NOT NULL,
    unit_price   REAL NOT NULL,
    invoice_date TEXT NOT NULL,
    revenue_gbp  REAL NOT NULL,
    revenue_usd  REAL,
    FOREIGN KEY (stock_code) REFERENCES products(stock_code),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS fx_rates (
    date       TEXT PRIMARY KEY,
    gbp_to_usd REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(invoice_date);
CREATE INDEX IF NOT EXISTS idx_transactions_customer ON transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_stock ON transactions(stock_code);
