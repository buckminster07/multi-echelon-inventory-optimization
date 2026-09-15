-- Sample variance from SQL moments; n-1 denominator, not population variance.
SELECT store_id, COUNT(*) AS observations,
       AVG(quantity) AS mean_demand,
       MAX(0.0, (SUM(1.0 * quantity * quantity)
         - SUM(1.0 * quantity) * SUM(quantity) / COUNT(*))
         / (COUNT(*) - 1)) AS variance_demand
FROM demand
GROUP BY store_id
ORDER BY store_id;
