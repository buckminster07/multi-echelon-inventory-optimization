"""Finite-grid joint optimization and paired, out-of-sample policy evaluation."""
import numpy as np
import pandas as pd
from scipy.stats import t
from stockpyl.meio_general import meio_by_enumeration
from .model import build_network, demand_paths, simulate_policy


def optimize(baseline, leads, samples, config):
    paths = [demand_paths(samples, config["warmup"] + config["optimization_periods"], seed)
             for seed in config["optimization_seeds"]]
    grid = {node: sorted({max(0, int(round(value * m))) for m in config["grid_multipliers"]} | {value})
            for node, value in baseline.items()}
    candidates = []
    def objective(targets):
        cost = float(np.mean([simulate_policy(targets, leads, config, p)["cost_per_day"] for p in paths]))
        candidates.append({**{f"node_{i}": int(targets[i]) for i in [0, 1, 2]}, "training_cost_per_day": cost})
        return cost
    network = build_network(baseline, leads, config, paths[0])
    best, cost = meio_by_enumeration(network, base_stock_levels=grid,
                                    objective_function=objective, progress_bar=False)
    return {int(k): int(v) for k, v in best.items()}, float(cost), pd.DataFrame(candidates), grid


def evaluate(policies, leads, samples, config):
    if set(config["optimization_seeds"]) & set(config["evaluation_seeds"]):
        raise ValueError("Optimization and evaluation seeds must be disjoint.")
    rows = []
    for scenario, settings in config["scenarios"].items():
        for seed in config["evaluation_seeds"]:
            paths = demand_paths(samples, config["warmup"] + config["evaluation_periods"], seed,
                                 settings["demand_multiplier"], config["warmup"])
            for policy, targets in policies.items():
                metrics = simulate_policy(targets, leads, config, paths, settings["supplier_delay"])
                rows.append({"scenario": scenario, "seed": seed, "policy": policy, **metrics})
    return pd.DataFrame(rows)


def paired_summary(trials):
    rows = []
    for scenario, frame in trials.groupby("scenario", sort=False):
        cost = frame.pivot(index="seed", columns="policy", values="cost_per_day")
        delta = cost.independent - cost.coordinated
        n = len(delta)
        margin = float(t.ppf(0.975, n - 1) * delta.std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan")
        b, c = cost.independent.mean(), cost.coordinated.mean()
        fill = frame.groupby("policy").fill_rate.mean()
        rows.append({"scenario": scenario, "trials": n,
                     "independent_cost": b, "coordinated_cost": c,
                     "saving_pct": 100 * (b - c) / b if b else 0,
                     "saving_per_day": delta.mean(),
                     "saving_ci95_low": delta.mean() - margin,
                     "saving_ci95_high": delta.mean() + margin,
                     "independent_fill": fill.independent,
                     "coordinated_fill": fill.coordinated})
    return pd.DataFrame(rows)
