# Contributing

Install with `python -m pip install -e ".[dev]"` and run `python -m pytest -q`.
Simulation changes should include a hand-checkable example and preserve inventory,
demand and open-order balances. Changes to metrics need explicit documentation.
Never select evaluation seeds based on favorable outcomes. Preserve failure cases
in reports. Keep data provenance and historical results distinct when regenerating
examples. See `docs/METHODOLOGY.md` before changing the event sequence.
