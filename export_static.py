"""Freeze the dashboard into plain files for GitHub Pages.

Every API route is written to site/api/<route> as JSON, next to a copy of
static/. The page fetches relative URLs, so it runs the same with or without
app.py. The snapshot is dated by the build, like the live app.
"""

from __future__ import annotations

import json
import shutil

from app import ROOT, ROUTES, STATIC, company, rows

SITE = ROOT / "site"


def write(route: str, payload: object) -> None:
    target = SITE / route.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(STATIC, SITE / "static")
    shutil.copy(STATIC / "index.html", SITE / "index.html")
    for route, handler in ROUTES.items():
        write(route, handler())
    ids = [row["id"] for row in rows("SELECT id FROM companies ORDER BY id")]
    for company_id in ids:
        write(f"/api/company/{company_id}", company(company_id))
    print(f"routes={len(ROUTES)} companies={len(ids)} -> {SITE}")


if __name__ == "__main__":
    main()
