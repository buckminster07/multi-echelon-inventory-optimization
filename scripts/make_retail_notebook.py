"""Generate the complete Colab workflow; core logic lives in tested modules."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
cells=[]
def md(s):cells.append(dict(cell_type='markdown',metadata={},source=s.splitlines(True)))
def code(s):cells.append(dict(cell_type='code',metadata={},source=s.splitlines(True),execution_count=None,outputs=[]))
md('''# Inventory Decision Intelligence — real-data retail planning

**Business assignment:** turn retail transactions into feasible replenishment decisions under uncertain demand, limited cash and warehouse capacity.

This is the complete project workflow: data acquisition → cleaning → SQL → segmentation → forecasting → uncertainty → network simulation → optimization → test results → planner → export.

**Data:** [UCI Online Retail II](https://doi.org/10.24432/C5CG6D), contributed by Daqing Chen, CC BY 4.0. About 1.07 million original transaction rows. Real sales and selling prices; proposed network and operating assumptions. Modeling excludes Customer IDs; extended EDA inspects only their aggregate completeness and exports no identifiers.

Start with `PROFILE='quick'`; use `'full'` for 150 products and six training-selected markets. Both are complete pipelines. The real retailer's actual inventory and stockouts are unknown. Reported inventory outcomes are model results, not verified company savings.''')
md('''## 1. Reproducible setup

The notebook uses the repository's tested modules. The source commit is printed so you can repeat the exact version. Set `REVISION` to a recorded commit for an exact source checkout. The first run downloads a 45 MB ZIP and reads the Excel workbook; subsequent runs reuse the cache.''')
code('''import sys,subprocess,os,time,json,hashlib,zipfile
from pathlib import Path
from datetime import datetime,timezone
REPOSITORY='https://github.com/buckminster07/multi-echelon-inventory-optimization.git'
REVISION='main'
if globals().get('LOCAL_REPO'):
    repo=Path(LOCAL_REPO).resolve()
else:
    repo=Path('/content/inventory-decision-intelligence')
    if not repo.exists():subprocess.check_call(['git','clone',REPOSITORY,str(repo)])
    subprocess.check_call(['git','-C',str(repo),'fetch','origin',REVISION])
    subprocess.check_call(['git','-C',str(repo),'checkout','--detach','FETCH_HEAD'])
    subprocess.check_call([sys.executable,'-m','pip','install','-q','-r',str(repo/'retail_requirements.txt')])
os.chdir(repo);sys.path.insert(0,str(repo))
print('Source commit:',subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
try:
    from google.colab import output
    output.enable_custom_widget_manager()
except ImportError:pass
import numpy as np,pandas as pd
from IPython.display import display,Image,HTML
from retail_planner.config import Config
PROFILE=globals().get('PROFILE','quick')
c=Config() if PROFILE=='full' else Config.quick()
started=time.perf_counter()
out=Path('outputs')/('colab-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
out.mkdir(parents=True,exist_ok=False)
display(pd.Series(c.dict()))''')
md('''## 2. Acquire and audit real transactions

Gross positive outbound sales form the demand proxy. Cancellations/returns are reported separately; they are not negative future demand. Exact repeated lines are retained because invoice-line identifiers are unavailable. Seven extreme bulk lines above 10,000 units were excluded in the published source audit. Inspect the current audit rather than assuming it is unchanged.

**Learn:** distinguish a fixed cleaning rule from a model tuned to the test set. **Exercise:** explain what would change if returned units were refurbished and restocked.''')
code('''from retail_planner.data import acquire,clean_transactions,prepare,sql_store
archive=acquire('data/cache')
transactions,audit=clean_transactions(archive,'data/cache')
display(pd.Series(audit))
display(transactions[['date','sku','quantity','price','market']].head())''')
md('''## 3. Select the cohort and integrate through SQL

Markets and products are ranked using only data through April 2011. The initial assortment is fixed before later evaluation. A zero-filled active pair means zero observed sales, not confirmed zero latent demand. SQLite keys separate products, locations and active pairs; the modeling array is reconstructed through SQL.

**Learn:** a country is a demand market; its proposed fulfillment hub is an operating assumption. **Exercise:** why would choosing the highest-selling products across the entire dataset leak future information?''')
code('''data=prepare(transactions,c)
db=sql_store(data,c,out/'planning.sqlite')
print('Markets:',data['markets'])
print('Products:',len(data['skus']),'Active pairs:',int(data['active'].sum()))
display(pd.read_sql_query("SELECT location,COUNT(*) AS stocked_products FROM assortment GROUP BY location",db))
display(pd.read_sql_query("SELECT a.location,a.sku,SUM(d.units) AS units FROM assortment a JOIN daily_sales d USING(location,sku) WHERE d.date<=? GROUP BY a.location,a.sku ORDER BY units DESC LIMIT 10",db,params=(c.train_end,)))
assert not db.execute('PRAGMA foreign_key_check').fetchall()
data['sku_master'].to_csv(out/'sku_master.csv',index=False)
data['pairs'].to_csv(out/'assortment.csv',index=False)''')
md('''## 4. Demand diagnostics and segmentation

ABC describes training sales-value concentration. CV is standard deviation divided by mean; XYZ segments that variability. ADI is elapsed days divided by nonzero-demand days. These descriptive segments do not automatically determine an optimal policy.

**Exercise:** compare a high-volume UK pair with an intermittent export pair. Explain why portfolio WAPE can hide poor small-market performance.''')
code('''import matplotlib.pyplot as plt
fig,axes=plt.subplots(1,2,figsize=(12,3.6))
axes[0].plot(data['dates'],data['y'].sum(axis=(1,2)));axes[0].set(title='Observed sales for the fixed cohort',ylabel='Units')
axes[1].hist(data['pairs'].query('active').zero_fraction,bins=15);axes[1].set(title='Zero-sales frequency across active pairs',xlabel='Fraction of days')
fig.tight_layout();plt.show()
display(data['sku_master'].head(12));display(data['pairs'].query('active').sort_values('adi',ascending=False).head(10))
del transactions''')
md('''## 4B. Extended EDA: evidence before modeling

The missing-value audit covers every original column and sheet. Customer IDs are inspected only for aggregate completeness and discarded. Behavioral diagnostics use the initial training window across eligible products and markets. They do not change the original cleaning rule or select models using later test outcomes.

Charts cover weekly/monthly patterns, within-product-market prices, market returns and extreme-order thresholds. The Friedman weekday test and effect size are exploratory; serial dependence and closure schedules limit interpretation. Monthly patterns do not establish annual seasonality with fewer than two complete training years.

**Learn:** a negative-quantity-to-gross-sales ratio is not a matched order-return probability; a transaction median price change is not causal price elasticity. Cutoff sensitivity here measures data changes, not inventory-policy performance.''')
code('''from retail_planner.eda import run_eda
eda_tables,seasonality_evidence=run_eda(archive,'data/cache',out/'eda',c.train_end)
display(eda_tables['missing_values'])
display(pd.Series(seasonality_evidence))
display(eda_tables['market_returns'].head(12))
display(eda_tables['cutoff_sensitivity'])
for chart in ['missing_values','seasonality','price_changes','market_returns','cutoff_sensitivity']:
    display(Image(filename=str(out/'eda'/(chart+'.png'))))
print('Read the accompanying interpretation:',out/'eda/README.md')''')
md('''## 5. Train and select forecasts

Compare seasonal naive, a 28-day mean, TSB for intermittent demand, and a global Poisson gradient booster. The booster learns across product–market pairs using categorical IDs, calendar fields and lagged demand statistics. Its recursive forecast uses predictions as future lags. May backtests select a method separately for each pair.

**Math:** TSB forecast = occurrence probability × positive-demand size. **Exercise:** if probability is 0.2 and positive size is ten, what is expected daily quantity?''')
code('''from retail_planner.forecast import train_booster,select_models,calibrate,forecast_window,end_index,summarize_forecasts,MODELS
model,training_rows=train_booster(data,c)
choice,selection=select_models(data,c,model)
display(selection.groupby('model')[['mae','rmse','bias','wape']].mean())
display(pd.Series([MODELS[i] for i in choice[data['active']]]).value_counts().rename('selected_pairs'))
print('Global-model training rows:',training_rows)''')
md('''## 6. Calibrate cumulative uncertainty

June–July data calibrates cumulative forecast errors. Demand over a lead/review interval is a sum, so its uncertainty is different from one-day error. The 5th and 95th empirical error quantiles form a 90% interval. Simultaneous errors across markets are aggregated for the DC buffer.

**Exercise:** explain why summing six separate 95th percentiles usually does not give the 95th percentile of total demand. Inspect held-out coverage later; calibration is not a guarantee under distribution shift.''')
code('''cal=calibrate(data,c,model,choice)
display(pd.DataFrame([dict(horizon=h,calibration_origins=len(v['errors']),average_upper_buffer=v['buffer'][data['active']].mean()) for h,v in cal.items()]))
windows={};forecast_rows=[];coverage_rows=[]
for name,left,right in [('tuning',c.calibration_end,c.tuning_end),('validation',c.tuning_end,c.validation_end),('test',c.validation_end,c.test_end)]:
    a=end_index(data,left);b=end_index(data,right)
    f,m,cov=forecast_window(data,c,model,choice,a,b,cal)
    windows[name]=(f,data['y'][a:b]);m['split']=name;cov['split']=name
    forecast_rows.append(m);coverage_rows.append(cov)
forecast_errors=pd.concat(forecast_rows,ignore_index=True)
coverage=pd.concat(coverage_rows,ignore_index=True)
print('Test forecast diagnostics are displayed after policy choices are frozen below.')''')
md('''## 7. Define policies and run an accounting check

Hub IP = on-hand + shipped inbound + queued requests. Compare fixed cover, daily (r,Q), weekly order-up-to and forecast-aware targets. Every request is constrained by packs, MOQ, item space, total space and rolling seven-day purchasing budget.

**Example:** ten units/day × ten protection days + 25 buffer gives target 125. IP 77 leaves a 48-unit gap, or eight six-unit packs. Limited shared budget may reduce that order.

The simulator receives supply, serves customers, records loss, reviews requests, allocates DC stock, places supplier orders and charges costs in that order.''')
code('''from retail_planner.simulation import simulate,POLICIES,SCENARIOS
check=simulate(data,c,*windows['tuning'],cal,'periodic','normal',c.seed+900,record=True)
display(pd.Series(check[0]));display(check[1].head());display(check[3].head())
assert check[0]['fulfilled_units']+check[0]['lost_units']==check[0]['demand_units']
assert (check[3].due>check[3].placed).all()
print('Daily conservation, pipeline, budget, pack and capacity checks are enforced inside the engine.')''')
md('''## 8. Optimize joint inventory targets

Eight hub/DC multiplier pairs are evaluated on August normal, spike and delay scenarios. Combined stress is excluded. First prefer candidates meeting 95% aggregate fill and 97% A-item fill in every tuning scenario; among them minimize cost. If no tested candidate qualifies, select the least service violation and report that fact.

**Learn:** finite-grid optimization does not prove a global optimum. **Exercise:** explain why the cheapest unconstrained policy may be unacceptable to the business.''')
code('''from retail_planner.evaluation import tune,evaluate,summarize,sensitivity
best,search=tune(data,c,*windows['tuning'],cal)
display(search.sort_values(['service_gap','mean_cost']))
print('Frozen settings:',best)
print('Any service-feasible candidate:',bool(search.service_feasible.any()))''')
md('''## 9. Validate and evaluate on untouched test months

September is diagnostic validation; October–November is the final test. All policies share the same demand and lead realizations for a seed. Paired cost differences compare them within seed. The intervals are conditional on observed sales and scenario assumptions, not uncertainty about all future markets.

**Exercise:** find a scenario where a policy improves service but raises cost. Explain the business choice rather than selecting one headline percentage.''')
code('''validation=evaluate(data,c,*windows['validation'],cal,best,seed_offset=3000,replications=5)
raw=evaluate(data,c,*windows['test'],cal,best)
summary,paired=summarize(raw)
display(summary);display(paired)
forecast_summary=summarize_forecasts(forecast_errors.query("split=='test'"))
display(forecast_summary)
display(coverage.query("split=='test'").groupby('horizon')[['covered','width']].mean())''')
md('''## 10. Sensitivity and operational drill-down

Vary budget, annual holding rate and unobserved-demand uplift with the chosen policy frozen. Cash budgets constrain decisions; lost-margin and holding assumptions affect tradeoffs. Historical sales may understate latent demand, so demand uplift is a stress bound rather than recovered truth.

**Exercise:** inspect an A-item with low service. Is the cause forecast error, upstream availability, MOQ, budget or capacity? Use shipments and proposal records to investigate.''')
code('''sens=sensitivity(data,c,*windows['test'],cal,best)
display(sens.groupby(['parameter','value'])[['relevant_cost_gbp','fill_rate','lost_units']].mean())
example=simulate(data,c,*windows['test'],cal,'forecast_optimized','normal',c.seed+5000,record=True,**best)
display(example[4].sort_values('fill_rate').head(12))''')
md('''## 11. Planner workflow and decision replay

Choose a product/location/policy/scenario, review the proposals, and approve, reduce or reject a quantity. A planner name and reason are required. Quantity increases need a new batch allocation because other products already reserve cash and capacity. Duplicate decisions are rejected transactionally.

**Evaluate decisions** reruns the same case with selected order quantities capped by your recorded decisions. Other orders remain automated. The audit is real SQLite persistence; supplier dispatch is simulated.''')
code('''from retail_planner.planner import interface,save_proposals
save_proposals(db,f'planner-forecast_optimized-normal-{c.seed+5000}','forecast_optimized','normal',c.seed+5000,example[2])
planner_state=interface(data,c,*windows['test'],cal,best,raw,db)''')
md('''## 12. Export results, audit and reproduction evidence

The export includes the database, individual trials, paired comparisons, forecasts, coverage, SKU-market service, proposals, shipments, assumptions, source/data checksums and a readable report. Rerun this cell after making additional planner decisions. Colab storage is temporary: download the ZIP.

**Explain the project:** use the business brief, methods and learning path in the repository. Clearly distinguish observed sales from assumed operations and modeled business outcomes.''')
code('''from retail_planner.pipeline import finalize
frames={'forecast_selection':selection,'forecast_errors':forecast_errors,'interval_coverage':coverage,'forecast_summary':forecast_summary,'tuning':search,'validation_trials':validation,'trials':raw,'policy_summary':summary,'paired_differences':paired,'sensitivity':sens,'daily_trace':example[1],'proposals':example[2],'shipments':example[3],'pair_service':example[4]}
db.commit()
pd.read_sql_query('SELECT * FROM decision',db).to_csv(out/'planner_decisions.csv',index=False)
manifest=finalize(data,c,best,frames,audit,training_rows,out,started)
display(Image(filename=str(out/'policy_comparison.png')))
import base64
report_html=(out/'report.html').read_text(encoding='utf-8')
for chart_path in out.rglob('*.png'):
    encoded=base64.b64encode(chart_path.read_bytes()).decode('ascii')
    report_html=report_html.replace('src="'+chart_path.relative_to(out).as_posix()+'"','src="data:image/png;base64,'+encoded+'"')
display(HTML(report_html))
archive_path=out.with_suffix('.zip')
with zipfile.ZipFile(archive_path,'w',zipfile.ZIP_DEFLATED) as z:
    for p in out.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(out))
print('Export:',archive_path)
try:
    from google.colab import files
    files.download(str(archive_path))
except ImportError:print('Local run: open the output ZIP directly.')''')
for i,cell in enumerate(cells):cell['id']=f'retail-{i:03d}'
nb=dict(nbformat=4,nbformat_minor=5,cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'},'colab':{'name':'02_real_retail_planning.ipynb'}})
(root/'notebooks/02_real_retail_planning.ipynb').write_text(json.dumps(nb,indent=2),encoding='utf-8')
print('Generated',len(cells),'notebook cells')
