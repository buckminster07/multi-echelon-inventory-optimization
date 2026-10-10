# Methods and operational contracts

## Data preparation and SQL

`retail_planner/data.py` downloads the original UCI ZIP, records its SHA-256, and loads both workbook sheets. It never loads Customer ID. Cancellations and negative quantities are excluded from gross outbound sales and reported in the audit. Nonpositive prices/quantities, nonproduct codes, invalid dates and lines exceeding 10,000 units are removed. Exact repeated lines are retained: there is no invoice-line identifier to establish that they are erroneous duplicates. These rules are fixed before model evaluation.

Only the initial training period selects markets, products, prices and assortment. Unobserved dates in an active pair are zero **observed sales**, not confirmed zero latent demand. The full daily grid is loaded into SQLite, validated with foreign keys and nonnegative checks, then extracted back through a SQL join for modeling. `sku`, `location`, `assortment` and `daily_sales` are separate entities. `experiment`, `proposal` and `decision` use run-specific identifiers so simulations and approval records do not mix.

ABC ranks cumulative training sales value; X/Y/Z uses coefficient-of-variation thresholds 0.5 and 1.0 on aggregate product daily sales. ADI is training days divided by nonzero sales days. ABC describes value exposure, not a theorem about service priority. SKU selection favors commercially important products; results do not cover the full catalog.

## Chronological experiment

| Stage | Data available / purpose |
|---|---|
| Initial fit and cohort | Through 30 April 2011 |
| Forecast method selection | May 2011; 7-day horizons at 3-day origin spacing |
| Error calibration | June–July 2011; 14-day forecasts at 3-day origin spacing |
| Inventory tuning | August 2011; normal, spike and supplier-delay scenarios |
| Validation diagnostic | September 2011; frozen choices and buffers |
| Final test | October–November 2011; four scenarios including previously untuned combined disruption |

The learned booster remains frozen after initial fitting. Baselines and lag features use observations preceding each forecast origin. Forecasts publish weekly; decisions use the latest published path. Overlapping forecast horizons are dependent, so fold rows are not independent statistical replications. The simulation assumes customer request quantities become observable by the end of the day; historical positive sales serve as that request proxy.

## Forecasting

Four methods compete per active product–market pair on May absolute error:

1. Seasonal naive: repeat the prior seven observations.
2. Moving average: repeat the prior 28-day mean.
3. TSB: update demand occurrence probability every day and positive-demand size on positive days, smoothing each at 0.1; multiply probability by size.
4. Global histogram gradient boosting with Poisson loss: one model across pairs, using product/market categories, calendar fields, lags 1/7/14/28, shifted rolling means, standard deviation and zero frequency. Sample training rows with a fixed seed to cap memory. Forecast recursively, appending predictions rather than future actuals.

No future prices, weather or promotions are used. Product IDs are categorical rather than interpreted as a numeric ranking. The configured cohort stays below the booster's 255-category limit. ML is a challenger; it is not declared the winner in advance. An explicit future-mutation test verifies that a forecast cannot change when later actuals are modified.

For each origin o and horizon h, cumulative error E(o,h)=sum(actual−forecast) over h future days. June–July errors calibrate h=1,3,7,14. A 90% empirical interval adds the 5th and 95th error quantiles to the cumulative point forecast, with nonnegative bounds. The nonnegative upper error quantile supplies the stock buffer. Aggregate simultaneous hub errors before estimating the DC buffer, preserving observed cross-market dependence. Coverage/width are evaluated later, per horizon. Short and dependent calibration samples do not provide distribution-free coverage guarantees. Interpolation to four/nine/ten protection days uses square-root horizon scaling of the 7/14-day calibrated buffer; this is an explicit approximation under dependence.

## Policy mathematics

Let IP be local inventory position, μ the initial mean daily sales, K the request fee, h the per-unit daily holding cost, B_L the calibrated buffer for a protection interval, and κ/a the optimized hub/DC multipliers.

| Policy | Hub decision |
|---|---|
| Fixed cover baseline | Every 7 days, q=max(0,10μ−IP) |
| Daily (r,Q) approximation | r=4μ+B4; when IP≤r, q=sqrt(2Kμ/h), then apply order constraints |
| Periodic order-up-to | Every 7 days, q=max(0,10μ+B10−IP) |
| Forecast optimized | Daily, q=max(0,sum(next four published forecasts)×recent-demand signal+κB4−IP) |

The recent-demand signal is the ratio of already observed last-seven-day requests to corresponding published expectation, stabilized with seven units and capped at 0.7–1.6. It responds to demand changes after they occur. Four days protect up to three-day transport plus a daily review; ten days protect weekly review plus three-day transport. Every policy uses the same exogenous lead-time realizations.

Store IP=on-hand+shipped inbound+queued internal requests. DC IP=on-hand+supplier inbound−owed hub requests. The DC reviews daily to a nine-day aggregate forecast target plus buffer. The adaptive policy jointly scales hub and DC targets; the other policies use unscaled DC buffers. This is a whole-network comparison. It is **local-stock policy optimization on a constrained two-echelon network**, not an exact Clark–Scarf echelon-stock optimum.

## Resources and allocation

All operating parameters are assumptions. Supplier lead times are discrete uniform 4–8 days; internal transport is 2–3 days. Stress adds five supplier days to orders placed in the middle fourteen-day window. Demand stress doubles requests for a seeded 30% of products in that window. Supplier arrays are keyed by day/product; transport arrays by day/market/product, irrespective of order count.

Per-product hub capacity is 35 days of initial mean sales, with a minimum MOQ for active products. Shared hub capacity is 80% of the sum of those nominal day-cover quantities (with a minimum MOQ). DC uses 45 days and the same 80% shared adjustment. Initial inventories use eight days at hubs and twelve at the DC, identical for all policies. No warm-up is removed: the experiment includes startup transients.

Order rounding: positive request → ceil to six-unit pack with twelve-unit MOQ → cap by item space, shared space and cash budget. Each location gets a rolling seven-day line-purchase budget. Its daily allowance is four days of initial expected acquisition spend, with a minimum allowing one maximum-cost MOQ; seven-day capacity is seven times that allowance, minus spending over the prior six days. Weekly and daily policies can access the same rolling allowance, avoiding an artificial penalty for infrequent ordering. A greedy shortage-exposure priority ranks products; this is a feasible heuristic, not an integer-programming optimal allocation. Internal partial shipments need not be complete packs. The DC proportionally allocates each scarce SKU across outstanding requests, then rotates the remainder priority.

## Simulation and cost accounting

Daily events: receive scheduled shipments → serve customer demand → record lost units → review/request hub orders → allocate and dispatch DC stock → place supplier orders → charge end-of-day costs. Positive lead times prohibit same-day fulfillment from newly placed orders.

Daily identities:

- Initial internal physical stock + external receipts − customer fulfilled units = DC + hubs + internal transit.
- Hub incoming scheduled quantities = shipped hub pipeline; external scheduled quantities = supplier pipeline.
- Customer requested units = served units + permanently lost units.
- Committed stock respects item and shared capacity; every placed request respects pack, MOQ and purchasing budget.

Selling prices are training medians from the source. Acquisition costs are assumed at 45% of selling price. Annual holding is 25% of acquisition value, divided by 365; DC holding uses 70% of that rate. Lost-margin penalty is selling price minus assumed acquisition cost. Supplier and transfer request fees are GBP 8 and GBP 2 per nonzero SKU line. Internal freight is 4% of selling price per unit dispatched. These are illustrative model coefficients, not measured company expenses.

Relevant cost = holding + ordering + transport + lost-margin penalty. Procurement cash is counted at external receipt and reported separately. Internal transfers are not purchases again. Ending internal inventory/transit value and outstanding supplier units are reported; no procurement capital or terminal salvage enters the relevant-cost objective. Model sensitivity before interpreting savings.

## Optimization, statistics and metrics

Eight κ∈{0.5,1,1.5,2} × a∈{0.8,1.2} combinations are tested using three seeds and three tuning scenarios: 72 simulations in the full profile. Select lowest cost among candidates meeting mean aggregate fill≥95% and A-item fill≥97% in each tuning scenario. If infeasible, minimize summed service gaps then cost. This is best-of-grid selection, not global optimality or guaranteed future service.

Final evaluation uses 20 paired replications × four scenarios × four policies = 320 network simulations, plus validation and sensitivity. Mean confidence intervals and paired cost-difference intervals use Student t across replication seeds. They quantify supplier randomness and randomized shocked-product selection conditional on the observed demand history; they do not imply 20 independently observed histories. Combined stress is absent from tuning.

Forecast MAE=sum|f−y|/n; RMSE=sqrt(sum(f−y)²/n); bias=sum(f−y)/n; WAPE=sum|f−y|/sum y. Positive bias is overforecast. Pool numerators/denominators across active pairs; do not average pair WAPEs. Zero-demand denominators are undefined. Fill=sum served/sum requested, A-item fill restricts to training A-products, and worst material-pair fill restricts to pairs requesting at least thirty units in the evaluation window. That worst-pair threshold is descriptive, not part of selection.

Cycle service counts shortage-free complete receipt-to-receipt cycles, excluding initial/final partial cycles. Split deliveries and intermittent demand complicate its interpretation. Average inventory averages end-of-day physical units, excluding transit. Runtime is machine-specific. Feasibility covers modeled quantity/capacity/budget/accounting constraints; service feasibility is reported separately.

## Planner contract

Each proposal belongs to a run, day, location and SKU. Approval uses a transaction and unique per-proposal decision constraint. Modified quantities may only reduce the already budgeted recommendation; increases require a new batch plan. This preserves shared-budget/capacity feasibility. Actor and reason are required; repeated or stale selections are rejected. A decision replay caps those selected orders in a fresh same-seed simulation; other orders remain automated. Decisions remain in SQLite and the export ZIP. This is functional decision support, not ERP transmission or authenticated multi-user production software.
