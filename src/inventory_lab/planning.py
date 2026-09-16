"""Independent analytical baseline and joint warehouse/store target search."""

import numpy as np
from scipy.stats import norm
from .simulator import Network, simulate


def network_for(tables, leads, sku):
    nodes = tables["nodes"]
    item = tables["skus"].set_index("sku").loc[sku]
    return Network(
        tuple(int(n) for n in nodes.node_id),
        tuple(int(n) for n in nodes[nodes.kind == "store"].node_id),
        tuple(int(n) for n in nodes[nodes.kind == "warehouse"].node_id),
        {
            int(r.node_id): int(r.parent_id)
            for r in nodes[nodes.kind == "store"].itertuples()
        },
        {
            int(r.node_id): float(r.holding_cost * item.cost_multiplier)
            for r in nodes.itertuples()
        },
        float(item.shortage_penalty),
        {
            int(n): leads[(leads.node_id == n) & (leads.sku == sku)].lead_days.to_numpy(
                dtype=int
            )
            for n in nodes.node_id
        },
    )


def baseline_targets(net, profile, sku):
    p = profile[profile.sku == sku].set_index("node_id")
    mu = {n: float(p.loc[n, "mean_demand"]) for n in net.stores}
    var = {n: float(p.loc[n, "variance_demand"]) for n in net.stores}
    for wh in net.warehouses:
        children = [n for n in net.stores if net.parents[n] == wh]
        mu[wh] = sum(mu[n] for n in children)
        var[wh] = sum(var[n] for n in children)
    result = {}
    for n in net.nodes:
        ls = net.lead_samples[n]
        protection = float(np.mean(ls)) + 1
        sigma = np.sqrt(var[n] * protection + mu[n] ** 2 * np.var(ls, ddof=0))
        z = norm.ppf(net.penalty / (net.penalty + net.holding[n]))
        result[n] = max(0, int(np.ceil(mu[n] * protection + z * sigma)))
    return result


def apply_scenario(paths, settings, warmup):
    result = {n: np.array(x, dtype=int).copy() for n, x in paths.items()}
    length = len(next(iter(result.values()))) - warmup
    start = warmup + length // 3
    end = start + max(1, length // 4)
    for n in result:
        result[n][start:end] = np.ceil(
            result[n][start:end] * settings["spike_multiplier"]
        ).astype(int)
    return result


def search(net, baseline, train, config):
    records = []
    targets_by_id = {}
    multipliers = config["grid_multipliers"]
    warm = config["warmup"]
    days = config["search_days"]
    paths = {}
    # Resample whole observed days: cross-store dependence is retained within a SKU.
    for seed in config["search_seeds"]:
        rng = np.random.default_rng(seed)
        sample = train.iloc[rng.integers(0, len(train), size=warm + days)]
        for name in config["search_scenarios"]:
            paths[(seed, name)] = apply_scenario(
                {int(n): sample[n].to_numpy() for n in sample},
                config["scenarios"][name],
                warm,
            )
    for wm in multipliers:
        for sm in multipliers:
            candidate = len(targets_by_id)
            targets = {
                n: max(
                    0, int(np.ceil(baseline[n] * (wm if n in net.warehouses else sm)))
                )
                for n in net.nodes
            }
            targets_by_id[candidate] = targets
            scenario_costs = {}
            min_fill = 1.0
            for name in config["search_scenarios"]:
                costs = []
                totals = {n: [0, 0] for n in net.stores}
                for seed in config["search_seeds"]:
                    m, counts, _ = simulate(
                        net,
                        targets,
                        paths[(seed, name)],
                        seed,
                        warm,
                        config["scenarios"][name]["supplier_delay"],
                    )
                    costs.append(m["cost_per_day"])
                    for n, (filled, dem) in counts.items():
                        totals[n][0] += filled
                        totals[n][1] += dem
                scenario_costs[name] = float(np.mean(costs))
                min_fill = min(
                    min_fill, min(f / d if d else 1 for f, d in totals.values())
                )
            records.append(
                {
                    "candidate": candidate,
                    "warehouse_multiplier": wm,
                    "store_multiplier": sm,
                    "normal_cost": scenario_costs["normal"],
                    "stress_mean_cost": float(np.mean(list(scenario_costs.values()))),
                    "worst_store_scenario_fill": min_fill,
                    "feasible": min_fill >= config["target_fill_rate"],
                }
            )
    normal = min(records, key=lambda r: r["normal_cost"])
    feasible = [r for r in records if r["feasible"]]
    robust = (
        min(feasible, key=lambda r: r["stress_mean_cost"])
        if feasible
        else min(
            records,
            key=lambda r: (-r["worst_store_scenario_fill"], r["stress_mean_cost"]),
        )
    )
    policies = {
        "independent": baseline,
        "normal_optimized": targets_by_id[normal["candidate"]],
        "service_aware": targets_by_id[robust["candidate"]],
    }
    selection = {
        "normal_candidate": normal["candidate"],
        "service_candidate": robust["candidate"],
        "service_feasible_on_training": bool(feasible),
        "training_worst_fill": robust["worst_store_scenario_fill"],
        "service_at_search_boundary": any(
            robust[k] in (min(multipliers), max(multipliers))
            for k in ["warehouse_multiplier", "store_multiplier"]
        ),
    }
    return policies, records, selection
