"""Build a deterministic synthetic SME credit-file database.

The book is fictional. Seed 42 keeps the story stable for the write-up:
some files are overdue, a handful of balance sheets do not balance,
and a few margins sit far from their segment.
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "sme.db"
SCHEMA = (ROOT / "schema.sql").read_text(encoding="utf-8")

SEGMENTS = ("Manufacturing", "Wholesale", "Professional services", "Construction")
CITIES = ("Bratislava", "Bratislava", "Bratislava", "Pezinok", "Senec", "Malacky")
MANAGERS = ("Elena Horvath", "Peter Krajci", "Lucia Benova", "Martin Sabol")
DOC_TYPES = ("annual_statements", "notes", "tax_return", "bank_confirmation")

STEMS = [
    "Dunaj", "Karpat", "Vah", "Hron", "Morava", "Nitra", "Torysa", "Poprad",
    "Orava", "Ipel", "Laborec", "Rimava", "Slana", "Zitava", "Topla", "Hornad",
    "Vahsky", "Rudava", "Myjava", "Cierny", "Biely", "Malý", "Velky", "Stary",
]
TAILS = {
    "Manufacturing": ["Form", "Metal", "Pack", "Press", "Mill", "Cast"],
    "Wholesale": ["Trade", "Supply", "Market", "Goods", "Link", "Store"],
    "Professional services": ["Advisory", "Studio", "Office", "Partner", "Group", "Desk"],
    "Construction": ["Stav", "Build", "Site", "Frame", "Mont", "Ground"],
}


def company_name(rng: random.Random, segment: str, used: set[str]) -> str:
    for _ in range(50):
        name = f"{rng.choice(STEMS)} {rng.choice(TAILS[segment])} s.r.o."
        if name not in used:
            used.add(name)
            return name
    raise RuntimeError("could not mint a unique company name")


def build() -> None:
    rng = random.Random(42)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    companies = []
    used: set[str] = set()
    for i in range(1, 85):
        segment = SEGMENTS[(i - 1) % 4]
        companies.append(
            {
                "id": i,
                "name": company_name(rng, segment, used),
                "ico": f"99{i:06d}",
                "city": rng.choice(CITIES),
                "segment": segment,
                "employees": rng.randint(8, 180),
                "rm": MANAGERS[(i - 1) % 4],
                "since": f"{rng.randint(2016, 2023)}-{rng.randint(1, 12):02d}-01",
            }
        )

    # Forced story beats so the case is not a flat random cloud.
    missing_statement = {3, 11, 18, 27, 36, 44, 52, 63, 71}
    broken_balance = {7, 15, 22, 33, 48, 59, 76}
    fat_margin = {5, 29, 41, 68}
    thin_margin = {9, 54}
    overdue_heavy = {3, 6, 11, 14, 18, 21, 27, 30, 36, 39, 44, 47, 52, 58, 63, 66, 71, 80}

    statements = []
    documents = []
    sid = 0
    did = 0

    for company in companies:
        cid = company["id"]
        base_revenue = rng.randint(400_000, 6_500_000)
        for year, growth in ((2023, 1.0), (2024, rng.uniform(0.92, 1.14)), (2025, rng.uniform(0.90, 1.12))):
            if year == 2025 and cid in missing_statement:
                continue
            revenue = int(base_revenue * growth) if year > 2023 else base_revenue
            if year == 2024:
                base_revenue = revenue
            margin = rng.uniform(0.03, 0.12)
            if year == 2025 and cid in fat_margin:
                margin = rng.uniform(0.34, 0.48)
            if year == 2025 and cid in thin_margin:
                margin = rng.uniform(-0.22, -0.12)
            net_income = int(revenue * margin)
            ebit = int(net_income * rng.uniform(1.15, 1.45))
            assets = int(revenue * rng.uniform(0.55, 1.15))
            equity = int(assets * rng.uniform(0.22, 0.55))
            liabilities = assets - equity
            if year == 2025 and cid in broken_balance:
                liabilities -= rng.choice([18_000, 42_000, 75_000, 120_000])
            cash = int(assets * rng.uniform(0.04, 0.18))
            receivables = int(revenue * rng.uniform(0.08, 0.28))
            received = None
            if year < 2025 or cid not in missing_statement:
                month = 5 if year < 2025 else rng.randint(4, 8)
                received = f"{year + 1}-{month:02d}-{rng.randint(1, 27):02d}"
            sid += 1
            statements.append(
                (
                    sid, cid, year, revenue, ebit, net_income, assets, equity,
                    liabilities, cash, receivables, received,
                )
            )

        for doc_type in DOC_TYPES:
            did += 1
            requested = "2026-03-16"
            due = "2026-05-31" if doc_type != "tax_return" else "2026-06-30"
            received = None
            roll = rng.random()
            if cid in overdue_heavy and doc_type == "annual_statements":
                received = None
            elif roll < 0.90:
                received = f"2026-0{rng.randint(4, 6)}-{rng.randint(1, 27):02d}"
            elif roll < 0.96:
                received = f"2026-07-{rng.randint(1, 20):02d}"
            documents.append((did, cid, 2025, doc_type, requested, due, received))

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            """
            INSERT INTO companies
              (id, name, ico, city, segment, employees, relationship_manager, client_since)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (c["id"], c["name"], c["ico"], c["city"], c["segment"], c["employees"], c["rm"], c["since"])
                for c in companies
            ],
        )
        conn.executemany(
            """
            INSERT INTO statements (
              id, company_id, fiscal_year, revenue_eur, ebit_eur, net_income_eur,
              total_assets_eur, equity_eur, liabilities_eur, cash_eur, receivables_eur, received_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            statements,
        )
        conn.executemany(
            """
            INSERT INTO documents (
              id, company_id, fiscal_year, doc_type, requested_on, due_on, received_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            documents,
        )
        conn.commit()
        _assert_story(conn)
    finally:
        conn.close()
    print(f"wrote {DB_PATH}")


def _assert_story(conn: sqlite3.Connection) -> None:
    overdue = conn.execute(
        "SELECT COUNT(*) FROM v_file_status WHERE docs_overdue > 0"
    ).fetchone()[0]
    missing = conn.execute(
        "SELECT COUNT(*) FROM v_file_status WHERE latest_statement_year < 2025"
    ).fetchone()[0]
    broken = conn.execute(
        "SELECT COUNT(*) FROM v_statement_quality WHERE fiscal_year = 2025 AND ABS(imbalance_eur) >= 1000"
    ).fetchone()[0]
    outliers = conn.execute(
        """
        SELECT COUNT(*)
        FROM v_statement_quality q
        JOIN companies c ON c.id = q.company_id
        JOIN v_segment_margin seg
          ON seg.segment = c.segment AND seg.fiscal_year = q.fiscal_year
        WHERE q.fiscal_year = 2025
          AND ABS(q.net_margin - seg.avg_net_margin) >= 0.20
        """
    ).fetchone()[0]
    print(f"overdue files={overdue} missing statements={missing} broken={broken} outliers={outliers}")
    if not (10 <= overdue <= 36 and missing >= 6 and broken >= 5 and outliers >= 4):
        raise SystemExit("story shape is too flat; adjust the generator")


if __name__ == "__main__":
    build()
