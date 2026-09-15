import numpy as np
import pandas as pd
import pytest
from inventory_lab.model import simulate_policy, demand_paths
from inventory_lab.experiment import paired_summary, evaluate
from stockpyl.supply_chain_network import single_stage_system
from stockpyl.sim import simulation


def test_stockpyl_documented_deterministic_inventory_path():
    network = single_stage_system(demand_type="D", demand_list=[12, 6, 12, 14],
                                  policy_type="BS", base_stock_level=13,
                                  initial_inventory_level=13, shipment_lead_time=1)
    simulation(network, 4, progress_bar=False, consistency_checks="E")
    levels = [sum(s.inventory_level.values()) for s in network.nodes[0].state_vars[:4]]
    assert levels == [1, 7, 1, -1]


def test_zero_stock_conserves_unfilled_demand():
    leads = pd.DataFrame({"model_lead_time": [2, 1, 1]}, index=[0, 1, 2])
    config = {"warmup": 0, "holding_cost": [1, 1, 1], "stockout_penalty": [0, 10, 10]}
    paths = {1: [5] * 10, 2: [7] * 10}
    metrics = simulate_policy({0: 0, 1: 0, 2: 0}, leads, config, paths)
    assert metrics["fill_rate"] == 0
    assert metrics["shortage_units"] == metrics["demand_units"] == 120
    assert metrics["cost_per_day"] == pytest.approx(metrics["holding_per_day"] + metrics["penalty_per_day"])


def test_demand_stress_only_changes_defined_window():
    samples = {1: np.array([5]), 2: np.array([8])}
    normal = demand_paths(samples, 24, 10, 1, 4)
    stress = demand_paths(samples, 24, 10, 2, 4)
    assert stress[1][:4] == normal[1][:4]
    assert stress[1][4:9] == [10] * 5
    assert stress[1][9:] == normal[1][9:]


def test_paired_interval_and_sign():
    rows = [{"scenario": "normal", "seed": s, "policy": p, "cost_per_day": c,
             "fill_rate": 0.9} for s in range(5) for p, c in [("independent", 100), ("coordinated", 80)]]
    summary = paired_summary(pd.DataFrame(rows)).iloc[0]
    assert summary.saving_pct == 20
    assert summary.saving_ci95_low == summary.saving_ci95_high == 20


def test_leakage_guard():
    with pytest.raises(ValueError, match="disjoint"):
        evaluate({}, None, {}, {"optimization_seeds": [1], "evaluation_seeds": [1]})
