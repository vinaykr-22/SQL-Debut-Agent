"""
Task definitions for the SQL Query Debug Agent environment.
Each task ships with schema, seed data, buggy query, and correct query.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class Task:
    task_name: str
    difficulty: Literal["easy", "medium", "hard"]
    schema_sql: str
    seed_sql: str
    buggy_query: str
    correct_query: str
    task_description: str


TASK_ACTIVE_CUSTOMERS = Task(
    task_name="active_customers_last_90_days",
    difficulty="easy",
    schema_sql="""
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    total_amount REAL NOT NULL
);
""".strip(),
    seed_sql="""
INSERT INTO customers (id, name, region) VALUES
(1, 'Ari Patel', 'West'),
(2, 'Bianca Lee', 'North'),
(3, 'Carlos Diaz', 'South'),
(4, 'Dana Scott', 'West'),
(5, 'Elena Rossi', 'North');

INSERT INTO orders (id, customer_id, order_date, total_amount) VALUES
(1, 1, '2025-10-05', 120.00),
(2, 2, '2025-12-09', 210.00),
(3, 3, '2025-12-22', 95.00),
(4, 4, '2025-08-16', 400.00),
(5, 1, '2025-11-11', 75.00),
(6, 5, '2025-12-25', 180.00),
(7, 2, '2025-07-01', 60.00);
""".strip(),
    buggy_query=(
        "SELECT c.name, MAX(o.order_date) AS last_order_date "
        "FROM customers c JOIN orders o ON c.id = o.id "
        "WHERE o.order_date >= date('2026-01-01', '-90 day') "
        "GROUP BY c.name ORDER BY c.name"
    ),
    correct_query=(
        "SELECT c.name, MAX(o.order_date) AS last_order_date "
        "FROM customers c JOIN orders o ON c.id = o.customer_id "
        "WHERE o.order_date >= date('2026-01-01', '-90 day') "
        "GROUP BY c.name ORDER BY c.name"
    ),
    task_description=(
        "List customers with at least one order in the last 90 days from 2026-01-01. "
        "Return columns name and last_order_date sorted by name. "
        "The query uses the wrong join key and misses valid customers."
    ),
)


TASK_SUPPORT_BACKLOG = Task(
    task_name="support_ticket_backlog_by_priority",
    difficulty="medium",
    schema_sql="""
CREATE TABLE agents (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    team TEXT NOT NULL
);

CREATE TABLE tickets (
    id INTEGER PRIMARY KEY,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    assigned_agent_id INTEGER
);
""".strip(),
    seed_sql="""
INSERT INTO agents (id, name, team) VALUES
(1, 'Noah', 'Platform'),
(2, 'Mia', 'Billing'),
(3, 'Omar', 'Platform');

INSERT INTO tickets (id, priority, status, opened_at, assigned_agent_id) VALUES
(1, 'P1', 'open', '2025-12-20', 1),
(2, 'P1', 'closed', '2025-12-21', 1),
(3, 'P2', 'open', '2025-12-22', 2),
(4, 'P3', 'open', '2025-12-25', NULL),
(5, 'P2', 'closed', '2025-12-27', 3),
(6, 'P1', 'open', '2025-12-29', 3),
(7, 'P3', 'open', '2025-12-29', NULL),
(8, 'P2', 'open', '2025-12-30', 2);
""".strip(),
    buggy_query="""SELECT priority, COUNT(*) AS backlog_count
FROM tickets
WHERE status = 'closed'
GROUP BY priority
ORDER BY backlog_count DESC""".strip(),
    correct_query="""SELECT priority, COUNT(*) AS backlog_count
FROM tickets
WHERE status = 'open'
GROUP BY priority
ORDER BY backlog_count DESC, priority""".strip(),
    task_description=(
        "Compute open support-ticket backlog by priority. "
        "Return priority and backlog_count, sorted by backlog_count descending and priority. "
        "The current query counts closed tickets instead of open tickets."
    ),
)


TASK_MONTHLY_MARGIN = Task(
    task_name="monthly_subscription_margin",
    difficulty="hard",
    schema_sql="""
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    plan TEXT NOT NULL,
    month TEXT NOT NULL,
    revenue REAL NOT NULL
);

CREATE TABLE infra_costs (
    month TEXT PRIMARY KEY,
    infra_cost REAL NOT NULL
);
""".strip(),
    seed_sql="""
INSERT INTO subscriptions (id, customer_id, plan, month, revenue) VALUES
(1, 101, 'pro', '2025-09', 120.00),
(2, 102, 'pro', '2025-09', 150.00),
(3, 103, 'basic', '2025-09', 60.00),
(4, 101, 'pro', '2025-10', 120.00),
(5, 104, 'enterprise', '2025-10', 420.00),
(6, 105, 'basic', '2025-10', 60.00),
(7, 106, 'pro', '2025-11', 150.00),
(8, 107, 'enterprise', '2025-11', 500.00),
(9, 108, 'basic', '2025-11', 60.00),
(10, 109, 'pro', '2025-11', 150.00);

INSERT INTO infra_costs (month, infra_cost) VALUES
('2025-09', 250.00),
('2025-10', 450.00),
('2025-11', 700.00);
""".strip(),
    buggy_query="""SELECT
    s.month,
    SUM(s.revenue) AS total_revenue,
    c.infra_cost,
    SUM(s.revenue) - c.infra_cost AS margin
FROM subscriptions s
JOIN infra_costs c ON s.month = c.infra_cost
GROUP BY s.month, c.infra_cost
ORDER BY s.month""".strip(),
    correct_query="""SELECT
    s.month,
    SUM(s.revenue) AS total_revenue,
    c.infra_cost,
    SUM(s.revenue) - c.infra_cost AS margin
FROM subscriptions s
JOIN infra_costs c ON s.month = c.month
GROUP BY s.month, c.infra_cost
HAVING SUM(s.revenue) - c.infra_cost > 0
ORDER BY s.month""".strip(),
    task_description=(
        "Find profitable months for subscriptions. "
        "Return month, total_revenue, infra_cost, margin. "
        "Include only months where margin is positive. "
        "The current query joins month to infra_cost and misses the required HAVING filter."
    ),
)


TASK_CHURN_RISK_REFUNDS = Task(
    task_name="churn_risk_accounts_with_refunds",
    difficulty="hard",
    schema_sql="""
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    account_name TEXT NOT NULL,
    segment TEXT NOT NULL
);

CREATE TABLE invoices (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    invoice_month TEXT NOT NULL,
    amount REAL NOT NULL
);

CREATE TABLE refunds (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL,
    refund_amount REAL NOT NULL,
    refund_date TEXT NOT NULL
);
""".strip(),
    seed_sql="""
INSERT INTO accounts (id, account_name, segment) VALUES
(1, 'Alpha Retail', 'mid_market'),
(2, 'Beta Logistics', 'enterprise'),
(3, 'Gamma Health', 'smb'),
(4, 'Delta Telecom', 'enterprise');

INSERT INTO invoices (id, account_id, invoice_month, amount) VALUES
(1, 1, '2025-10', 600.00),
(2, 1, '2025-11', 600.00),
(3, 2, '2025-10', 700.00),
(4, 2, '2025-11', 800.00),
(5, 3, '2025-11', 900.00),
(6, 4, '2025-10', 1200.00),
(7, 4, '2025-11', 800.00);

INSERT INTO refunds (id, invoice_id, refund_amount, refund_date) VALUES
(1, 1, 300.00, '2025-10-20'),
(2, 3, 100.00, '2025-10-22'),
(3, 6, 400.00, '2025-10-25'),
(4, 7, 200.00, '2025-11-26');
""".strip(),
    buggy_query="""SELECT
    a.account_name,
    SUM(i.amount) AS total_billed,
    COALESCE(SUM(r.refund_amount), 0) AS total_refunded,
    ROUND(COALESCE(SUM(r.refund_amount), 0) / SUM(i.amount), 4) AS refund_ratio
FROM accounts a
JOIN invoices i ON a.id = i.account_id
LEFT JOIN refunds r ON i.account_id = r.invoice_id
GROUP BY a.account_name
HAVING SUM(i.amount) >= 1000
ORDER BY refund_ratio DESC, a.account_name""".strip(),
    correct_query="""WITH account_rollup AS (
    SELECT
        a.account_name,
        SUM(i.amount) AS total_billed,
        COALESCE(SUM(r.refund_amount), 0) AS total_refunded
    FROM accounts a
    JOIN invoices i ON a.id = i.account_id
    LEFT JOIN refunds r ON i.id = r.invoice_id
    GROUP BY a.account_name
)
SELECT
    account_name,
    total_billed,
    total_refunded,
    ROUND(total_refunded / total_billed, 4) AS refund_ratio
FROM account_rollup
WHERE total_billed >= 1000
  AND (total_refunded / total_billed) >= 0.2
ORDER BY refund_ratio DESC, account_name""".strip(),
    task_description=(
        "Identify high refund-risk accounts for churn review. "
        "Return account_name, total_billed, total_refunded, refund_ratio for accounts with "
        "total_billed >= 1000 and refund_ratio >= 0.2. "
        "Sort by refund_ratio descending then account_name. "
        "The buggy query joins refunds using the wrong key and misses the refund-ratio filter."
    ),
)


TASKS: dict[str, Task] = {
    t.task_name: t
    for t in [
        TASK_ACTIVE_CUSTOMERS,
        TASK_SUPPORT_BACKLOG,
        TASK_MONTHLY_MARGIN,
        TASK_CHURN_RISK_REFUNDS,
    ]
}

__all__ = ["Task", "TASKS"]
