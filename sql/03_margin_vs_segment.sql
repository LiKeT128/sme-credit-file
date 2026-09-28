-- Net margin against the company's own segment in the same year.
-- A 35% margin in a segment that averages 7% is a question, not a result.

SELECT
  c.id AS company_id,
  c.name,
  c.segment,
  q.fiscal_year,
  q.revenue_eur,
  q.net_income_eur,
  ROUND(100.0 * q.net_margin, 1) AS net_margin_pct,
  ROUND(100.0 * seg.avg_net_margin, 1) AS segment_avg_pct
FROM v_statement_quality q
JOIN companies c ON c.id = q.company_id
JOIN v_segment_margin seg
  ON seg.segment = c.segment
 AND seg.fiscal_year = q.fiscal_year
WHERE q.fiscal_year = 2025
  AND ABS(q.net_margin - seg.avg_net_margin) >= 0.20
ORDER BY ABS(q.net_margin - seg.avg_net_margin) DESC;
