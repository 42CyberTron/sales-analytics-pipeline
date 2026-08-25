-- ============================================================
-- ANALYSIS QUERIES — Online Retail II Dataset
-- Run against db/sales.db after load_db.py
-- ============================================================

-- Q1: Monthly revenue by country
SELECT
    substr(invoice_date, 1, 7) AS month,
    c.country,
    ROUND(SUM(revenue_gbp), 2) AS revenue_gbp,
    ROUND(SUM(COALESCE(revenue_usd, revenue_gbp * 1.27)), 2) AS revenue_usd
FROM transactions t
JOIN customers c ON t.customer_id = c.customer_id
GROUP BY month, c.country
ORDER BY month, revenue_gbp DESC;

-- Q2: Top 10 products by total revenue
SELECT
    p.stock_code,
    p.description,
    ROUND(SUM(t.revenue_gbp), 2) AS total_revenue_gbp,
    COUNT(DISTINCT t.invoice_no) AS num_orders
FROM transactions t
JOIN products p ON t.stock_code = p.stock_code
GROUP BY p.stock_code, p.description
ORDER BY total_revenue_gbp DESC
LIMIT 10;

-- Q3: Customer cohort — first purchase month + retention by month
WITH first_purchase AS (
    SELECT customer_id, substr(MIN(invoice_date), 1, 7) AS cohort_month
    FROM transactions
    GROUP BY customer_id
),
activity AS (
    SELECT DISTINCT customer_id, substr(invoice_date, 1, 7) AS active_month
    FROM transactions
)
SELECT
    f.cohort_month,
    a.active_month,
    COUNT(DISTINCT a.customer_id) AS customers_active,
    (julianday(a.active_month || '-01') - julianday(f.cohort_month || '-01')) / 30 AS months_since_first
FROM first_purchase f
JOIN activity a ON f.customer_id = a.customer_id
GROUP BY f.cohort_month, a.active_month
ORDER BY f.cohort_month, a.active_month;

-- Q4: Month-over-month growth rate
WITH monthly AS (
    SELECT substr(invoice_date, 1, 7) AS month,
           ROUND(SUM(revenue_gbp), 2) AS revenue
    FROM transactions
    GROUP BY month
)
SELECT
    month,
    revenue,
    LAG(revenue) OVER (ORDER BY month) AS prev_month_revenue,
    ROUND(
        (revenue - LAG(revenue) OVER (ORDER BY month)) * 100.0 /
        NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 2
    ) AS mom_growth_pct
FROM monthly
ORDER BY month;

-- Q5: Average order value trend
WITH order_totals AS (
    SELECT invoice_no,
           substr(invoice_date, 1, 7) AS month,
           ROUND(SUM(revenue_gbp), 2) AS order_total
    FROM transactions
    GROUP BY invoice_no
)
SELECT
    month,
    COUNT(*) AS num_orders,
    ROUND(AVG(order_total), 2) AS avg_order_value,
    ROUND(MIN(order_total), 2) AS min_order,
    ROUND(MAX(order_total), 2) AS max_order
FROM order_totals
GROUP BY month
ORDER BY month;

-- Q6: Revenue by day of week (seasonality insight)
SELECT
    CASE CAST(strftime('%w', invoice_date) AS INTEGER)
        WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END AS day_of_week,
    ROUND(SUM(revenue_gbp), 2) AS total_revenue,
    COUNT(DISTINCT invoice_no) AS num_orders
FROM transactions
GROUP BY strftime('%w', invoice_date)
ORDER BY total_revenue DESC;

-- Q7: Top 5 customers by lifetime value
SELECT
    c.customer_id,
    c.country,
    ROUND(SUM(t.revenue_gbp), 2) AS lifetime_value,
    COUNT(DISTINCT t.invoice_no) AS total_orders
FROM transactions t
JOIN customers c ON t.customer_id = c.customer_id
GROUP BY c.customer_id, c.country
ORDER BY lifetime_value DESC
LIMIT 5;

-- Q8: Country contribution to total revenue (% share)
WITH country_rev AS (
    SELECT c.country, ROUND(SUM(t.revenue_gbp), 2) AS revenue
    FROM transactions t
    JOIN customers c ON t.customer_id = c.customer_id
    GROUP BY c.country
)
SELECT
    country,
    revenue,
    ROUND(revenue * 100.0 / SUM(revenue) OVER (), 2) AS pct_of_total
FROM country_rev
ORDER BY revenue DESC;
