# Decision brief

**Question:** should an operations team select the policy with the lowest normal-day cost?

The experiment says that choice carries service and disruption risk. Normal-cost
optimization saves 22.0% under ordinary test demand, but aggregate fill falls to
94.14%, and combined-stress cost becomes 2.77 times the independent baseline.

The service-aware candidate maintains more stock. In the combined-stress test it
cuts costs 31.6% and lifts aggregate fill 11.37 percentage points versus independent
planning. Yet its worst store–SKU fill is only 74.77%, and its normal-day costs are
42.2% higher. It does not meet all service commitments.

**Decision supported:** use the report to price resilience and identify vulnerable
store/SKU pairs. Do not deploy the selected service-aware targets solely because
the training feasibility flag is true. A planner would need to address held-out
failures and approve the incremental carrying cost.

**Next experiment:** include joint disruptions in the design objective, expand
the search and use more training replications, then reserve a fresh evaluation
window or independently generated demand dataset. Do not repeatedly tune to the
current test results and continue calling them untouched.

This is a simulation decision study. No live deployment, stakeholder study or
employer performance improvement is claimed.
