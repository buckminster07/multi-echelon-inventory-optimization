"""Generate a portable visual report, Markdown evidence and decision charts."""

from html import escape
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

COLORS = {
    "independent": "#94a3b8",
    "normal_optimized": "#e5a446",
    "service_aware": "#0d9488",
}
LABELS = {
    "independent": "Independent",
    "normal_optimized": "Normal cost optimized",
    "service_aware": "Service aware",
}


def report(summary, targets, trace, manifest, out):
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    test = summary[summary.split == "test"]
    scenarios = list(test.scenario.unique())
    policies = list(COLORS)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), facecolor="#f8fafc")
    x = np.arange(len(scenarios))
    for i, p in enumerate(policies):
        g = test[test.policy == p].set_index("scenario").loc[scenarios]
        axes[0].bar(
            x + (i - 1) * 0.24, g.cost_per_day, 0.24, color=COLORS[p], label=LABELS[p]
        )
        axes[1].bar(
            x + (i - 1) * 0.24, g.worst_store_sku_fill * 100, 0.24, color=COLORS[p]
        )
    for ax in axes:
        ax.set_facecolor("#f8fafc")
        ax.set_xticks(x, [s.replace("_", "\n").title() for s in scenarios])
        ax.grid(axis="y", alpha=0.15)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Cost units / day")
    axes[0].legend(frameon=False, fontsize=9)
    axes[1].set_ylabel("Worst store–SKU immediate fill (%)")
    axes[1].set_ylim(0, 105)
    axes[1].axhline(
        manifest["config"]["target_fill_rate"] * 100, color="#334155", ls="--", lw=1
    )
    fig.suptitle(
        "Inventory decisions | cost, service and disruption risk",
        x=0.07,
        ha="left",
        weight="bold",
        fontsize=17,
    )
    fig.text(
        0.07,
        0.90,
        f"{manifest['data_source'].title()} · chronological test window · per-order lead-time uncertainty",
        color="#475569",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.87])
    fig.savefig(out / "policy_comparison.png", dpi=170)
    plt.close(fig)
    # Paired cost savings with uncertainty, all adverse outcomes retained.
    fig, ax = plt.subplots(figsize=(9, 4.5), facecolor="#f8fafc")
    ax.set_facecolor("#f8fafc")
    for i, p in enumerate(policies[1:]):
        g = test[test.policy == p].set_index("scenario").loc[scenarios]
        means = g.saving_per_day.to_numpy()
        errors = np.vstack(
            [means - g.ci95_low.to_numpy(), g.ci95_high.to_numpy() - means]
        )
        ax.errorbar(
            means,
            x + (i - 0.5) * 0.16,
            xerr=errors,
            fmt="o",
            capsize=4,
            color=COLORS[p],
            label=LABELS[p],
        )
    ax.axvline(0, color="#475569", lw=1)
    ax.set_yticks(x, [s.replace("_", " ").title() for s in scenarios])
    ax.invert_yaxis()
    ax.set_xlabel("Savings vs independent policy (cost units/day) · positive is better")
    ax.set_title(
        "Paired 95% intervals on test-window savings", loc="left", weight="bold"
    )
    ax.legend(frameon=False)
    ax.grid(axis="x", alpha=0.15)
    fig.tight_layout()
    fig.savefig(out / "savings_intervals.png", dpi=170)
    plt.close(fig)
    lines = [
        "# Measured results",
        "",
        f"Data: **{manifest['data_source']}**. No operational deployment is implied.",
        "",
        "| Split | Scenario | Policy | Cost/day | Fill | Worst store–SKU fill | Saving vs baseline | 95% CI: saving/day |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in summary.itertuples():
        lines.append(
            f"| {r.split} | {r.scenario} | {r.policy} | {r.cost_per_day:.2f} | {r.fill_rate:.2%} | {r.worst_store_sku_fill:.2%} | {r.saving_pct:.1f}% | [{r.ci95_low:.2f}, {r.ci95_high:.2f}] |"
        )
    lines += [
        "",
        "Intervals are paired over lead-time seeds, conditional on the fixed demand history.",
        "The 95% service target is a training selection constraint; held-out attainment is measured, not guaranteed.",
        "",
        "![Policy comparison](policy_comparison.png)",
        "",
        "![Savings intervals](savings_intervals.png)",
        "",
    ]
    (out / "RESULTS.md").write_text("\n".join(lines))
    rows = "".join(
        f"<tr><td>{escape(r.scenario.replace('_', ' '))}</td><td>{LABELS[r.policy]}</td><td>{r.cost_per_day:.2f}</td><td>{r.fill_rate:.2%}</td><td>{r.worst_store_sku_fill:.2%}</td><td>{r.saving_pct:+.1f}%</td></tr>"
        for r in test.itertuples()
    )
    service = test[test.policy == "service_aware"]
    met = int(
        (service.worst_store_sku_fill >= manifest["config"]["target_fill_rate"]).sum()
    )
    html = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Inventory Decision Intelligence | Results</title>
<style>body{margin:0;background:#f2f5f8;color:#142538;font:16px/1.6 system-ui,sans-serif}main{max-width:1120px;margin:48px auto;padding:0 24px}.eyebrow{color:#0d8078;font-weight:700;letter-spacing:.12em;text-transform:uppercase;font-size:13px}h1{font-size:clamp(30px,5vw,54px);line-height:1.08;max-width:900px;margin:18px 0}h2{font-size:25px}.lede{font-size:19px;color:#506175;max-width:800px}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:32px 0}.card,section{background:white;padding:24px;border-radius:14px;border:1px solid #e1e7ec;margin:16px 0}.card strong{display:block;font-size:32px;color:#0d8078}img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:12px;border-bottom:1px solid #e1e7ec}th{background:#f3f7fa}.scroll{overflow:auto}a{color:#086e69}footer{color:#596a79;margin:32px 0}@media(max-width:700px){.cards{grid-template-columns:1fr}.card{margin:0}main{margin-top:24px}}</style>
<main><div class="eyebrow">Operations research / Data analytics</div><h1>Inventory decisions that account for uncertainty.</h1><p class="lede">Compare independent planning, normal-cost optimization and service-aware planning using a transparent Python simulator and chronological demand windows.</p>"""
    html += f'<div class="cards"><div class="card"><strong>{len(targets.sku.unique())}</strong>SKUs modeled</div><div class="card"><strong>{len(targets.node_id.unique())}</strong>inventory locations</div><div class="card"><strong>{met}/{len(scenarios)}</strong>test scenarios meeting the service target with the service-aware policy</div></div>'
    html += (
        '<section><h2>Cost and customer service</h2><img src="policy_comparison.png" alt="Cost and worst store SKU fill by policy and scenario"></section><section><h2>Test-window evidence</h2><div class="scroll"><table><thead><tr><th>Scenario</th><th>Policy</th><th>Cost/day</th><th>Fill</th><th>Worst fill</th><th>Cost saving</th></tr></thead><tbody>'
        + rows
        + "</tbody></table></div></section>"
    )
    html += '<section><h2>How certain are the cost differences?</h2><img src="savings_intervals.png" alt="Paired confidence intervals of cost savings"><p>Positive values favor the optimized policy. Intervals account for simulated lead-time randomness, conditional on the observed demand path; they exclude demand-model error.</p></section>'
    html += f'<section><h2>Scope and provenance</h2><p>Source: {escape(manifest["data_source"])}. Parameters and policies use training data only. Validation and test results are reported without retuning. A combined demand-and-delay scenario is excluded from policy search.</p><p>Model: one product per simulation, multiple independent SKUs, warehouses and stores, FIFO dispatch, customer backorders, random per-order transport times, and unlimited external supply. No production deployment or global optimality is claimed.</p><p><a href="summary.csv">Summary CSV</a> · <a href="trials.csv">All SKU trials</a> · <a href="manifest.json">Run manifest</a></p></section><footer>Inventory Decision Intelligence · Reproducible research portfolio</footer></main></html>'
    (out / "report.html").write_text(html)
