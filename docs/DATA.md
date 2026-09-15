# Data contract and provenance

The shipped demo generates **synthetic records**, not confidential company data.
No real customer, vendor or employee identifiers are included. A fixed seed creates
540 daily observations for each of two stores and a replenishment history for
one warehouse and two stores. There is one SKU (`SKU-001`).

## Required CSVs

`demand.csv`

| Field | Type | Meaning |
|---|---|---|
| date | YYYY-MM-DD | Demand date, daily granularity |
| store_id | integer | 1 or 2 |
| sku | string | SKU-001 |
| quantity | integer ≥ 0 | Requested units, including unmet demand |

`replenishment.csv`

| Field | Type | Meaning |
|---|---|---|
| order_id | unique integer | Purchase/replenishment order |
| node_id | integer | Receiving node: warehouse 0, stores 1/2 |
| order_date | YYYY-MM-DD | Order placement |
| receipt_date | YYYY-MM-DD | Complete receipt |
| quantity | positive integer | Received units |

Every store must have every date in the same training window, including zeros.
At least 30 days are required. Orders and receipts must lie inside that window.
Partial receipts are not supported. Historical receipts estimate lead-time
statistics; their quantities do not calibrate the simulated ordering policy.

For compatible data, run:

```bash
inventory-lab --config configs/demo.json --data-dir /path/to/csvs --output outputs/custom
```

Do not equate sales with demand if stockouts censor observed sales. Recover unmet
requests or document the resulting underestimation. For real data, also exclude
receipts not yet observable at the training cutoff to avoid future information.

## SQL analysis

- `schema.sql` defines keys and constraints.
- `demand_profile.sql` computes demand means and sample variances.
- `lead_times.sql` derives elapsed calendar days from order/receipt dates.
- Python aggregates lead-time quantiles and uses empirical demand samples.

The demand generator uses independent negative-binomial draws by store. It does
not simulate seasonality or cross-store correlation. The evaluation bootstrap
inherits these assumptions. Fresh seeds are independent simulated replications,
not a claim of chronological validation on real future sales.
