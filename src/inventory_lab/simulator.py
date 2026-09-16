"""From-scratch daily discrete-event simulator. No Stockpyl dependency.

Receipts → old/new customer demand → store orders → FIFO warehouse shipments
→ supplier orders → accounting. Positive integer per-order lead times.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class Network:
    nodes: tuple
    stores: tuple
    warehouses: tuple
    parents: dict
    holding: dict
    penalty: float
    lead_samples: dict


def simulate(
    network,
    targets,
    demand,
    seed=1,
    warmup=0,
    supplier_delay=0,
    record=False,
    check=True,
):
    if set(targets) != set(network.nodes) or any(
        v < 0 or int(v) != v for v in targets.values()
    ):
        raise ValueError("Require a nonnegative integer stock target at every node")
    if set(demand) != set(network.stores):
        raise ValueError("Demand must cover each store")
    horizon = len(next(iter(demand.values())))
    if horizon <= warmup or warmup < 0:
        raise ValueError("Invalid warm-up")
    if any(
        len(x) != horizon
        or not np.isfinite(x).all()
        or (np.asarray(x) < 0).any()
        or (np.asarray(x) % 1 != 0).any()
        for x in demand.values()
    ):
        raise ValueError("Invalid demand paths")
    if supplier_delay < 0 or int(supplier_delay) != supplier_delay:
        raise ValueError("Invalid supplier delay")
    onhand = {n: int(targets[n]) for n in network.nodes}
    backlog = {n: 0 for n in network.stores}
    outstanding = {n: 0 for n in network.stores}
    vendor_open = {n: 0 for n in network.warehouses}
    pending = {n: [] for n in network.warehouses}
    # Shipments: (due_day, destination, quantity, external_supplier).
    shipments = []
    lead_rng = {
        n: np.random.default_rng(np.random.SeedSequence([seed, int(n), 11]))
        for n in network.nodes
    }
    initial = sum(onhand.values())
    received = shipped = total_requested = 0
    metrics = {
        "holding_cost": 0.0,
        "shortage_cost": 0.0,
        "demand_units": 0,
        "immediate_units": 0,
        "shortage_units": 0,
        "backlog_unit_days": 0,
        "inventory_unit_days": 0,
    }
    store_demand = {n: 0 for n in network.stores}
    store_fill = {n: 0 for n in network.stores}
    trace = []
    for day in range(horizon):
        # Draw for every node/day, regardless of policy, preserving common random numbers.
        lead = {
            n: int(lead_rng[n].choice(network.lead_samples[n]))
            + (supplier_delay if n in network.warehouses else 0)
            for n in network.nodes
        }
        if min(lead.values()) < 1:
            raise ValueError("Lead times must be positive integer days")
        future = []
        for due, node, q, external in shipments:
            if due <= day:
                onhand[node] += q
                if external:
                    vendor_open[node] -= q
                    received += q
                else:
                    outstanding[node] -= q
            else:
                future.append((due, node, q, external))
        shipments = future
        day_demand = day_fill = 0
        for node in network.stores:
            old = min(backlog[node], onhand[node])
            backlog[node] -= old
            onhand[node] -= old
            shipped += old
            q = int(demand[node][day])
            total_requested += q
            met = min(q, onhand[node])
            onhand[node] -= met
            shipped += met
            backlog[node] += q - met
            day_demand += q
            day_fill += met
            if day >= warmup:
                store_demand[node] += q
                store_fill[node] += met
        # Rotate same-day store order priority; older unfilled requests remain first.
        ordered = list(network.stores)
        shift = day % len(ordered)
        ordered = ordered[shift:] + ordered[:shift]
        for node in ordered:
            ip = onhand[node] + outstanding[node] - backlog[node]
            q = max(0, int(targets[node]) - ip)
            if q:
                pending[network.parents[node]].append([node, q])
                outstanding[node] += q
        for wh in network.warehouses:
            queue = []
            for node, q in pending[wh]:
                sent = min(q, onhand[wh])
                onhand[wh] -= sent
                if sent:
                    shipments.append((day + lead[node], node, sent, False))
                if sent < q:
                    queue.append([node, q - sent])
            pending[wh] = queue
            ip = onhand[wh] + vendor_open[wh] - sum(q for _, q in queue)
            q = max(0, int(targets[wh]) - ip)
            if q:
                vendor_open[wh] += q
                shipments.append((day + lead[wh], wh, q, True))
        holding = sum(onhand[n] * network.holding[n] for n in network.nodes)
        short = sum(backlog.values()) * network.penalty
        if check:
            internal = sum(q for _, _, q, ext in shipments if not ext)
            assert initial + received == sum(onhand.values()) + internal + shipped, (
                "Material balance failed"
            )
            assert total_requested == shipped + sum(backlog.values()), (
                "Demand balance failed"
            )
            assert all(q >= 0 for q in onhand.values()), "Negative physical stock"
            for node in network.stores:
                owed = sum(
                    q for wh in network.warehouses for s, q in pending[wh] if s == node
                )
                transit = sum(q for _, s, q, ext in shipments if s == node and not ext)
                assert outstanding[node] == owed + transit, "Order balance failed"
        if day >= warmup:
            metrics["holding_cost"] += holding
            metrics["shortage_cost"] += short
            metrics["demand_units"] += day_demand
            metrics["immediate_units"] += day_fill
            metrics["shortage_units"] += day_demand - day_fill
            metrics["backlog_unit_days"] += sum(backlog.values())
            metrics["inventory_unit_days"] += sum(onhand.values())
            if record:
                trace.append(
                    {
                        "day": day - warmup,
                        "on_hand": sum(onhand.values()),
                        "backlog": sum(backlog.values()),
                        "demand": day_demand,
                        "immediate": day_fill,
                        "holding_cost": holding,
                        "shortage_cost": short,
                    }
                )
    measured = horizon - warmup
    metrics["cost_per_day"] = (
        metrics["holding_cost"] + metrics["shortage_cost"]
    ) / measured
    metrics["fill_rate"] = (
        metrics["immediate_units"] / metrics["demand_units"]
        if metrics["demand_units"]
        else 1.0
    )
    metrics["mean_on_hand"] = metrics["inventory_unit_days"] / measured
    metrics["measured_days"] = measured
    return metrics, {n: (store_fill[n], store_demand[n]) for n in network.stores}, trace
