import sqlite3
import numpy as np
import pytest
from inventory_lab.data import generate_records, build_database, estimate_parameters, validate_records


def test_sql_moments_match_independent_calculation(tmp_path):
    demand, orders = generate_records(90, 7)
    db = tmp_path / "test.sqlite"
    build_database(demand, orders, db)
    profile, leads, _ = estimate_parameters(db)
    for row in profile.itertuples():
        values = demand.loc[demand.store_id == row.store_id, "quantity"]
        assert row.mean_demand == pytest.approx(values.mean())
        assert row.variance_demand == pytest.approx(values.var(ddof=1))
    assert (leads.model_lead_time >= leads['mean']).all()
    with sqlite3.connect(db) as con:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO demand VALUES ('2023-01-01',1,'SKU-001',-1)")


def test_reject_missing_day_and_invalid_receipt():
    demand, orders = generate_records(90)
    with pytest.raises(ValueError, match="every day"):
        validate_records(demand.iloc[1:], orders)
    orders.loc[0, "receipt_date"] = "2022-12-31"
    with pytest.raises(ValueError, match="Receipts"):
        validate_records(demand, orders)


def test_synthetic_data_reproducible():
    a, b = generate_records(90, 9)
    c, d = generate_records(90, 9)
    assert a.equals(c) and b.equals(d)
