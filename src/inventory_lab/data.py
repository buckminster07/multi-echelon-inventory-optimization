"""Auditable synthetic source data, strict CSV contract and training-only SQL."""

from pathlib import Path
from importlib.resources import files
import sqlite3
import numpy as np
import pandas as pd


def generate(days=900, seed=42):
    rng = np.random.default_rng(seed)
    nodes = pd.DataFrame(
        [
            (0, "North warehouse", "warehouse", None, 0.3),
            (1, "South warehouse", "warehouse", None, 0.35),
            (2, "North central", "store", 0, 1),
            (3, "North east", "store", 0, 1.1),
            (4, "South central", "store", 1, 1),
            (5, "South west", "store", 1, 1.15),
        ],
        columns=["node_id", "name", "kind", "parent_id", "holding_cost"],
    )
    skus = pd.DataFrame(
        [
            ("SKU-001", "Everyday", 1, 18),
            ("SKU-002", "Premium", 2, 32),
            ("SKU-003", "Occasional", 0.7, 12),
        ],
        columns=["sku", "label", "cost_multiplier", "shortage_penalty"],
    )
    dates = pd.date_range("2023-01-01", periods=days)
    demand = []
    for node in [2, 3, 4, 5]:
        for sku, mu in zip(skus.sku, [9, 5, 2]):
            for day in dates:
                mean = (
                    mu * (1 + 0.08 * (node - 2)) * (1.2 if day.dayofweek >= 5 else 0.92)
                )
                q = int(rng.negative_binomial(8, 8 / (8 + mean)))
                demand.append((day.date().isoformat(), node, sku, q))
    receipts = []
    for node in range(6):
        for sku in skus.sku:
            for i in range(0, days - 10, 10):
                lead = int(rng.choice([2, 3, 4, 6] if node < 2 else [1, 1, 2, 3]))
                receipts.append(
                    (
                        len(receipts),
                        node,
                        sku,
                        dates[i].date().isoformat(),
                        (dates[i] + pd.Timedelta(days=lead)).date().isoformat(),
                        int(rng.integers(30, 100)),
                    )
                )
    return {
        "nodes": nodes,
        "skus": skus,
        "demand": pd.DataFrame(demand, columns=["date", "node_id", "sku", "quantity"]),
        "receipts": pd.DataFrame(
            receipts,
            columns=[
                "receipt_id",
                "node_id",
                "sku",
                "dispatch_date",
                "receipt_date",
                "quantity",
            ],
        ),
    }


def validate(tables):
    nodes, skus, demand, receipts = [
        tables[x] for x in ["nodes", "skus", "demand", "receipts"]
    ]
    if nodes.node_id.duplicated().any() or skus.sku.duplicated().any():
        raise ValueError("Duplicate node or SKU keys")
    if not set(nodes.kind) <= {"warehouse", "store"}:
        raise ValueError("Unknown node kind")
    stores = nodes[nodes.kind == "store"]
    warehouses = nodes[nodes.kind == "warehouse"]
    if stores.empty or warehouses.empty or not warehouses.parent_id.isna().all():
        raise ValueError(
            "Require warehouses with external suppliers and downstream stores"
        )
    if not set(stores.parent_id) <= set(warehouses.node_id):
        raise ValueError("Every store must reference a warehouse")
    if not set(warehouses.node_id) <= set(stores.parent_id):
        raise ValueError("Every warehouse must serve a store")
    for values in [nodes.holding_cost, skus.cost_multiplier, skus.shortage_penalty]:
        if not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError("Costs must be positive and finite")
    for table, key in [
        (demand, ["date", "node_id", "sku"]),
        (receipts, ["receipt_id"]),
    ]:
        if table.isna().any().any() or table.duplicated(key).any():
            raise ValueError("Null or duplicate records")
        q = table.quantity
        if not np.isfinite(q).all() or (q < 0).any() or (q % 1 != 0).any():
            raise ValueError("Invalid quantities")
    if (receipts.quantity <= 0).any():
        raise ValueError("Receipt quantity must be positive")
    if set(demand.node_id) != set(stores.node_id) or set(demand.sku) != set(skus.sku):
        raise ValueError("Demand network mismatch")
    if not set(receipts.node_id) <= set(nodes.node_id) or not set(receipts.sku) <= set(
        skus.sku
    ):
        raise ValueError("Unknown receipt key")
    d = pd.to_datetime(demand.date, errors="raise")
    dates = pd.date_range(d.min(), d.max())
    if len(dates) < 90:
        raise ValueError("At least 90 calendar days required")
    if len(demand.groupby(["node_id", "sku"])) != len(stores) * len(skus):
        raise ValueError("Missing store/SKU series")
    for _, frame in demand.groupby(["node_id", "sku"]):
        if not pd.DatetimeIndex(pd.to_datetime(frame.date)).sort_values().equals(dates):
            raise ValueError("Missing daily demand, including zero days")
    start = pd.to_datetime(receipts.dispatch_date, errors="raise")
    end = pd.to_datetime(receipts.receipt_date, errors="raise")
    if (end <= start).any() or (start < d.min()).any() or (end > d.max()).any():
        raise ValueError("Invalid receipt dates")


def prepare(tables, output, config):
    validate(tables)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    database = output / "inventory.sqlite"
    if database.exists():
        database.unlink()
    with sqlite3.connect(database) as con:
        con.executescript(files("inventory_lab").joinpath("sql/schema.sql").read_text())
        for name in ["nodes", "skus", "demand", "receipts"]:
            tables[name].to_sql(name, con, if_exists="append", index=False)
            tables[name].to_csv(output / f"{name}.csv", index=False)
        dates = sorted(tables["demand"].date.unique())
        tr = config["train_days"]
        va = tr + config["validation_days"]
        if tr < 30 or config["validation_days"] < 10 or len(dates) - va < 10:
            raise ValueError("Insufficient data for chronological splits")
        cutoff = dates[tr]
        profile = pd.read_sql_query(
            files("inventory_lab").joinpath("sql/profile.sql").read_text(),
            con,
            params={"cutoff": cutoff},
        )
        leads = pd.read_sql_query(
            files("inventory_lab").joinpath("sql/lead_times.sql").read_text(),
            con,
            params={"cutoff": cutoff},
        )
    expected = {
        (int(n), s) for n in tables["nodes"].node_id for s in tables["skus"].sku
    }
    if set(zip(leads.node_id, leads.sku)) != expected:
        raise ValueError("Every node/SKU needs observed training receipts")
    profile.to_csv(output / "demand_profile.csv", index=False)
    lp = leads.groupby(["node_id", "sku"]).lead_days.agg(
        ["count", "mean", "std", "min", "max"]
    )
    lp["p90"] = leads.groupby(["node_id", "sku"]).lead_days.quantile(0.9)
    lp.to_csv(output / "lead_time_profile.csv")
    splits = {"train": dates[:tr], "validation": dates[tr:va], "test": dates[va:]}
    series = {}
    for sku in tables["skus"].sku:
        # Explicit filtering avoids query-local scope differences across Python versions.
        demand = tables["demand"]
        frame = demand.loc[demand["sku"] == sku].pivot(
            index="date", columns="node_id", values="quantity"
        )
        series[sku] = {split: frame.loc[ds] for split, ds in splits.items()}
    return profile, leads, series, splits
