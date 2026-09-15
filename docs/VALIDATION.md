# Validation record

Validated locally on 2026-09-15 with Python 3.12.14 and Stockpyl 1.0.2.
See the generated example manifest for all direct scientific-package versions.

## Executed checks

`python -m pytest -q`: **9 tests passed**.

| Check | What it establishes |
|---|---|
| SQL demand moments | Matches independent Pandas mean and sample variance |
| Invalid input rejection | Missing daily data and impossible receipt dates fail |
| Synthetic reproducibility | Fixed seed recreates identical input records |
| Documented Stockpyl path | Deterministic four-period example yields [1, 7, 1, -1] inventory |
| Zero-stock accounting | 120 requested units are recorded as 120 immediately unfilled units |
| Stress-window isolation | Demand multiplier affects only the defined post-warm-up interval |
| Paired statistics | Known constant savings produce the correct sign and interval |
| Seed separation | Overlapping selection/evaluation seeds are rejected |
| End-to-end execution | SQL through search, trials, manifest and chart succeeds |

## Full experiment executed

- 27 target combinations, each assessed on three selection paths.
- Four scenarios × 20 evaluation seeds × two policies = 160 validation trials.
- 60 warm-up days excluded; 365 measured days per validation trial.
- All results committed in `examples/demo/`; no numeric results hand-invented.
- Stockpyl flow consistency checks configured to raise on detected errors.

Normal-scenario savings: 26.37%, with paired absolute savings interval
[13.89, 17.94] cost units/day. Service decreases and adverse-scenario losses are
reported alongside this figure. Two targets hit the search-grid boundary.

## Not established

No real-company deployment, independent code audit, global-optimality proof,
production scalability benchmark, live GitHub CI run or browser-based Colab run
is claimed. This record validates the local demo and focused tests. The provided
GitHub workflow should execute after the repository is published.
