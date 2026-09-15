SELECT node_id, order_id,
       CAST(julianday(receipt_date) - julianday(order_date) AS INTEGER) AS lead_time_days
FROM replenishment
ORDER BY node_id, lead_time_days, order_id;
