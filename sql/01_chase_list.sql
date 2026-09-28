-- Who blocks the October annual review?
-- A file is blocked when a 2025 document is past due, or the statement never arrived.
-- Priority is a working queue, not a credit score.

SELECT
  company_id,
  name,
  segment,
  relationship_manager,
  docs_received || '/' || docs_expected AS file_progress,
  docs_overdue,
  CASE WHEN statement_missing = 1 THEN 'missing' ELSE 'filed' END AS statement_2025,
  imbalance_eur,
  priority
FROM v_chase_list
ORDER BY priority DESC, name;
