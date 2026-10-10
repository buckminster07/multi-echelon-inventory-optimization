# Business brief: inventory decision intelligence

## The assignment

An online retailer sells a broad giftware catalog to several international markets. Management wants a repeatable way to decide how much to replenish, where to hold stock, and which exceptions planners should review. Finance wants visibility into inventory capital; commercial teams want high availability; operations must respect supplier lead times, warehouse space, pack sizes and purchasing budgets.

Build a decision-support pipeline that answers:

1. Which product–market combinations deserve attention, and what demand patterns do they exhibit?
2. Does a global machine-learning forecast improve on simple and intermittent-demand methods?
3. How much uncertainty should inventory targets protect against?
4. How do replenishment policies behave when warehouse supply, space and budget are limited?
5. Which tested stock-target settings give the best cost/service tradeoff?
6. Can a planner inspect, approve, reduce or reject a proposed order and evaluate the consequences?

## Dataset chosen

**UCI Online Retail II**, contributed by Daqing Chen: [dataset](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii), [DOI](https://doi.org/10.24432/C5CG6D). It contains 1,067,371 transaction rows from December 2009 to December 2011. Product codes, quantities, invoice dates, selling prices, cancellation flags and customer countries support demand analysis. License: **CC BY 4.0**. Attribute the source and describe transformations when sharing derived data.

This dataset was selected because it has two years of transactions, product-level quantities and prices, meaningful data-cleaning issues, intermittent demand and multiple destination markets. No account, API key or competition registration is required. It is preferable here to inventing a retail demand history. The dates describe the source data, not a claimed project employment period.

## Scope that follows from the business problem

The full profile selects the top **150 products** and **six destination markets** by revenue in the initial training period, subject to product history requirements. Active product–market pairs need at least three training transaction lines; products require at least thirty distinct training sales dates. These are compute/assortment rules, not claims about an entire enterprise. The quick profile uses 24 products and three markets. Their actual active-pair counts and market names are exported.

Country is a destination market, not an observed warehouse. We evaluate a **proposed central distribution center plus one hub per selected market**. This is a design experiment for stock placement, not evidence that the retailer operated that network. The network must become an input master before deployment. Inventory, lead-time, availability and cost records are absent; they are transparent operating assumptions.

Sales are not unconstrained demand. The dataset has no reliable historical stockout flags, so the main experiment uses positive gross sales as a demand proxy. Its results are conditional on that proxy. A sensitivity analysis adds 10% and 25% unobserved demand without giving the policy advance knowledge. Returns are audited separately and excluded from outbound demand; no recovery into sellable stock is assumed.

## Proposed decision rules

- Daily planning, with weekly forecasts published before the day's observations.
- Replenishment moves from an external supplier to the central DC, then to market hubs.
- Customer demand that cannot be served immediately is lost in the simulator. Internal hub requests remain queued until the DC dispatches them.
- Compare fixed days of cover, a daily approximation of (r,Q), weekly order-up-to, and forecast-aware targets with calibrated buffers.
- Respect per-product and shared location capacity, line purchasing budgets, six-unit packs and twelve-unit minimum orders.
- Tune joint hub/DC buffer settings on August only; validate in September; report untouched October–November test results.
- Proposed tuning objectives: at least 95% aggregate fill and 97% A-item fill in every tuning scenario, then minimum relevant cost. If no tested candidate qualifies, report the least violating candidate explicitly.

## What counts as success

A defensible result is a reproducible recommendation with evidence and limitations. It need not show that the most complex policy always wins. Report forecast accuracy, interval coverage, fill, lost units, stockholding, costs, terminal capital, constrained orders and paired uncertainty. Explain which policy is preferred under which circumstances and why.

The delivered artifact is a complete Colab/Python decision-support project with an auditable prototype workflow. Production adoption additionally requires actual network/supplier inputs, demand-availability data, user identity, transactional ERP dispatch and monitored service outcomes. These are concrete implementation boundaries, not reasons to avoid a substantial working project.
