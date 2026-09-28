-- Accounting identity: assets = equity + liabilities.
-- Anything else is a capture error. Do not analyse a broken filing as if it were performance.

SELECT
  c.id AS company_id,
  c.name,
  c.segment,
  q.fiscal_year,
  q.total_assets_eur,
  q.equity_eur,
  q.liabilities_eur,
  q.imbalance_eur
FROM v_statement_quality q
JOIN companies c ON c.id = q.company_id
WHERE ABS(q.imbalance_eur) >= 1000
ORDER BY ABS(q.imbalance_eur) DESC;
