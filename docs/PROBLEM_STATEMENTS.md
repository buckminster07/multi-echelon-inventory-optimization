# Business questions and acceptance evidence

## 1. Convert records into planning inputs

**Problem:** demand and transport uncertainty cannot be planned from averages alone.

**Work:** ingest four related tables; reject duplicates, missing daily series,
invalid quantities and unsupported network structures; calculate SQL demand
moments and empirical transport lead-time distributions using training data only.

**Evidence:** `demand_profile.csv`, `lead_time_profile.csv`, `inventory.sqlite`.
Tests compare SQL moments with independent Pandas calculations and verify that
changing held-out data cannot alter fitted training profiles.

## 2. Allocate inventory across locations

**Problem:** independently sized stores and warehouses ignore upstream availability.

**Work:** derive local base-stock targets; evaluate 36 paired warehouse/store
multipliers per SKU using the full network; choose the minimum normal-demand cost.

**Evidence:** `search_results.csv`, `targets.csv`. A target's optimality is limited
to this grid, not all integer stock vectors.

## 3. Make the cost/service trade-off explicit

**Problem:** a low-cost solution may leave customers waiting.

**Work:** choose the lowest average training-scenario cost among candidates whose
worst store/scenario immediate fill reaches 95%. If none qualifies, select the
highest worst-fill candidate and report infeasibility explicitly.

**Evidence:** training feasibility and chosen candidate IDs in `manifest.json`;
worst store–SKU fill in `summary.csv`; granular evidence in `store_trials.csv`.

## 4. Stress the policy before relying on it

**Problem:** demand spikes and supplier delays may invalidate normal-day policies.

**Work:** run normal demand, a temporary 1.6× spike, +4-day supplier transport delays,
and their combination. Sample individual shipment lead times and track queues,
backorders and inventory balances. Combined stress is excluded from policy search.

**Evidence:** `trials.csv`, `daily_trace.csv.gz`, `policy_comparison.png`.
The compressed trace contains the first evaluation seed for every SKU, policy,
scenario and window, not all 12 seeds; aggregate trial CSVs cover all seeds.

## 5. Demonstrate generalization and uncertainty

**Problem:** an attractive training score does not establish future performance.

**Work:** freeze policies after training; evaluate chronological validation and
test demand without retuning; use common lead-time draws across policies and
report paired Student-t intervals on cost differences.

**Evidence:** `aggregate_trials.csv`, `savings_intervals.png`, `RESULTS.md`.
These intervals describe transport randomness conditional on observed demand.
They are not confidence bounds for deployed business savings.
