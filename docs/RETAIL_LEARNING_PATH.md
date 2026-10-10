# Learn the project by explaining each decision

The learning goal is to become able to defend the full chain: business question → data → model → inventory decision → experiment → planner action. Run the notebook, inspect its output, and explain one module aloud before moving on. The professional pipeline and the explanations use the same implementation.

| Stage | What to learn | What to explain or calculate |
|---|---|---|
| Business brief | Decision scope, stakeholders, service versus capital | Why can finance and sales prefer different inventory targets? |
| Acquisition/provenance | Source licenses, checksums, reproducibility | Why does a checksum identify data but not prove that it is correct? |
| Cleaning | Cancellations, returns, nonproducts, extreme bulk orders | Why is a return not negative future customer demand? |
| SQL | Primary/foreign keys, assortment, daily panels and joins | How can a nonunique join double sales? |
| Segmentation | ABC, CV/XYZ, ADI, intermittent demand | Why might a high-value slow mover need a different policy from a fast cheap item? |
| Forecasting | Baselines, global boosting, recursive horizons | Why must next week's lag features use predictions rather than actual next-week sales? |
| Calibration | Residuals, quantiles, lead-time demand | Why is daily uncertainty insufficient for a ten-day protection interval? |
| Policies | IP, (r,Q), periodic order-up-to, pack/MOQ | Why do both queued requests and shipped inbound belong in hub position? |
| Network simulation | Shared resources, allocation, physical balance | How does a DC shortage delay all dependent hubs? |
| Optimization | Grid search, objectives, constraints, feasibility | What do you report when every candidate misses its service target? |
| Evaluation | Chronological testing, common random numbers, paired intervals | Which uncertainty is and is not captured by twenty seeds? |
| Planner/export | Transactions, audit, idempotence, decision replay | Why must an increased order quantity reserve budget across the whole batch? |

## A small worked decision

A product sells ten units/day. A hub reviews weekly and transport takes up to three days, so the protection interval is ten days. Expected demand is 100. If the calibrated buffer is 25, target S=125. On-hand is 35, shipped inbound is 24 and queued requests are 18: IP=77. The raw order is 48. With six-unit packs and MOQ twelve, 48 is valid. If only 36 units fit within shared cash/space, request 36 and expose the remaining service risk to the planner.

The forecast describes expected requests; the buffer protects uncertainty; inventory position avoids duplicate commitments; resource constraints turn an unconstrained target into a feasible order. These are separate steps and should be explained separately.

## Forecasting exercise

Take one selected product-market pair. Display its daily series and zero fraction. Calculate the seven-day seasonal-naive forecast by hand. Compare it with the 28-day mean and TSB. Then inspect the global booster's held-out error. A more complex model earns use only if it improves the selected metric or inventory outcome. Explain the tradeoff if it improves MAE but underpredicts a few large wholesale orders.

TSB example: occurrence probability p=.2 and positive size z=10 imply expected daily quantity pz=2. After a zero day with smoothing α=.1, p becomes .18 while z stays ten, producing 1.8. After a positive day of twenty units, p=.28 and z=11 from the original state, producing 3.08. It separates occurrence from size rather than averaging zeros and positives indiscriminately.

## Uncertainty exercise

Suppose three cumulative errors over a review-plus-lead interval are −10, 5 and 30. The empirical upper quantile is large, but three observations provide little confidence. Explain why a buffer calibrated from many overlapping windows still does not have the same evidence as many independent seasons. Inspect actual interval coverage at 1, 3, 7 and 14 days. If coverage fails, consider more history, segment pooling, direct horizon models or recalibration; do not simply rename the interval “95% reliable.”

## Simulation exercise

Begin with twenty units at the DC and five at a hub. Ship eight units internally. Physical network stock is still twenty-five; only its location changes. Receive ten externally: stock becomes thirty-five. Fulfill seven customer units: stock becomes twenty-eight. A pending request for twelve changes commitments, not physical stock. Verify this in `daily_trace.csv` and `shipments.csv`.

Now reject a recorded planner order and run decision replay. Observe how later inventory, fill and cost change. The replay recomputes the future plan; an approval record alone would not show the consequence.

## Business reasoning exercise

Compare adaptive with periodic under normal and combined stress. Read the paired difference, not just two independent error bars. A negative cost difference favors adaptive. Ask whether the difference is large enough to matter, whether fill meets the service commitment, and whether terminal inventory capital is acceptable. Then double the budget and change holding rates through the sensitivity output. Distinguish a policy benefit from an assumption benefit.

## Interview explanation: roughly sixty seconds

“I built an inventory decision-support pipeline for an online retailer using UCI Online Retail II, which contains about a million real transaction records. I cleaned cancellations and nonproduct lines, selected products and markets using only training data, and integrated the daily sales panel through SQLite. I compared seasonal, moving-average and intermittent-demand forecasts with a global Poisson boosting model using chronological backtests. Cumulative forecast errors became inventory buffers. I then simulated a proposed central warehouse and market-hub network with lead times, shared capacity, purchasing budgets, MOQ and packs. Four policies were compared on the same scenarios, and joint stock-target settings were tuned before the final test period. The planner records approvals and modifications and can replay their effects. The key contribution is connecting forecasts to feasible decisions and measurable cost–service tradeoffs, while distinguishing real sales from assumed operational inputs.”

## Questions to rehearse

- Why did you select this dataset rather than generate all demand?
- What is missing from the dataset, and how does it limit your conclusions?
- How did you avoid choosing products using future sales?
- Why retain repeated invoice lines? What additional key would resolve duplication?
- What changes if sales were censored by stockouts?
- Why compare against naive models even with a global model available?
- How does your multi-step forecast prevent leakage?
- How do correlated markets affect DC uncertainty?
- Why does minimum order quantity sometimes make zero the only feasible order?
- Is greedy budget allocation optimal? How could a mixed-integer model improve it?
- What is the difference between fill rate, cycle service and worst-pair service?
- Which costs are real observations and which are scenario coefficients?
- Does the optimizer guarantee the service target? Why not?
- Why use common random numbers and paired differences?
- What happens to pending requests when the DC cannot ship?
- What is persisted after an approval? What is actually dispatched?
- Which result would make you recommend periodic ordering instead of adaptive ordering?
- What would you build next with actual supplier/availability records?

Suggested extensions after reproducing the main run: solve order allocation as an integer program; replace proxy demand with availability-aware estimates; tune direct multi-horizon models; add supplier-specific lead-time learning; extend the network input master to multiple actual DCs; build a monitored service-target dashboard. Each extension should introduce a measurable business question and a testable change.
