"""Synthetic Paytm merchant data. Run: python -m app.seed  (drops and recreates all tables)."""
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import insert, text

from app import models as m
from app.db import Base, engine, session_scope

IST = timezone(timedelta(hours=5, minutes=30))
FIRST = ["Ramesh", "Suresh", "Anita", "Sunita", "Mohan", "Vikram", "Priya", "Rahul", "Kavita", "Amit", "Neha",
         "Sanjay", "Pooja", "Deepak", "Meena", "Rajesh", "Sneha", "Ajay", "Geeta", "Manoj", "Rekha", "Nitin",
         "Asha", "Vijay", "Shweta", "Prakash", "Lata", "Santosh", "Jyoti", "Dinesh"]
LAST = ["Kulkarni", "Patil", "Sharma", "Deshmukh", "Joshi", "Jadhav", "Pawar", "Shinde", "More", "Gupta",
        "Verma", "Yadav", "Singh", "Kale", "Bhosale", "Chavan", "Nair", "Iyer"]

# name, category, price Rs, cost Rs, gst %, popularity weight, unit, distributor idx (0 dairy, 1 wholesale)
PRODUCTS: list[tuple[str, str, float, float, int, float, str, int]] = [
    ("Amul Doodh 500ml", "Dairy", 30, 27, 0, 14, "pcs", 0),
    ("Amul Butter 100g", "Dairy", 58, 52, 12, 2.5, "pcs", 0),
    ("Amul Dahi 400g", "Dairy", 45, 40, 5, 3, "pcs", 0),
    ("Fresh Paneer 200g", "Dairy", 90, 78, 5, 1.8, "pcs", 0),
    ("Britannia Bread", "Bakery", 40, 34, 0, 5, "pcs", 1),
    ("Eggs (6 pack)", "Dairy", 48, 42, 0, 3, "pack", 0),
    ("Aashirvaad Atta 5kg", "Staples", 265, 238, 5, 0.5, "pcs", 1),
    ("Basmati Rice 1kg", "Staples", 110, 94, 5, 0.8, "pcs", 1),
    ("Toor Dal 1kg", "Staples", 160, 142, 5, 0.7, "pcs", 1),
    ("Sugar 1kg", "Staples", 46, 41, 5, 3, "pcs", 1),
    ("Fortune Oil 1L", "Staples", 150, 134, 5, 0.7, "pcs", 1),
    ("Tata Salt 1kg", "Staples", 28, 24, 0, 2.2, "pcs", 1),
    ("Tata Tea 250g", "Staples", 130, 114, 5, 1.8, "pcs", 1),
    ("Parle-G Biscuit", "Snacks", 10, 8.5, 18, 9, "pcs", 1),
    ("Maggi Noodles", "Snacks", 14, 12, 12, 7, "pcs", 1),
    ("Kurkure", "Snacks", 20, 17, 12, 4, "pcs", 1),
    ("Lays Chips", "Snacks", 20, 17, 12, 4.5, "pcs", 1),
    ("Haldiram Bhujia 200g", "Snacks", 55, 47, 12, 2, "pcs", 1),
    ("Good Day Biscuit", "Snacks", 30, 26, 18, 3, "pcs", 1),
    ("Dairy Milk Chocolate", "Snacks", 40, 34, 18, 3, "pcs", 1),
    ("Coca-Cola 750ml", "Beverages", 40, 34, 28, 4, "pcs", 1),
    ("Frooti 200ml", "Beverages", 20, 17, 12, 3.5, "pcs", 1),
    ("Bisleri Water 1L", "Beverages", 20, 15, 18, 6, "pcs", 1),
    ("Real Juice 1L", "Beverages", 110, 96, 12, 1, "pcs", 1),
    ("Lux Soap", "Personal Care", 38, 33, 18, 2.5, "pcs", 1),
    ("Colgate 100g", "Personal Care", 58, 51, 18, 2.2, "pcs", 1),
    ("Clinic Plus Sachet", "Personal Care", 2, 1.6, 18, 4, "pcs", 1),
    ("Surf Excel 500g", "Household", 120, 106, 18, 1.5, "pcs", 1),
    ("Vim Bar", "Household", 10, 8, 18, 3, "pcs", 1),
    ("Harpic 500ml", "Household", 95, 83, 18, 0.8, "pcs", 1),
    ("Diya Pack (12)", "Festive", 60, 45, 12, 0.6, "pack", 1),
    ("Dry Fruits Box 250g", "Festive", 350, 300, 12, 0.5, "pcs", 1),
    ("Mithai Box 500g", "Festive", 280, 230, 5, 0.6, "pcs", 1),
    ("Incense Sticks", "Festive", 30, 22, 12, 1.2, "pcs", 1),
    ("Cooking Gas Lighter", "Household", 70, 55, 18, 0.5, "pcs", 1),
]

# hour of day weights (peaks 8-10 and 17-21)
HOUR_W = {7: 4, 8: 9, 9: 9, 10: 6, 11: 4, 12: 4, 13: 3, 14: 3, 15: 4, 16: 5, 17: 8, 18: 11, 19: 11, 20: 8, 21: 4}


def create_views() -> None:
    ms = "current_setting('app.merchant_id', true)::int"
    stmts = [
        f"""CREATE OR REPLACE VIEW v_sales AS SELECT (s.ts AT TIME ZONE 'Asia/Kolkata') AS ts_ist,
            s.amount_paise/100.0 AS amount_rupees, s.mode, c.name AS customer
            FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.merchant_id={ms}""",
        f"""CREATE OR REPLACE VIEW v_sale_items AS SELECT (s.ts AT TIME ZONE 'Asia/Kolkata') AS ts_ist,
            p.name AS product, p.category, i.qty, i.amount_paise/100.0 AS amount_rupees
            FROM sale_items i JOIN sales s ON s.id=i.sale_id JOIN products p ON p.id=i.product_id
            WHERE s.merchant_id={ms}""",
        f"""CREATE OR REPLACE VIEW v_products AS SELECT name, category, unit, price_paise/100.0 AS price_rupees,
            cost_paise/100.0 AS cost_rupees, stock_qty FROM products WHERE merchant_id={ms}""",
        f"""CREATE OR REPLACE VIEW v_khata AS SELECT c.name AS customer, k.amount_paise/100.0 AS amount_rupees,
            k.created_at, k.status, (CURRENT_DATE - k.created_at::date) AS days_pending
            FROM khata_entries k JOIN customers c ON c.id=k.customer_id WHERE k.merchant_id={ms}""",
    ]
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))


def _bulk(conn: Any, table: Any, rows: list[dict[str, Any]], chunk: int = 4000) -> None:
    for i in range(0, len(rows), chunk):
        conn.execute(insert(table), rows[i : i + chunk])


def _fix_seq(conn: Any, table: str) -> None:
    conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}','id'), COALESCE((SELECT MAX(id) FROM {table}),1))"))


def seed(days: int = 60) -> None:
    rnd = random.Random(42)
    with engine.begin() as conn:
        for v in ("v_sales", "v_sale_items", "v_products", "v_khata"):
            conn.execute(text(f"DROP VIEW IF EXISTS {v}"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    create_views()
    now = datetime.now(IST)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    with engine.begin() as conn:
        _bulk(conn, m.Merchant.__table__, [
            {"id": 1, "name": "Sharma General Store", "owner_name": "Sharma ji", "city": "Hinjawadi, Pune", "language": "hi", "phone": "9822000001"},
            {"id": 2, "name": "Patil Medical & General", "owner_name": "Patil saheb", "city": "Baner, Pune", "language": "mr", "phone": "9822000002"},
        ])
        _bulk(conn, m.Distributor.__table__, [
            {"id": 1, "merchant_id": 1, "name": "Gupta Dairy Distributors", "phone": "9890011111"},
            {"id": 2, "merchant_id": 1, "name": "Shree Ganesh Wholesale", "phone": "9890022222"},
            {"id": 3, "merchant_id": 2, "name": "Sai Pharma Wholesale", "phone": "9890033333"},
        ])
        prods = []
        for i, (n, cat, pr, co, gst, _w, unit, d) in enumerate(PRODUCTS, start=1):
            prods.append({"id": i, "merchant_id": 1, "distributor_id": d + 1, "name": n, "category": cat, "unit": unit,
                          "price_paise": int(pr * 100), "cost_paise": int(co * 100), "gst_rate": gst,
                          "stock_qty": 0, "reorder_qty": 48 if cat == "Dairy" else 24})
        base = len(prods)
        for j, (n, pr) in enumerate([("Paracetamol Strip", 25), ("ORS Sachet", 20), ("Dettol 100ml", 65), ("Biscuit Pack", 10)], start=1):
            prods.append({"id": base + j, "merchant_id": 2, "distributor_id": 3, "name": n, "category": "Medical",
                          "unit": "pcs", "price_paise": pr * 100, "cost_paise": int(pr * 80), "gst_rate": 12,
                          "stock_qty": 50, "reorder_qty": 30})
        _bulk(conn, m.Product.__table__, prods)

        # customers: 1..400 for merchant 1 (1..120 regulars, 81..120 lapsed), 401..420 for merchant 2
        customers = []
        for cid in range(1, 421):
            customers.append({"id": cid, "merchant_id": 1 if cid <= 400 else 2,
                              "name": f"{rnd.choice(FIRST)} {rnd.choice(LAST)}", "phone": f"98{22000000 + cid * 37:08d}"[:10]})
        customers[0]["name"] = "Ramesh Kulkarni"
        customers[1]["name"] = "Sunita Devi"
        customers[2]["name"] = "Mohan Patil"
        customers[3]["name"] = "Anita Joshi"
        customers[4]["name"] = "Vikram Shinde"
        _bulk(conn, m.Customer.__table__, customers)

        # ---- sales for merchant 1 ----
        weights = [p[5] for p in PRODUCTS]
        sales: list[dict[str, Any]] = []
        items: list[dict[str, Any]] = []
        sid = 0
        iid = 0
        hours = list(HOUR_W.keys())
        hw = list(HOUR_W.values())
        regulars = list(range(6, 121))  # ids 6..120; first five are khata customers
        lapsed = set(range(81, 121))
        for d in range(days, 0, -1):
            day = today - timedelta(days=d)
            wd = day.weekday()
            factor = {0: 0.92, 1: 0.95, 2: 0.97, 3: 1.0, 4: 1.06, 5: 1.15, 6: 1.12}[wd]
            if d <= 7:
                factor *= 1.05  # recent uplift
            n = int(rnd.gauss(285, 18) * factor)
            for _ in range(n):
                sid += 1
                hr = rnd.choices(hours, hw)[0]
                ts = day.replace(hour=hr, minute=rnd.randint(0, 59), second=rnd.randint(0, 59))
                cust: int | None = None
                if rnd.random() < 0.5:
                    pool = [c for c in regulars if not (c in lapsed and d <= 30)] if rnd.random() < 0.7 else None
                    cust = rnd.choice(pool) if pool else rnd.randint(121, 400)
                total = 0
                for pid in set(rnd.choices(range(1, len(PRODUCTS) + 1), weights, k=rnd.choice([1, 1, 1, 1, 2, 2]))):
                    iid += 1
                    qty = rnd.choice([1, 1, 1, 1, 2]) if PRODUCTS[pid - 1][2] < 50 else 1
                    amt = int(PRODUCTS[pid - 1][2] * 100) * qty
                    total += amt
                    items.append({"id": iid, "sale_id": sid, "product_id": pid, "qty": qty, "amount_paise": amt})
                sales.append({"id": sid, "merchant_id": 1, "customer_id": cust, "ts": ts, "amount_paise": total, "mode": "UPI"})

        # planted anomalies: a huge late-night payment and a rapid-fire burst of identical payments
        anomaly_day = today - timedelta(days=2)
        sid += 1
        sales.append({"id": sid, "merchant_id": 1, "customer_id": None, "ts": anomaly_day.replace(hour=2, minute=13),
                      "amount_paise": 1850000, "mode": "UPI"})
        burst_day = today - timedelta(days=3)
        for k in range(6):
            sid += 1
            sales.append({"id": sid, "merchant_id": 1, "customer_id": None,
                          "ts": burst_day.replace(hour=15, minute=40 + k // 2, second=10 * k % 60),
                          "amount_paise": 49900, "mode": "UPI"})

        # merchant 2 small history
        for d in range(20, 0, -1):
            for _ in range(rnd.randint(25, 40)):
                sid += 1
                day = today - timedelta(days=d)
                pid = base + rnd.randint(1, 4)
                price = next(p["price_paise"] for p in prods if p["id"] == pid)
                iid += 1
                sales.append({"id": sid, "merchant_id": 2, "customer_id": None, "ts": day.replace(hour=rnd.randint(9, 20), minute=rnd.randint(0, 59)),
                              "amount_paise": price * 2, "mode": "UPI"})
                items.append({"id": iid, "sale_id": sid, "product_id": pid, "qty": 2, "amount_paise": price * 2})

        _bulk(conn, m.Sale.__table__, sales)
        _bulk(conn, m.SaleItem.__table__, items)

        # stock from demand: milk ~2 days of cover, Maggi ~3 days, others healthy
        demand: dict[int, float] = {}
        for it in items:
            sale_day = next(s for s in [sales[it["sale_id"] - 1]])["ts"]
            if sale_day >= today - timedelta(days=14) and sales[it["sale_id"] - 1]["merchant_id"] == 1:
                demand[it["product_id"]] = demand.get(it["product_id"], 0) + it["qty"]
        for pid in range(1, len(PRODUCTS) + 1):
            daily = demand.get(pid, 1) / 14
            cover = 2.0 if pid == 1 else 3.0 if pid == 15 else rnd.uniform(6, 14)
            conn.execute(text("UPDATE products SET stock_qty=:q WHERE id=:i"), {"q": max(1, math.ceil(daily * cover)), "i": pid})

        # ---- khata ----
        def khata(cid: int, rupees_: int, days_ago: int, note: str) -> dict[str, Any]:
            return {"merchant_id": 1, "customer_id": cid, "amount_paise": rupees_ * 100, "note": note,
                    "created_at": now - timedelta(days=days_ago), "status": "open", "paid_at": None}

        _bulk(conn, m.KhataEntry.__table__, [
            khata(1, 1200, 15, "Monthly ration"), khata(2, 850, 22, "Atta, dal, oil"), khata(3, 2300, 18, "Diwali shopping"),
            khata(4, 400, 3, "Milk and bread"), khata(5, 650, 6, "Snacks"),
            {**khata(12, 500, 40, "Old udhaar"), "status": "recovered", "paid_at": now - timedelta(days=30)},
        ])
        for t in ("merchants", "distributors", "products", "customers", "sales", "sale_items", "khata_entries"):
            _fix_seq(conn, t)

        from app.seed_expiry import apply_expiry

        apply_expiry(conn)

    print(f"Seeded: {len(sales)} sales, {len(items)} items, {len(PRODUCTS)} products.")


if __name__ == "__main__":
    seed()
    with session_scope() as s:
        print("merchants:", s.query(m.Merchant).count())

