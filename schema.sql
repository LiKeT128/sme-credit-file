PRAGMA foreign_keys = ON;

-- Synthetic corporate-banking book. No real clients.
-- Question: which SME annual reviews are blocked, and which filed numbers cannot be trusted.

CREATE TABLE companies (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  ico TEXT NOT NULL UNIQUE,
  city TEXT NOT NULL,
  segment TEXT NOT NULL,
  employees INTEGER NOT NULL,
  relationship_manager TEXT NOT NULL,
  client_since TEXT NOT NULL
);

CREATE TABLE statements (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  fiscal_year INTEGER NOT NULL,
  revenue_eur INTEGER NOT NULL,
  ebit_eur INTEGER NOT NULL,
  net_income_eur INTEGER NOT NULL,
  total_assets_eur INTEGER NOT NULL,
  equity_eur INTEGER NOT NULL,
  liabilities_eur INTEGER NOT NULL,
  cash_eur INTEGER NOT NULL,
  receivables_eur INTEGER NOT NULL,
  received_on TEXT,
  UNIQUE (company_id, fiscal_year)
);

CREATE TABLE documents (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  fiscal_year INTEGER NOT NULL,
  doc_type TEXT NOT NULL,
  requested_on TEXT NOT NULL,
  due_on TEXT NOT NULL,
  received_on TEXT,
  UNIQUE (company_id, fiscal_year, doc_type)
);

CREATE INDEX idx_documents_company_year ON documents (company_id, fiscal_year);
CREATE INDEX idx_statements_company_year ON statements (company_id, fiscal_year);

-- A file is complete when all four 2025 documents have arrived
-- and a 2025 statement row exists.
CREATE VIEW v_file_status AS
SELECT
  c.id AS company_id,
  c.name,
  c.city,
  c.segment,
  c.employees,
  c.relationship_manager,
  COUNT(d.id) AS docs_expected,
  SUM(CASE WHEN d.received_on IS NOT NULL THEN 1 ELSE 0 END) AS docs_received,
  SUM(CASE WHEN d.received_on IS NULL AND d.due_on < date('now') THEN 1 ELSE 0 END) AS docs_overdue,
  MAX(CASE WHEN d.received_on IS NULL AND d.due_on < date('now') THEN d.due_on END) AS oldest_overdue_due,
  MAX(s.fiscal_year) AS latest_statement_year
FROM companies c
LEFT JOIN documents d
  ON d.company_id = c.id
 AND d.fiscal_year = 2025
LEFT JOIN statements s
  ON s.company_id = c.id
GROUP BY c.id;

-- Assets must equal equity + liabilities. A gap is a data-entry defect, not a business result.
CREATE VIEW v_statement_quality AS
SELECT
  s.company_id,
  s.fiscal_year,
  s.revenue_eur,
  s.ebit_eur,
  s.net_income_eur,
  s.total_assets_eur,
  s.equity_eur,
  s.liabilities_eur,
  s.cash_eur,
  s.receivables_eur,
  s.received_on,
  (s.total_assets_eur - s.equity_eur - s.liabilities_eur) AS imbalance_eur,
  ROUND(1.0 * s.net_income_eur / NULLIF(s.revenue_eur, 0), 4) AS net_margin
FROM statements s;

CREATE VIEW v_segment_margin AS
SELECT
  c.segment,
  q.fiscal_year,
  COUNT(*) AS filings,
  ROUND(AVG(q.net_margin), 4) AS avg_net_margin,
  ROUND(AVG(q.revenue_eur), 0) AS avg_revenue_eur
FROM v_statement_quality q
JOIN companies c ON c.id = q.company_id
GROUP BY c.segment, q.fiscal_year;

-- Priority: missing statement, then overdue documents, then a broken balance sheet.
CREATE VIEW v_chase_list AS
SELECT
  f.company_id,
  f.name,
  f.city,
  f.segment,
  f.employees,
  f.relationship_manager,
  f.docs_received,
  f.docs_expected,
  f.docs_overdue,
  f.oldest_overdue_due,
  f.latest_statement_year,
  CASE WHEN f.latest_statement_year = 2025 THEN 0 ELSE 1 END AS statement_missing,
  COALESCE(q.imbalance_eur, 0) AS imbalance_eur,
  COALESCE(q.net_margin, NULL) AS net_margin,
  COALESCE(seg.avg_net_margin, NULL) AS segment_avg_margin,
  (
    CASE WHEN f.latest_statement_year = 2025 THEN 0 ELSE 50 END
    + f.docs_overdue * 12
    + CASE WHEN q.imbalance_eur IS NOT NULL AND ABS(q.imbalance_eur) >= 1000 THEN 20 ELSE 0 END
    + CASE
        WHEN q.net_margin IS NOT NULL AND seg.avg_net_margin IS NOT NULL
         AND ABS(q.net_margin - seg.avg_net_margin) >= 0.20 THEN 8
        ELSE 0
      END
  ) AS priority
FROM v_file_status f
LEFT JOIN v_statement_quality q
  ON q.company_id = f.company_id
 AND q.fiscal_year = 2025
LEFT JOIN v_segment_margin seg
  ON seg.segment = f.segment
 AND seg.fiscal_year = 2025
WHERE f.docs_overdue > 0
   OR f.latest_statement_year < 2025
   OR (q.imbalance_eur IS NOT NULL AND ABS(q.imbalance_eur) >= 1000)
   OR (
        q.net_margin IS NOT NULL
        AND seg.avg_net_margin IS NOT NULL
        AND ABS(q.net_margin - seg.avg_net_margin) >= 0.20
      );
