# Data contract and provenance

All committed demo inputs are synthetic and generated from seed 42. They contain
900 days × 4 stores × 3 SKUs = 10,800 daily demand records. The generator includes
negative-binomial variability and a weekend demand effect. It makes no claim to
represent a specific company. Receipt records are synthetic transport observations.

## CSV schemas

| File | Required columns | Meaning |
|---|---|---|
| nodes.csv | node_id, name, kind, parent_id, holding_cost | kind is warehouse/store; warehouses have blank parent, stores reference a warehouse |
| skus.csv | sku, label, cost_multiplier, shortage_penalty | Holding rates are multiplied by SKU cost multiplier; shortage penalty is per unit/day |
| demand.csv | date, node_id, sku, quantity | YYYY-MM-DD, daily requested units at stores; include zero-demand days |
| receipts.csv | receipt_id, node_id, sku, dispatch_date, receipt_date, quantity | Destination node and SKU; dispatch-to-receipt days must be positive |

Daily observations must cover the same dates for every store/SKU. Quantities are
nonnegative integers; receipt quantities are positive. IDs must match master
tables. Date keys must use ISO YYYY-MM-DD strings. Every node/SKU needs receipt
observations available within the training period. Cost units are arbitrary and
must be consistent; the example does not label them INR or USD.

Receipt quantities are validated but not used to calibrate order-size policies.
Partial historical receipts must be preprocessed into a consistent transport-time
sample. The simulation allows partial warehouse dispatches.

For custom data, adjust train_days and validation_days so at least ten test days
remain. Use ≥30 training days and ≥10 validation days. The demo uses 540/180/180.
The importer supports additional stores, warehouses and SKUs within the two-echelon
schema; capacity coupling between SKUs is not implemented or scalability-tested.

## Output artifacts

| Artifact | Purpose |
|---|---|
| inventory.sqlite | Derived relational database; generated locally, not committed |
| demand_profile.csv / lead_time_profile.csv | Training-only statistics |
| search_results.csv | Every candidate and its cost/service/feasibility scores |
| targets.csv | Selected stock levels by node, SKU and policy |
| trials.csv / store_trials.csv | All SKU and store-level evaluation metrics |
| aggregate_trials.csv | Network-level seed results used for paired inference |
| daily_trace.csv | First-seed daily trace for all configurations |
| summary.csv / RESULTS.md | Readable and machine-readable comparison |
| report.html / PNGs | Portable visual report |
| manifest.json | Configuration, date boundaries, versions, hashes and selection flags |

The committed daily trace is gzip-compressed. Read with
`pd.read_csv('examples/full/daily_trace.csv.gz')`; full runs produce uncompressed CSV.
