"""One-command reproducible experiment runner."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
from .data import generate_records, build_database, estimate_parameters
from .model import independent_targets
from .experiment import optimize, evaluate, paired_summary
from .report import write_report


def run(config_path, output, data_dir=None):
    config = json.loads(Path(config_path).read_text())
    if set(config["optimization_seeds"]) & set(config["evaluation_seeds"]):
        raise ValueError("Optimization and evaluation seeds must be disjoint.")
    if len(config["evaluation_seeds"]) < 2:
        raise ValueError("At least two evaluation seeds are needed for confidence intervals.")
    if any(len(config[k]) != len(set(config[k])) for k in ["optimization_seeds", "evaluation_seeds"]):
        raise ValueError("Seeds must be unique within each split.")
    if config["warmup"] < 0 or min(config["optimization_periods"], config["evaluation_periods"]) < 1:
        raise ValueError("Invalid simulation horizon.")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if data_dir:
        import pandas as pd
        demand = pd.read_csv(Path(data_dir) / "demand.csv")
        receipts = pd.read_csv(Path(data_dir) / "replenishment.csv")
        source = "user-supplied records; synthetic status is user-defined"
    else:
        demand, receipts = generate_records(config["training_days"], config["data_seed"])
        source = "synthetic demonstration data"
    demand.to_csv(output / "demand.csv", index=False)
    receipts.to_csv(output / "replenishment.csv", index=False)
    build_database(demand, receipts, output / "inventory.sqlite")
    profile, leads, samples = estimate_parameters(output / "inventory.sqlite")
    profile.to_csv(output / "demand_profile.csv", index=False)
    leads.to_csv(output / "lead_time_profile.csv")
    baseline = independent_targets(profile, leads, config)
    print("SQL profiles ready. Searching joint inventory targets…", flush=True)
    best, training_cost, candidates, grid = optimize(baseline, leads, samples, config)
    policies = {"independent": baseline, "coordinated": best}
    candidates.to_csv(output / "search_results.csv", index=False)
    print(f"Evaluating {len(config['evaluation_seeds'])} fresh seeds across {len(config['scenarios'])} scenarios…", flush=True)
    trials = evaluate(policies, leads, samples, config)
    summary = paired_summary(trials)
    trials.to_csv(output / "trials.csv", index=False)
    summary.to_csv(output / "summary.csv", index=False)
    manifest = {"data_source": source, "config": config, "policies": policies,
                "training_cost_per_day": training_cost, "search_grid": grid,
                "selected_at_grid_boundary": [n for n in best if best[n] in (min(grid[n]), max(grid[n]))],
                "python": platform.python_version(),
                "packages": {p: importlib.metadata.version(p) for p in ["stockpyl", "numpy", "pandas", "scipy", "matplotlib"]},
                "input_sha256": {f: hashlib.sha256((output / f).read_bytes()).hexdigest() for f in ["demand.csv", "replenishment.csv"]}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(summary, policies, output, synthetic=data_dir is None)
    if data_dir:
        report = output / "RESULTS.md"
        report.write_text(report.read_text().replace("All inputs are synthetic;", "Inputs are user-supplied;"))
    print(summary.to_string(index=False))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/demo.json")
    parser.add_argument("--output", default="outputs/demo")
    parser.add_argument("--data-dir", help="Folder with demand.csv and replenishment.csv; see docs/DATA.md")
    args = parser.parse_args()
    run(args.config, args.output, args.data_dir)

if __name__ == "__main__":
    main()
