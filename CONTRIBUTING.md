# Contributing

Install with `python -m pip install -e '.[dev]'` and run `python -m pytest -q`.
Keep configuration changes explicit and regenerate example outputs when model
assumptions change. Include a test for accounting, timing or metric changes.
Do not select evaluation seeds based on favorable results. Report regressions
as well as improvements; keep upstream Stockpyl attribution intact.
