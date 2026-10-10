from pathlib import Path
import json,html
import numpy as np
import pandas as pd

def build_report(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=Path(output);summary=pd.read_csv(out/'policy_summary.csv');manifest=json.loads((out/'manifest.json').read_text())
    forecast=pd.read_csv(out/'forecast_summary.csv')
    palette={'fixed_cover':'#8696a0','rq':'#d19c37','periodic':'#318a99','forecast_optimized':'#7056b4'}
    fig,axes=plt.subplots(1,2,figsize=(12,4.7))
    for p,g in summary.groupby('policy'):
        axes[0].errorbar(g.fill_rate*100,g.relevant_cost_gbp/1000,xerr=g.fill_rate_ci_half*100,
                        yerr=g.relevant_cost_gbp_ci_half/1000,fmt='o',label=p,color=palette[p],capsize=2)
    axes[0].set(xlabel='Immediate unit fill (%)',ylabel='Modeled relevant cost (GBP thousands)',title='Cost and service across four scenarios')
    axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
    for p in ('periodic','forecast_optimized'):
        g=summary[summary.policy==p].set_index('scenario').loc[['normal','demand_spike','supplier_delay','combined']]
        axes[1].plot(range(4),g.fill_rate*100,'o-',label=p,color=palette[p])
    axes[1].set_xticks(range(4),['Normal','Spike','Delay','Combined']);axes[1].axhline(95,color='#444',linestyle='--',label='Proposed target')
    axes[1].set(ylabel='Immediate unit fill (%)',title='Service under disruptions');axes[1].legend(fontsize=8);axes[1].grid(alpha=.2)
    fig.suptitle(f"UCI retail sales replay: {manifest['skus']} products / {len(manifest['markets'])} markets / {manifest['test_replications']} replications",fontsize=11)
    fig.tight_layout();fig.savefig(out/'policy_comparison.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,3.8));ax.barh(forecast.model,forecast.wape*100,color='#318a99')
    ax.set(xlabel='Test WAPE (%)',title='Forecast methods on untouched test dates');fig.tight_layout();fig.savefig(out/'forecast_comparison.png',dpi=150);plt.close(fig)
    cols=['scenario','policy','relevant_cost_gbp','fill_rate','a_fill_rate','lost_units','average_inventory_units']
    shown=summary[cols].copy();shown[['fill_rate','a_fill_rate']]*=100
    lines=['# Real-data retail planning: executed results','',
      f"Dataset: UCI Online Retail II. Cohort: {manifest['skus']} SKUs, {len(manifest['markets'])} markets, {manifest['active_pairs']} active pairs. Test: 1 October–30 November 2011. {manifest['test_replications']} replications per policy and scenario.",'',
      'Sales are observed transactions. Service, shortages, network movements and operating costs are modeled counterfactual outcomes. They are not the retailer’s measured historical inventory performance.','',
      '| Scenario | Policy | Relevant cost GBP | Fill % | A-item fill % | Lost units | Average inventory |','|---|---|---:|---:|---:|---:|---:|']
    for r in shown.itertuples(index=False):lines.append(f'| {r.scenario} | {r.policy} | {r.relevant_cost_gbp:,.0f} | {r.fill_rate:.2f} | {r.a_fill_rate:.2f} | {r.lost_units:,.0f} | {r.average_inventory_units:,.0f} |')
    lines+=['','![Cost and service](policy_comparison.png)','','![Forecast comparison](forecast_comparison.png)','',
      'Read paired_differences.csv for adaptive-versus-each-comparator confidence intervals; negative differences favor adaptive. The intervals describe lead-time and selected disruption randomness conditional on the observed sales history. They do not quantify all uncertainty in unobserved demand or assumed costs.','',
      'The optimizer selects the cheapest service-feasible tested combination. If no candidate satisfies the proposed aggregate/A-item constraints on tuning scenarios, it selects the least violating candidate and reports the gap in tuning.csv. Combined disruption is excluded from tuning.','',
      'Procurement cash, terminal inventory value, constrained orders, per-pair service and sensitivity are separate exports. Cost excludes procurement capital to avoid finite-horizon purchase artifacts; lost-margin cost is an explicit assumption. No usability participants or production deployment are claimed.']
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    body=shown.to_html(index=False,float_format=lambda x:f'{x:,.2f}',classes='metrics')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Retail replenishment decision brief</title><style>body{font:16px system-ui;color:#193441;background:#f3f6f6;max-width:1150px;margin:40px auto;padding:0 24px}h1{font-size:38px;letter-spacing:-1px}p{line-height:1.6}section{background:white;border:1px solid #dce5e5;border-radius:12px;padding:24px;margin:22px 0}img{max-width:100%}table{border-collapse:collapse;font-size:13px;width:100%}td,th{padding:9px;border-bottom:1px solid #e3e9eb;text-align:right}th{background:#ecf4f4}a{color:#14748c}.scroll{overflow:auto}.tag{color:#14748c;font-weight:700}</style><body><p class="tag">INVENTORY DECISION INTELLIGENCE · REAL-DATA CASE STUDY</p><h1>Where should stock go—and when should we reorder?</h1><p>Demand forecasting, constrained multi-echelon replenishment and planner decisions using UCI Online Retail II.</p>'''
    page+=f"<section><b>{manifest['skus']} products · {len(manifest['markets'])} markets · {manifest['active_pairs']} active pairs</b><p>Observed sales from {html.escape(', '.join(manifest['markets']))}. The proposed central warehouse and market hubs, supplier lead times, budgets and costs are planning assumptions.</p></section>"
    page+='<section><h2>Cost–service tradeoffs</h2><img src="policy_comparison.png" alt="Cost and fill rates across policies and scenarios"><div class="scroll">'+body+'</div></section>'
    page+='<section><h2>Forecast benchmark</h2><img src="forecast_comparison.png" alt="Forecast WAPE by method"><p>Chronological model selection, calibration, tuning and test windows are separate. A machine-learning model is a challenger: the data decides whether it earns use.</p></section>'
    page+='<section><h2>Review the evidence</h2><p><a href="trials.csv">Individual trials</a> · <a href="paired_differences.csv">Paired differences</a> · <a href="pair_service.csv">Product-market service</a> · <a href="sensitivity.csv">Sensitivity</a> · <a href="manifest.json">Reproduction manifest</a></p><p>These are modeled decisions against historical sales, not verified company savings. See README and the business brief for assumptions and tradeoffs.</p></section></body></html>'
    (out/'report.html').write_text(page,encoding='utf-8')
