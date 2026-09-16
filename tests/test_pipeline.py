import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from inventory_lab.data import generate, prepare, validate
from inventory_lab.planning import apply_scenario
from inventory_lab.cli import run


def config():
    c = json.loads(Path("configs/demo.json").read_text())
    c.update(
        days=120,
        train_days=70,
        validation_days=25,
        warmup=5,
        search_days=10,
        search_seeds=[1],
        evaluation_seeds=[11, 12],
        grid_multipliers=[1, 2],
    )
    return c


def test_sql_statistics_and_temporal_cutoff(tmp_path):
    c = config()
    tables = generate(120)
    p, l, _, splits = prepare(tables, tmp_path, c)
    cutoff = splits["validation"][0]
    for r in p.itertuples():
        d = tables["demand"]
        values = d[
            (d.node_id == r.node_id) & (d.sku == r.sku) & (d.date < cutoff)
        ].quantity
        assert r.mean_demand == pytest.approx(values.mean())
        assert r.variance_demand == pytest.approx(values.var(ddof=1))
    tables["demand"].loc[tables["demand"].date >= cutoff, "quantity"] = 999
    tables["receipts"].loc[tables["receipts"].receipt_date >= cutoff, "quantity"] = 999
    p2, l2, _, _ = prepare(tables, tmp_path / "second", c)
    pd.testing.assert_frame_equal(p, p2)
    pd.testing.assert_frame_equal(l, l2)


def test_missing_dates_and_wrong_network_rejected():
    tables = generate(120)
    tables["demand"] = tables["demand"].iloc[1:]
    with pytest.raises(ValueError, match="daily"):
        validate(tables)
    tables = generate(120)
    tables["nodes"].loc[2, "parent_id"] = 999
    with pytest.raises(ValueError, match="reference"):
        validate(tables)


def test_scenario_does_not_modify_original_paths():
    x = {2: np.ones(20, dtype=int)}
    y = apply_scenario(x, {"spike_multiplier": 2}, 4)
    assert x[2].sum() == 20 and y[2][9:13].tolist() == [2] * 4
    assert y[2][:4].tolist() == [1] * 4


def test_end_to_end_with_all_outputs(tmp_path):
    c = config()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(c))
    out = tmp_path / "output"
    s = run(path, out)
    assert (
        len(s) == 24 and s.fill_rate.between(0, 1).all() and s.cost_per_day.ge(0).all()
    )
    assert all(
        (out / f).exists()
        for f in [
            "manifest.json",
            "report.html",
            "policy_comparison.png",
            "trials.csv",
            "store_trials.csv",
            "targets.csv",
        ]
    )
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["full_material_balance_checks"] is True
    scores = pd.read_csv(out / "search_results.csv")
    for sku, choice in manifest["selection"].items():
        g = scores[scores.sku == sku]
        assert g[g.candidate == choice["normal_candidate"]].iloc[
            0
        ].normal_cost == pytest.approx(g.normal_cost.min())


def test_overlapping_seeds_fail_before_execution(tmp_path):
    c = config()
    c["evaluation_seeds"] = [1, 2]
    p = tmp_path / "c.json"
    p.write_text(json.dumps(c))
    with pytest.raises(ValueError, match="disjoint"):
        run(p, tmp_path / "out")
