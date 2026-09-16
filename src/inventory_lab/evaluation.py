"""Chronological held-out demand and paired lead-time uncertainty evaluation."""

import numpy as np
import pandas as pd
from scipy.stats import t
from .simulator import simulate
from .planning import apply_scenario


def evaluate(net, policies, history, config, split, sku):
    # Warm-up uses immediately preceding observations, never future demand.
    preceding = (
        history["train"]
        if split == "validation"
        else pd.concat([history["train"], history["validation"]])
    )
    warm = config["warmup"]
    if len(preceding) < warm:
        raise ValueError("Not enough historical days for warm-up")
    pre = preceding.tail(warm) if warm else preceding.iloc[:0]
    frame = pd.concat([pre, history[split]])
    rows = []
    store_rows = []
    traces = []
    for name, settings in config["scenarios"].items():
        paths = apply_scenario(
            {int(n): frame[n].to_numpy() for n in frame}, settings, warm
        )
        for seed in config["evaluation_seeds"]:
            for policy, targets in policies.items():
                m, counts, trace = simulate(
                    net,
                    targets,
                    paths,
                    seed,
                    warm,
                    settings["supplier_delay"],
                    record=seed == config["evaluation_seeds"][0],
                )
                keys = {
                    "split": split,
                    "scenario": name,
                    "seed": seed,
                    "sku": sku,
                    "policy": policy,
                }
                rows.append({**keys, **m})
                store_rows.extend(
                    {
                        **keys,
                        "node_id": n,
                        "immediate_units": f,
                        "demand_units": d,
                        "fill_rate": f / d if d else 1.0,
                    }
                    for n, (f, d) in counts.items()
                )
                traces.extend({**keys, **row} for row in trace)
    return rows, store_rows, traces


def summarize(trials, store_trials):
    # Sum costs across SKUs, demand-weight service; one paired observation per seed.
    keys = ["split", "scenario", "seed", "policy"]
    agg = (
        trials.groupby(keys, sort=False)
        .agg(
            cost_per_day=("cost_per_day", "sum"),
            demand_units=("demand_units", "sum"),
            immediate_units=("immediate_units", "sum"),
            shortage_units=("shortage_units", "sum"),
            backlog_unit_days=("backlog_unit_days", "sum"),
            mean_on_hand=("mean_on_hand", "sum"),
        )
        .reset_index()
    )
    agg["fill_rate"] = np.where(
        agg.demand_units > 0, agg.immediate_units / agg.demand_units, 1.0
    )
    summaries = []
    for (split, scenario), frame in agg.groupby(["split", "scenario"], sort=False):
        baseline = frame[frame.policy == "independent"].set_index("seed").cost_per_day
        for policy, g in frame.groupby("policy", sort=False):
            costs = g.set_index("seed").cost_per_day
            delta = baseline - costs
            half = float(
                t.ppf(0.975, len(delta) - 1) * delta.std(ddof=1) / np.sqrt(len(delta))
            )
            stores = (
                store_trials[
                    (store_trials.split == split)
                    & (store_trials.scenario == scenario)
                    & (store_trials.policy == policy)
                ]
                .groupby(["sku", "node_id"])[["immediate_units", "demand_units"]]
                .sum()
            )
            worst = float(
                np.where(
                    stores.demand_units > 0,
                    stores.immediate_units / stores.demand_units,
                    1.0,
                ).min()
            )
            summaries.append(
                {
                    "split": split,
                    "scenario": scenario,
                    "policy": policy,
                    "cost_per_day": costs.mean(),
                    "fill_rate": g.immediate_units.sum() / g.demand_units.sum()
                    if g.demand_units.sum()
                    else 1.0,
                    "worst_store_sku_fill": worst,
                    "shortage_units": g.shortage_units.mean(),
                    "backlog_unit_days": g.backlog_unit_days.mean(),
                    "mean_on_hand": g.mean_on_hand.mean(),
                    "saving_pct": 100 * delta.mean() / baseline.mean()
                    if baseline.mean()
                    else 0.0,
                    "saving_per_day": delta.mean(),
                    "ci95_low": delta.mean() - half,
                    "ci95_high": delta.mean() + half,
                }
            )
    return pd.DataFrame(summaries), agg
