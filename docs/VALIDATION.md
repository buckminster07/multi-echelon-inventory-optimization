# Validation evidence

The version 0.2 full experiment was executed locally. The simulator is implemented
in this repository and no longer depends on Stockpyl. Configuration, dependency
versions and data hashes are recorded in `examples/full/manifest.json`.

**13 local tests passed** before publication. The GitHub workflow independently
runs tests on Python 3.10 and 3.11; the live badge in the README shows its status.

## Checks executed

- A hand-calculated deterministic network yields exact daily stock and cost.
- Zero target stock correctly distinguishes immediate shortages from later service.
- Warm-up demand is excluded; zero demand has defined service metrics.
- Repeated seeds reproduce stochastic results; changed seeds change outcomes.
- Supplier delay changes physical backlog behavior.
- Invalid quantities, missing daily records and bad parent references are rejected.
- SQL means and sample variances match independent Pandas calculations.
- Altering held-out records cannot alter fitted training profiles.
- Scenario transformations leave original demand arrays unchanged.
- A small end-to-end run produces targets, all evaluations and the report.
- Search and evaluation seed overlap is rejected.

All 1,512 full-run SKU simulations (648 search + 864 validation/test) execute
daily physical-stock, demand and open-store-order reconciliation assertions.

## Evidence boundaries

Passing tests is not an external audit or mathematical proof. The demo covers
synthetic data and the stated two-echelon assumptions. It does not establish
real-world forecasting quality, production scalability or deployment safety.
Colab bootstrap is provided; the Colab browser interface was not tested locally.
The search optimum is limited to grouped multiplier candidates.
