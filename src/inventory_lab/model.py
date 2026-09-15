"""Stockpyl adapter: warehouse 0 → stores 1 and 2, one SKU, backorders."""
import numpy as np
from scipy.stats import norm
from stockpyl.supply_chain_network import network_from_edges
from stockpyl.sim import simulation


def independent_targets(profile, leads, config):
    """Local normal-approximation targets, ignoring upstream availability coupling.

    Store protection time L+1 is a conservative daily-review approximation.
    Warehouse demand mean/variance are sums (independent stores assumed).
    Warehouse uses the mean downstream shortage penalty as a planning proxy;
    realized warehouse shortage cost remains zero to avoid double-counting.
    """
    means = dict(zip(profile.store_id, profile.mean_demand))
    variances = dict(zip(profile.store_id, profile.variance_demand))
    means[0], variances[0] = sum(means.values()), sum(variances.values())
    targets = {}
    for node in [0, 1, 2]:
        h = config["holding_cost"][node]
        p = float(np.mean(config["stockout_penalty"][1:])) if node == 0 else config["stockout_penalty"][node]
        z = norm.ppf(p / (p + h))
        protection = int(leads.loc[node, "model_lead_time"]) + 1
        targets[node] = max(0, int(np.ceil(means[node] * protection + z * np.sqrt(variances[node] * protection))))
    return targets


def demand_paths(samples, periods, seed, multiplier=1.0, warmup=0):
    """Empirical bootstrap; stress begins after warm-up, lasts 25% of horizon."""
    paths = {}
    stop = warmup + max(1, (periods - warmup) // 4)
    for node in [1, 2]:
        rng = np.random.default_rng(np.random.SeedSequence([seed, node]))
        path = rng.choice(samples[node], size=periods, replace=True).astype(int)
        path[warmup:stop] = np.ceil(path[warmup:stop] * multiplier).astype(int)
        paths[node] = path.tolist()
    return paths


def build_network(targets, leads, config, paths, supplier_delay=0):
    nodes = [0, 1, 2]
    transport = [int(leads.loc[i, "model_lead_time"]) + (supplier_delay if i == 0 else 0) for i in nodes]
    return network_from_edges(
        [(0, 1), (0, 2)], node_order_in_lists=nodes,
        local_holding_cost=config["holding_cost"],
        stockout_cost=config["stockout_penalty"],
        shipment_lead_time=transport, order_lead_time=0,
        demand_type=[None, "D", "D"],
        demand_list=[None, paths[1], paths[2]],
        policy_type="BS", base_stock_level=[int(targets[i]) for i in nodes],
        initial_inventory_level=[int(targets[i]) for i in nodes])


def simulate_policy(targets, leads, config, paths, supplier_delay=0):
    periods = len(paths[1])
    if len(paths[2]) != periods or periods <= config["warmup"]:
        raise ValueError("Paths must have equal length and exceed warm-up.")
    network = build_network(targets, leads, config, paths, supplier_delay)
    simulation(network, periods, rand_seed=0, progress_bar=False, consistency_checks="E")
    holding = penalty = demand = filled = backlog_days = shortage_units = 0.0
    count = periods - config["warmup"]
    for node in network.nodes:
        for t in range(config["warmup"], periods):
            state = node.state_vars[t]
            holding += state.holding_cost_incurred
            penalty += state.stockout_cost_incurred
            if node.index in [1, 2]:
                actual = paths[node.index][t]
                met = sum(state.demand_met_from_stock.values())
                demand += actual
                filled += met
                shortage_units += actual - met
                backlog_days += sum(max(-v, 0) for v in state.inventory_level.values())
    return {"cost_per_day": (holding + penalty) / count,
            "holding_per_day": holding / count, "penalty_per_day": penalty / count,
            "fill_rate": filled / demand if demand else 1.0,
            "shortage_units": shortage_units, "backlog_unit_days": backlog_days,
            "demand_units": demand}
