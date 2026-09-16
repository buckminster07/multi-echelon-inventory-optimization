-- All fitted parameters use TRAINING data only, including receipt observability.
SELECT d.node_id,n.name,d.sku,s.label,COUNT(*) AS days,
 AVG(d.quantity) AS mean_demand,
 MAX(0.0,(SUM(1.0*d.quantity*d.quantity)-SUM(1.0*d.quantity)*SUM(d.quantity)/COUNT(*))/(COUNT(*)-1)) AS variance_demand
FROM demand d JOIN nodes n ON n.node_id=d.node_id JOIN skus s ON s.sku=d.sku
WHERE d.date < :cutoff
GROUP BY d.node_id,d.sku ORDER BY d.node_id,d.sku;
