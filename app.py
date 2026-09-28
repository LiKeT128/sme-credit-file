"""Local dashboard for the SME credit-file case. Standard library only."""

from __future__ import annotations

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "sme.db"
STATIC = ROOT / "static"
HOST = "127.0.0.1"
PORT = 8765

QUERIES = {
    "chase": (ROOT / "sql" / "01_chase_list.sql").read_text(encoding="utf-8"),
    "breaks": (ROOT / "sql" / "02_balance_sheet_breaks.sql").read_text(encoding="utf-8"),
    "margins": (ROOT / "sql" / "03_margin_vs_segment.sql").read_text(encoding="utf-8"),
    "cycle": (ROOT / "sql" / "04_cycle_time.sql").read_text(encoding="utf-8"),
}


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Missing {DB_PATH}. Run build_db.py first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows(sql: str, params: tuple = ()) -> list[dict]:
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def summary() -> dict:
    book = rows("SELECT COUNT(*) AS companies FROM companies")[0]
    files = rows(
        """
        SELECT
          SUM(CASE WHEN docs_overdue > 0 THEN 1 ELSE 0 END) AS overdue_files,
          SUM(CASE WHEN latest_statement_year < 2025 THEN 1 ELSE 0 END) AS missing_statements,
          ROUND(100.0 * SUM(docs_received) / SUM(docs_expected), 1) AS docs_complete_pct
        FROM v_file_status
        """
    )[0]
    quality = rows(
        """
        SELECT COUNT(*) AS broken
        FROM v_statement_quality
        WHERE fiscal_year = 2025 AND ABS(imbalance_eur) >= 1000
        """
    )[0]
    return {**book, **files, **quality, "as_of": rows("SELECT date('now') AS as_of")[0]["as_of"]}


def company(company_id: int) -> dict | None:
    found = rows("SELECT * FROM companies WHERE id = ?", (company_id,))
    if not found:
        return None
    return {
        "company": found[0],
        "statements": rows(
            """
            SELECT fiscal_year, revenue_eur, ebit_eur, net_income_eur,
                   total_assets_eur, equity_eur, liabilities_eur, imbalance_eur,
                   ROUND(100.0 * net_margin, 1) AS net_margin_pct, received_on
            FROM v_statement_quality
            WHERE company_id = ?
            ORDER BY fiscal_year
            """,
            (company_id,),
        ),
        "documents": rows(
            """
            SELECT doc_type, requested_on, due_on, received_on,
                   CASE
                     WHEN received_on IS NULL AND due_on < date('now') THEN 'overdue'
                     WHEN received_on IS NULL THEN 'open'
                     WHEN received_on > due_on THEN 'late'
                     ELSE 'on time'
                   END AS state
            FROM documents
            WHERE company_id = ? AND fiscal_year = 2025
            ORDER BY doc_type
            """,
            (company_id,),
        ),
    }


ROUTES = {
    "/api/summary": summary,
    "/api/chase": lambda: rows(QUERIES["chase"]),
    "/api/breaks": lambda: rows(QUERIES["breaks"]),
    "/api/margins": lambda: rows(QUERIES["margins"]),
    "/api/cycle": lambda: rows(QUERIES["cycle"]),
    "/api/segments": lambda: rows(
        """
        SELECT segment,
               COUNT(*) AS companies,
               SUM(CASE WHEN docs_overdue > 0 THEN 1 ELSE 0 END) AS overdue_files,
               ROUND(100.0 * SUM(docs_received) / SUM(docs_expected), 1) AS complete_pct
        FROM v_file_status
        GROUP BY segment
        ORDER BY complete_pct
        """
    ),
    "/api/sql": lambda: QUERIES,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: object, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            target = (STATIC / path.removeprefix("/static/")).resolve()
            if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
                self._json({"error": "not found"}, 404)
                return
            kind = "text/css; charset=utf-8" if target.suffix == ".css" else "text/javascript; charset=utf-8"
            self._send(200, target.read_bytes(), kind)
            return
        if path in ROUTES:
            self._json(ROUTES[path]())
            return
        if path.startswith("/api/company/"):
            try:
                company_id = int(path.rsplit("/", 1)[-1])
            except ValueError:
                self._json({"error": "bad id"}, 400)
                return
            payload = company(company_id)
            if payload is None:
                self._json({"error": "not found"}, 404)
                return
            self._json(payload)
            return
        self._json({"error": "not found"}, 404)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"SME Credit File  http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
