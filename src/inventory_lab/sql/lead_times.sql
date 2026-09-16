SELECT node_id,sku,CAST(julianday(receipt_date)-julianday(dispatch_date) AS INTEGER) AS lead_days
FROM receipts WHERE receipt_date < :cutoff ORDER BY node_id,sku,receipt_id;
