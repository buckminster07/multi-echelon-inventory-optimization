import json
import pandas as pd
from inventory_lab.cli import run


def test_small_end_to_end_experiment(tmp_path):
    config = {"data_seed": 1, "training_days": 60,
              "optimization_seeds": [2], "evaluation_seeds": [3, 4],
              "warmup": 5, "optimization_periods": 10, "evaluation_periods": 12,
              "grid_multipliers": [0.8, 1.0], "holding_cost": [0.3, 1, 1],
              "stockout_penalty": [0, 12, 12],
              "scenarios": {"normal": {"demand_multiplier": 1, "supplier_delay": 0}}}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    out = tmp_path / "results"
    result = run(path, out)
    trials = pd.read_csv(out / "trials.csv")
    assert len(trials) == 4
    assert trials.fill_rate.between(0, 1).all()
    assert len(result) == 1
    assert (out / "policy_comparison.png").is_file()
    manifest = json.loads((out / "manifest.json").read_text())
    candidates = pd.read_csv(out / "search_results.csv")
    assert manifest["training_cost_per_day"] == candidates.training_cost_per_day.min()
