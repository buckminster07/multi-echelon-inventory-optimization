# Attribution and implementation provenance

Version 0.1 used [Stockpyl](https://github.com/LarrySnyder/stockpyl) to execute
simulation and target enumeration. That prototype remains in Git history.
Stockpyl's [MEIO](https://stockpyl.readthedocs.io/en/latest/tutorial/tutorial_meio.html)
and [simulation](https://stockpyl.readthedocs.io/en/latest/tutorial/tutorial_sim.html)
documentation informed the initial project framing.

Version 0.2 replaces that dependency with an application-specific Python simulator
and finite-grid search written in this repository. Base-stock policies, safety-stock
approximations, simulation and paired inference are established methods; no claim
of inventing these methods is made.

The implementation and documentation were developed with AI assistance. The
portfolio owner should review and reproduce the results before presenting them.
There is no implied employer endorsement. The earlier version 0.2 experiment uses synthetic data.
General numerical/data libraries retain their own licenses. Repository code is MIT.

The real-data retail workflow uses **Online Retail II**, contributed by Daqing Chen,
UCI Machine Learning Repository, https://doi.org/10.24432/C5CG6D, under CC BY 4.0.
The original dataset is downloaded on demand and retains its separate data license.
Cleaning, cohort selection, demand models, constrained replenishment, planner audit
and evaluation are implemented in `retail_planner/`. Actual transactions and assumed
operating inputs are distinguished in `docs/RETAIL_DATA_CARD.md`.
