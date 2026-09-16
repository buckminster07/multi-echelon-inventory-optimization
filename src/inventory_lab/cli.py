"""One-command SQL → planning → validation → test → report pipeline."""

import argparse, json, hashlib, platform, importlib.metadata
from pathlib import Path
import pandas as pd
from .data import generate, prepare
from .planning import network_for, baseline_targets, search
from .evaluation import evaluate, summarize
from .report import report


def run(config_path="configs/demo.json", output="outputs/full", data_dir=None):
    cfg = json.loads(Path(config_path).read_text())
    if set(cfg["search_seeds"]) & set(cfg["evaluation_seeds"]):
        raise ValueError("Search/evaluation seeds must be disjoint")
    if len(cfg["evaluation_seeds"]) < 2 or not cfg["search_seeds"]:
        raise ValueError("Need search seeds and >=2 evaluation seeds")
    for k in ["search_seeds", "evaluation_seeds"]:
        if len(set(cfg[k])) != len(cfg[k]):
            raise ValueError("Duplicate seeds")
    if not 0 < cfg["target_fill_rate"] <= 1:
        raise ValueError("Invalid service target")
    if (
        not cfg["grid_multipliers"]
        or 1 not in cfg["grid_multipliers"]
        or any(m <= 0 for m in cfg["grid_multipliers"])
    ):
        raise ValueError("Positive grid must include baseline 1.0")
    if cfg["warmup"] < 0 or cfg["search_days"] < 1:
        raise ValueError("Invalid horizon")
    if "normal" not in cfg["search_scenarios"] or not set(
        cfg["search_scenarios"]
    ) <= set(cfg["scenarios"]):
        raise ValueError("Invalid search scenarios")
    for s in cfg["scenarios"].values():
        if (
            s["spike_multiplier"] <= 0
            or s["supplier_delay"] < 0
            or int(s["supplier_delay"]) != s["supplier_delay"]
        ):
            raise ValueError("Invalid scenario")
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    tables = (
        {
            n: pd.read_csv(Path(data_dir) / f"{n}.csv")
            for n in ["nodes", "skus", "demand", "receipts"]
        }
        if data_dir
        else generate(cfg["days"], cfg["data_seed"])
    )
    profile, leads, series, splits = prepare(tables, out, cfg)
    trials = []
    store_rows = []
    traces = []
    searches = []
    selected = {}
    target_rows = []
    for sku in tables["skus"].sku:
        print(f"{sku}: optimizing targets from training data", flush=True)
        net = network_for(tables, leads, sku)
        baseline = baseline_targets(net, profile, sku)
        policies, scores, selection = search(net, baseline, series[sku]["train"], cfg)
        selected[sku] = selection
        searches.extend({"sku": sku, **r} for r in scores)
        target_rows.extend(
            {"sku": sku, "policy": policy, "node_id": n, "target_units": v}
            for policy, targets in policies.items()
            for n, v in targets.items()
        )
        for split in ["validation", "test"]:
            print(f"{sku}: {split} evaluation", flush=True)
            a, b, c = evaluate(net, policies, series[sku], cfg, split, sku)
            trials += a
            store_rows += b
            traces += c
    trials = pd.DataFrame(trials)
    stores = pd.DataFrame(store_rows)
    summary, aggregate = summarize(trials, stores)
    frames = {
        "trials": trials,
        "store_trials": stores,
        "daily_trace": pd.DataFrame(traces),
        "search_results": pd.DataFrame(searches),
        "targets": pd.DataFrame(target_rows),
        "summary": summary,
        "aggregate_trials": aggregate,
    }
    for name, frame in frames.items():
        frame.to_csv(out / f"{name}.csv", index=False)
    manifest = {
        "data_source": "synthetic demonstration"
        if not data_dir
        else "user-supplied CSVs",
        "config": cfg,
        "selection": selected,
        "split_dates": {
            k: {"start": v[0], "end": v[-1], "days": len(v)} for k, v in splits.items()
        },
        "python": platform.python_version(),
        "versions": {
            p: importlib.metadata.version(p)
            for p in ["numpy", "pandas", "scipy", "matplotlib"]
        },
        "input_sha256": {
            n: hashlib.sha256((out / f"{n}.csv").read_bytes()).hexdigest()
            for n in tables
        },
        "full_material_balance_checks": True,
        "simulator": "from-scratch periodic-review with sampled per-order transport times",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    report(summary, frames["targets"], frames["daily_trace"], manifest, out)
    print(
        summary[summary.split == "test"][
            ["scenario", "policy", "cost_per_day", "fill_rate", "worst_store_sku_fill"]
        ].to_string(index=False)
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/demo.json")
    parser.add_argument("--output", default="outputs/full")
    parser.add_argument("--data-dir")
    args = parser.parse_args()
    run(args.config, args.output, args.data_dir)


if __name__ == "__main__":
    main()
