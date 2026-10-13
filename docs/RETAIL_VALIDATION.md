# Verification and validation

The real-data pipeline is tested separately from the earlier synthetic inventory model.

## Automated checks

The test suite retains the legacy simulator tests and adds checks for:

- Joint order quantity, MOQ, pack, space and budget feasibility.
- Future-data mutation: later actuals cannot alter an earlier multi-step forecast.
- Training-only cohort selection: extreme future sales cannot change the chosen products.
- Daily material balance, supplier/internal timing and repeatable common random numbers.
- Independent cost totals and requested = fulfilled + lost identities.
- Transactional approvals: invalid packs, unallocated increases, missing actor and repeated decisions fail; valid reductions persist.

Run from the repository root:

```bash
python -m pip install -e '.[dev]'
python -m pip install -r retail_requirements.txt
python -m pytest -q
```

The GitHub Actions workflow runs the tests on Python 3.10 and 3.11. Its badge describes actual remote status; local execution does not imply remote CI completion.

## Experiment evidence

The extended EDA adds four tests for raw-sales cutoff denominators and training boundaries, unlinked returned-unit ratios, consecutive sufficiently populated price months, and a known synthetic weekday pattern with an incomplete final month. All 22 tests pass locally. Five EDA figures were generated from the original workbook and visually checked. Missingness covers both original sheets; behavioral diagnostics end at the initial training cutoff. The original inventory-policy benchmark is unchanged.

The full real-data experiment downloads/cleans the original workbook, integrates the training-selected cohort through SQLite, trains and selects forecasts, calibrates uncertainty, tunes policies, and evaluates held-out months. Manifests include source/data hashes, versions and seeds. Curated results are under `examples/retail/`; full CSVs, SQLite and shipment traces regenerate through the CLI/Colab notebook.

The first exploratory run exposed a budget-cadence confound: weekly policies could only spend one daily allocation per review. The final implementation uses a common rolling seven-day budget and reruns tuning and all evaluations. Earlier exploratory outputs are not the published benchmark.

Notebook verification executes its Python cells sequentially in an existing local checkout with the quick real-data profile. This verifies the computational path and exports. It does not establish Google Colab browser rendering, remote package availability or participant usability. A fresh Colab run should use the published notebook's setup cell and record the source revision.

## Proposed usability study

Use 5–8 planners or documented proxies. Give the same brief training and counterbalance task order. Tasks: find a risky product/market, compare policies under stress, inspect a proposal's constraints, reduce a quantity validly, reject an unnecessary order, replay decisions and export the audit. Record success, completion time, wrong-product selections, invalid submissions and explanation quality. Proposed targets are ≥90% task success, zero invalid persisted quantities and median task time below two minutes. No participant study is claimed.

## Business interpretation limits

Real sales are a lower-bound demand proxy when stockouts occurred. The network, lead times and cost coefficients are assumed. Confidence intervals describe scenario randomness conditional on the recorded sales. They do not establish actual company savings, unconstrained-demand forecast accuracy or a service guarantee. Weak final service should lead to revisiting capacity, assortment, lead-time promises and bulk-order handling—not to hiding the failed target.
