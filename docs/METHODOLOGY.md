# Modeling specification

## Network and decision

Each SKU is simulated independently through external suppliers → warehouses →
stores → customers. A store has exactly one warehouse parent. Suppliers have
unlimited inventory. There are no shared SKU capacity constraints.
The decision is a local integer base-stock target S at each node.

## State and daily event order

1. Receive due shipments. Decrease the corresponding open-order quantity.
2. At stores, serve old customer backorders before new demand.
3. Place store orders to restore inventory position toward S.
4. Warehouses dispatch FIFO requests, allowing partial fulfillment. Same-day
   store ordering priority rotates daily; older requests remain first.
5. Warehouses place supplier orders to restore their own inventory position.
6. Charge end-of-day holding and store-backorder costs and reconcile balances.

Store inventory position = on-hand + outstanding replenishment − customer backlog.
Warehouse inventory position = on-hand + open supplier orders − pending store requests.
Stock already shipped to a store belongs to transit, not warehouse on-hand.

Transport lead times are positive integers sampled from training receipt records.
Internal shipments are sampled on dispatch, so warehouse waiting time is modeled
separately. For comparable policies, each node draws one lead-time value per day
from a deterministic seed stream whether or not it orders. Same-node same-day
shipment fragments share that value. SKUs reuse node seed streams; intervals
therefore reflect that common randomness rather than independent SKU shocks.
Order crossing is allowed: a later shipment can arrive before an earlier one.

## Physical invariants

Every day, with assertions enabled:

- Initial inventory + supplier receipts = on-hand + internal transit + cumulative customer shipments.
- Cumulative customer requests = customer shipments + outstanding customer backlog.
- Store open orders = undispatched requests + internal transit.
- Physical on-hand stock is nonnegative.

These checks are useful accounting validation, not proof of every behavioral assumption.

## Independent baseline

For node i, use a normal approximation with demand mean μ, variance v and transport
lead-time moments E[L], Var[L]:

`S_i = ceil( μ_i (E[L_i] + 1) + z_i sqrt(v_i (E[L_i] + 1) + μ_i² Var[L_i]) )`

`z_i = Φ⁻¹(p_i / (p_i + h_i))`

For warehouses, aggregate downstream demand means and variances (independent
store approximation). The store shortage penalty is a planning proxy upstream;
realized backorder cost is charged only at stores. This is a transparent heuristic,
not an exact optimum for the simulation's event order.

## Joint policy search

Multipliers `[0.6, 1, 1.4, 1.8, 2.4, 3.2]` scale the baseline. All warehouse targets
for a SKU share one multiplier and all store targets share another. Their absolute
targets still differ. Enumerate 36 combinations per SKU.

- **Normal optimized:** minimum normal-scenario average cost.
- **Service aware:** minimum equally weighted cost across three training scenarios,
  subject to every store/scenario pooled fill being at least 95%.
- **Infeasible fallback:** maximum worst fill, then minimum mean cost, with a flag.

Search uses two seeded bootstrap paths of 100 measured days, after 45 warm-up days.
Whole store-demand vectors are sampled together within each SKU. This preserves
same-day cross-store dependence but not serial dependence or weekly order.
Two replications and the finite grid limit the precision of training estimates.

## Temporal isolation

540 training days estimate parameters and select all targets. The next 180 days
are diagnostic validation; the final 180 days are test. Neither selects policies.
Receipt records enter estimation only if received before the training cutoff.
Warm-up uses the immediately preceding 45 demand days for each evaluation window.
Validation and test are separately initialized simulations, not a continuous
inventory rollout. Initial on-hand equals each policy target; external stock is
not charged as a purchase cost.

Evaluation holds the observed demand path fixed and varies transport randomness
across 12 seeds. The normal test is an out-of-time synthetic backtest. Stress
scenarios transform that demand or supplier transport time.

## Scenarios

| Scenario | Demand | Supplier transport |
|---|---|---|
| Normal | Observed daily path | Empirical training samples |
| Demand spike | 1.6× for one-quarter of the measured horizon, starting one-third in | Base |
| Supplier delay | Base | Sampled lead + 4 days, including warm-up |
| Combined stress | Spike | Delayed |

The combined scenario is excluded from training search. Supplier delay is a
persistent slower regime; transport times still vary within it.

## Metrics and inference

Cost/day sums end-of-day holding and outstanding-store-backorder penalties,
divided by measured days. Backorder penalties are per unit per day.
Immediate fill is new demand served immediately / new demand; clearing an old
backorder does not count as immediate service. Shortage units sum newly unfilled
demand. Backlog unit-days repeatedly count outstanding backlog over time.

Network costs sum across SKUs. Aggregate fill is demand-weighted. Worst store–SKU
fill pools seeds for each store/SKU and then takes the minimum; it is not the
worst single realization. The service threshold is a training constraint only.

For each policy, pair per-seed costs with the independent baseline. Report a
Student-t 95% interval on the mean absolute cost saving (11 degrees of freedom).
Percent savings use the ratio of mean cost differences to mean baseline cost.
Intervals exclude demand-sample uncertainty, parameter uncertainty and model error.

## Deliberate exclusions

No lost sales, lead-time censoring model, capacity, MOQs, purchase/transport charges,
product expiry, correlated supplier failures, forecasting ML or live ERP integration.
Demand records must represent requests, not censored sales. Service-aware costs
can be higher. Held-out service failures are retained in all reports.
