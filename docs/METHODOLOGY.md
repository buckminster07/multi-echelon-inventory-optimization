# Modeling and validation decisions

## Decision and scope

Choose local base-stock targets S₀, S₁ and S₂ for a single-SKU network: warehouse
0 supplies stores 1 and 2. Orders restore inventory position toward each target.
Stockpyl 1.0.2 executes the inventory flows and replenishment logic.

The objective is mean daily holding cost plus daily penalties on outstanding
store backorders. Costs are arbitrary units, not rupees. There is no purchasing
cost, fixed order charge, capacity limit, expiry, MOQ or transportation charge.
External supply is unlimited. Initial inventory equals the policy target and
60 warm-up days are excluded from both costs and service calculations.

## Baseline: independent local targets

Each node's target is calculated with a normal-approximation rule:

`S_i = ceil(mu_i * (L_i + 1) + z_i * sqrt(var_i * (L_i + 1)))`

`z_i = NormalInverseCDF(p_i / (p_i + h_i))`

`L+1` is a conservative daily-review protection-period approximation. It is a
transparent heuristic rather than a theorem matching every Stockpyl timing
convention. Warehouse demand mean and variance are sums across independent
stores. Its planning shortage penalty is the average downstream penalty;
realized warehouse backlog has no additional penalty, avoiding double counting.
This baseline ignores how upstream availability affects downstream service.

## Coordinated targets

Stockpyl's `meio_by_enumeration` evaluates the Cartesian product of three target
multipliers (0.6, 1.0, 1.4) per node: 27 candidate combinations. The baseline is
included. A custom objective evaluates each combination on three identical
training demand paths, with 180 measured days after warm-up per path.

This is the best observed policy on a finite grid under normal conditions.
It is **not** a globally optimal solution or a robust optimization formulation.
`manifest.json` flags grid-boundary choices; widen the grid in a separate
experiment if a wider search is required. Do not tune using the evaluation seeds.

## Uncertainty and scenarios

Daily demands are drawn with replacement from historical store-specific samples.
All policies receive identical paths for each scenario/seed (common random
numbers). Optimization uses seeds 101–103; evaluation uses 1001–1020.

| Scenario | Demand | Warehouse inbound transport time |
|---|---|---|
| Normal | Empirical bootstrap | Ceiling of historical mean |
| Demand spike | 1.6× during first quarter of measured horizon | Base |
| Supplier delay | Base | Base + 3 days throughout, including warm-up |
| Combined stress | Spike | Base + 3 days throughout |

The spike represents a temporary demand surge. Supplier delay represents a
persistent slower supplier regime, not a randomly timed outage. Historical
lead-time distributions are summarized, but the engine uses fixed transport
times within a scenario; it does not sample a lead time for every order.

## Metrics

- **Cost/day:** (holding costs + backorder penalties) / measured days.
- **Immediate fill rate:** current demand served immediately from stock / current
  demand; excludes later clearance of previously backlogged demand.
- **Shortage units:** current demand not served immediately, summed across stores.
- **Backlog unit-days:** daily outstanding store backlog, summed over days.
  This is a different measure from shortage units.
- **Cost saving:** 100 × (mean baseline cost − mean coordinated cost) / mean baseline cost.
- **95% interval:** paired Student-t interval on per-seed cost differences, with
  19 degrees of freedom in the default run. The interval is for absolute savings
  per day, not for the reported percentage.

Store shortage penalties are charged per unit per day outstanding. A weighted
cost objective can favor lower service; always inspect fill rates alongside cost.
No minimum service constraint is enforced.

## Validation boundaries

Unit tests check SQL moments, input rejection, deterministic inventory behavior,
shortage accounting, scenario windows, seed separation and paired statistics.
An integration test runs data generation through optimization and reporting.
Stockpyl consistency checks are configured to raise exceptions.

The bootstrap evaluates robustness within the fitted synthetic demand model.
Its confidence intervals exclude distribution-estimation uncertainty and
structural model error. Deployment would require real-data backtesting,
calibrated costs, service constraints and operational review.

## References

- [Stockpyl source and MIT license](https://github.com/LarrySnyder/stockpyl)
- [Multi-echelon optimization tutorial](https://stockpyl.readthedocs.io/en/latest/tutorial/tutorial_meio.html)
- [Simulation timing and outputs](https://stockpyl.readthedocs.io/en/latest/tutorial/tutorial_sim.html)

Stockpyl supplies the optimization and simulation algorithms. This repository
adds SQL preparation, a defined baseline, experiment orchestration, paired
validation, reporting and reproducible configuration.
