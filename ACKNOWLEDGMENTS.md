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
There is no implied professor or employer endorsement. Data is explicitly synthetic.
General numerical/data libraries retain their own licenses. Repository code is MIT.
