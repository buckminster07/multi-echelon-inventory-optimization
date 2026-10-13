from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,platform,time
import numpy as np
import pandas as pd
from .data import acquire,clean_transactions,prepare,sql_store
from .forecast import train_booster,select_models,calibrate,forecast_window,end_index,summarize_forecasts
from .evaluation import tune,evaluate,summarize,sensitivity
from .simulation import simulate
from .planner import save_proposals

def run(c,output,cache='data/cache',progress=print):
    started=time.perf_counter();out=Path(output);out.mkdir(parents=True,exist_ok=True)
    if (out/'planning.sqlite').exists():raise FileExistsError('Choose a new output directory to preserve its decisions.')
    progress('1/8 Download/cache and clean UCI transactions')
    archive=acquire(cache);transactions,audit=clean_transactions(archive,cache)
    from .eda import run_eda
    progress('Extended EDA: missingness, seasonality, prices, returns and cutoff sensitivity')
    run_eda(archive,cache,out/'eda',c.train_end)
    data=prepare(transactions,c);del transactions
    progress(f"2/8 SQL integration: {len(data['skus'])} SKUs, {len(data['markets'])} markets, {data['active'].sum()} active pairs")
    db=sql_store(data,c,out/'planning.sqlite')
    data['sku_master'].to_csv(out/'sku_master.csv',index=False);data['pairs'].to_csv(out/'assortment.csv',index=False)
    progress('3/8 Train global boosting and select forecast methods chronologically')
    model,training_rows=train_booster(data,c);choice,selection=select_models(data,c,model)
    progress('4/8 Calibrate cumulative demand errors on later observations')
    cal=calibrate(data,c,model,choice)
    windows={};metrics=[];coverage=[]
    for name,left,right in [('tuning',c.calibration_end,c.tuning_end),('validation',c.tuning_end,c.validation_end),('test',c.validation_end,c.test_end)]:
        a=end_index(data,left);b=end_index(data,right)
        f,m,cov=forecast_window(data,c,model,choice,a,b,cal);m['split']=name;cov['split']=name
        windows[name]=(f,data['y'][a:b]);metrics.append(m);coverage.append(cov)
    progress('5/8 Joint target tuning with shared budget and capacity constraints')
    best,search=tune(data,c,*windows['tuning'],cal)
    progress('6/8 Validation and untouched test-scenario evaluation')
    validation=evaluate(data,c,*windows['validation'],cal,best,seed_offset=3000,replications=5)
    raw=evaluate(data,c,*windows['test'],cal,best)
    summary,paired=summarize(raw)
    progress('7/8 Sensitivity, planner proposal log and reports')
    sens=sensitivity(data,c,*windows['test'],cal,best)
    example=simulate(data,c,*windows['test'],cal,'forecast_optimized','normal',c.seed+5000,record=True,**best)
    save_proposals(db,f'planner-forecast_optimized-normal-{c.seed+5000}','forecast_optimized','normal',c.seed+5000,example[2])
    frames={'forecast_selection':selection,'forecast_errors':pd.concat(metrics,ignore_index=True),'interval_coverage':pd.concat(coverage,ignore_index=True),'tuning':search,'validation_trials':validation,'trials':raw,'policy_summary':summary,'paired_differences':paired,'sensitivity':sens,'daily_trace':example[1],'proposals':example[2],'shipments':example[3],'pair_service':example[4]}
    frames['forecast_summary']=summarize_forecasts(frames['forecast_errors'].query("split=='test'"))
    manifest=finalize(data,c,best,frames,audit,training_rows,out,started)
    progress(f'8/8 Complete: {out}; {manifest["runtime_seconds"]:.1f} seconds')
    return dict(data=data,config=c,model=model,choice=choice,calibration=cal,best=best,windows=windows,raw=raw,summary=summary,db=db,output=out,manifest=manifest)

def finalize(data,c,best,frames,audit,training_rows,out,started):
    out=Path(out)
    for name,frame in frames.items():frame.to_csv(out/(name+'.csv'),index=False)
    (out/'cleaning_audit.json').write_text(json.dumps(audit,indent=2))
    import sklearn,scipy
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'config':c.dict(),'best':best,'dataset':audit,'markets':data['markets'],'skus':len(data['skus']),'active_pairs':int(data['active'].sum()),'training_rows':training_rows,'selection_rule':data['selection_rule'],
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scikit_learn':sklearn.__version__,'scipy':scipy.__version__},
        'runtime_seconds':time.perf_counter()-started,'test_seed_start':c.seed+2000,'test_replications':c.replications,
        'interpretation':'Real historical gross sales proxy; hypothetical fulfillment network, lead times, budgets and costs. Intervals conditional on this history and scenario mechanisms.'}
    manifest['files_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.csv')}
    manifest['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    from .report import build_report
    build_report(out)
    return manifest
