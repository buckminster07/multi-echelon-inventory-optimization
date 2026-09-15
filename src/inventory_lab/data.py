"""Generate explicitly synthetic records and estimate parameters through SQLite."""
from importlib.resources import files
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd


def generate_records(days=540, seed=42):
    if days < 30:
        raise ValueError("Use at least 30 training days.")
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=days)
    records = []
    for store, mean in [(1, 8), (2, 12)]:
        # Overdispersed demand: variance = mean + mean**2 / dispersion.
        values = rng.negative_binomial(10, 10 / (10 + mean), days)
        records.extend((d.date().isoformat(), store, "SKU-001", int(q))
                       for d, q in zip(dates, values))
    orders = []
    for node, choices in [(0, [2, 3, 4, 5]), (1, [1, 1, 2, 3]), (2, [1, 2, 2, 3])]:
        for i in range(0, days - 7, 7):
            start = dates[i]
            end = start + pd.Timedelta(days=int(rng.choice(choices)))
            orders.append((len(orders), node, start.date().isoformat(),
                           end.date().isoformat(), int(rng.integers(25, 100))))
    return (pd.DataFrame(records, columns=["date", "store_id", "sku", "quantity"]),
            pd.DataFrame(orders, columns=["order_id", "node_id", "order_date", "receipt_date", "quantity"]))


def validate_records(demand, replenishment):
    """Reject gaps, invalid dates, duplicates and unsupported network shapes."""
    if set(demand.store_id) != {1, 2} or set(demand.sku) != {"SKU-001"}:
        raise ValueError("Expected stores 1/2 and exactly SKU-001.")
    if set(replenishment.node_id) != {0, 1, 2}:
        raise ValueError("Expected replenishment for nodes 0/1/2.")
    if demand.isna().any().any() or replenishment.isna().any().any():
        raise ValueError("Null values are not allowed.")
    if demand.duplicated(["date", "store_id", "sku"]).any():
        raise ValueError("Duplicate daily demand records.")
    if replenishment.order_id.duplicated().any():
        raise ValueError("Duplicate order IDs.")
    for series in [demand.quantity, replenishment.quantity]:
        if not np.isfinite(series).all() or (series < 0).any() or (series % 1 != 0).any():
            raise ValueError("Quantities must be finite, nonnegative integers.")
    if (replenishment.quantity == 0).any():
        raise ValueError("Replenishment quantities must be positive.")
    all_dates = pd.to_datetime(demand.date, errors="raise")
    expected = pd.date_range(all_dates.min(), all_dates.max(), freq="D")
    for _, frame in demand.groupby("store_id"):
        actual = pd.DatetimeIndex(pd.to_datetime(frame.date)).sort_values()
        if len(actual) < 30 or not actual.equals(expected):
            raise ValueError("Demand must include every day, including zero-demand days.")
    starts = pd.to_datetime(replenishment.order_date, errors="raise")
    ends = pd.to_datetime(replenishment.receipt_date, errors="raise")
    if (ends < starts).any() or (starts < all_dates.min()).any() or (ends > all_dates.max()).any():
        raise ValueError("Receipts must follow orders and lie inside the training window.")


def build_database(demand, replenishment, path):
    validate_records(demand, replenishment)
    path = Path(path)
    if path.exists():
        path.unlink()  # Derived output, rebuilt only inside the selected output directory.
    with sqlite3.connect(path) as con:
        con.executescript(files("inventory_lab").joinpath("sql/schema.sql").read_text())
        demand.to_sql("demand", con, if_exists="append", index=False)
        replenishment.to_sql("replenishment", con, if_exists="append", index=False)


def estimate_parameters(path):
    with sqlite3.connect(path) as con:
        profile = pd.read_sql_query(files("inventory_lab").joinpath("sql/demand_profile.sql").read_text(), con)
        leads = pd.read_sql_query(files("inventory_lab").joinpath("sql/lead_times.sql").read_text(), con)
        samples = {s: pd.read_sql_query("SELECT quantity FROM demand WHERE store_id=? ORDER BY date", con, params=(s,)).quantity.to_numpy() for s in [1, 2]}
    lead_profile = leads.groupby("node_id").lead_time_days.agg(["count", "mean", "std", "median", "max"])
    lead_profile["p90"] = leads.groupby("node_id").lead_time_days.quantile(0.9)
    # Stockpyl uses fixed integer transport times in this experiment.
    lead_profile["model_lead_time"] = np.ceil(lead_profile["mean"]).astype(int)
    return profile, lead_profile, samples
