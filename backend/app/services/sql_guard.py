"""Read-only, merchant-scoped text-to-SQL guard.

Defence in depth: (1) sqlglot AST allows only a single SELECT over whitelisted views,
(2) the views filter on a per-transaction `app.merchant_id` setting,
(3) the transaction is READ ONLY with a statement timeout and a row cap.
"""
from typing import Any

import sqlglot
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlglot import exp

from app.core import AppError

ALLOWED_VIEWS = {"v_sales", "v_sale_items", "v_products", "v_khata"}
MAX_ROWS = 50

SCHEMA_HINT = """Dialect: PostgreSQL (use CURRENT_DATE - INTERVAL '7 days', never SQLite date('now')).
Views (all already scoped to the current merchant; amounts in rupees; ts_ist is IST local time):
v_sales(ts_ist timestamp, amount_rupees numeric, mode text, customer text)
v_sale_items(ts_ist timestamp, product text, category text, qty int, amount_rupees numeric)
v_products(name text, category text, unit text, price_rupees numeric, cost_rupees numeric, stock_qty int)
v_khata(customer text, amount_rupees numeric, created_at timestamptz, status text, days_pending int)"""


class UnsafeSQLError(AppError):
    code = "unsafe_sql"


def validate(sql: str) -> str:
    try:
        trees = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as exc:
        raise UnsafeSQLError("Could not parse SQL") from exc
    if len(trees) != 1 or trees[0] is None or not isinstance(trees[0], exp.Select):
        raise UnsafeSQLError("Only a single SELECT statement is allowed")
    tree = trees[0]
    banned = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Command, exp.Alter)
    if any(tree.find(b) for b in banned):
        raise UnsafeSQLError("Statement contains a write or DDL operation")
    cte_names = {c.alias_or_name for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        if t.name not in ALLOWED_VIEWS and t.name not in cte_names:
            raise UnsafeSQLError(f"Table '{t.name}' is not allowed")
    for fn in tree.find_all(exp.Anonymous):
        if fn.name.lower().startswith(("pg_", "set_config", "current_setting", "dblink", "lo_")):
            raise UnsafeSQLError("Function not allowed")
    return tree.sql(dialect="postgres")


def run_scoped(s: Session, merchant_id: int, sql: str) -> list[dict[str, Any]]:
    safe = validate(sql)
    conn = s.connection()
    conn.execute(text("SET TRANSACTION READ ONLY"))
    conn.execute(text("SET LOCAL statement_timeout = '4000'"))
    conn.execute(text("SELECT set_config('app.merchant_id', :m, true)"), {"m": str(int(merchant_id))})
    res = conn.execute(text(f"SELECT * FROM ({safe}) AS q LIMIT {MAX_ROWS}"))
    rows = [dict(r._mapping) for r in res]
    s.rollback()
    return [{k: (float(v) if hasattr(v, "as_tuple") else (v.isoformat() if hasattr(v, "isoformat") else v))
             for k, v in r.items()} for r in rows]
