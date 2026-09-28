-- How long does a complete document actually take, and which types stall?
-- Received rows only. Overdue rows have no cycle time yet; they sit in the chase list.

SELECT
  doc_type,
  COUNT(*) AS received_docs,
  ROUND(AVG(julianday(received_on) - julianday(requested_on)), 1) AS avg_days_to_receive,
  SUM(CASE WHEN received_on > due_on THEN 1 ELSE 0 END) AS arrived_late
FROM documents
WHERE fiscal_year = 2025
  AND received_on IS NOT NULL
GROUP BY doc_type
ORDER BY avg_days_to_receive DESC;
