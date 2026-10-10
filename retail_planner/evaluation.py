import numpy as np
import pandas as pd
from scipy.stats import t as student_t
from .simulation import simulate,POLICIES,SCENARIOS

def tune(data,c,forecast,observed,cal):
    rows=[]
    for risk in (.5,1.,1.5,2.):
        for dc_scale in (.8,1.2):
            outcomes=[]
            for scenario in SCENARIOS[:-1]:
                for k in range(c.tune_replications):
                    outcomes.append(simulate(data,c,forecast,observed,cal,'forecast_optimized',scenario,c.seed+1000+k,risk,dc_scale)[0])
            frame=pd.DataFrame(outcomes);means=frame.groupby('scenario')[['fill_rate','a_fill_rate']].mean()
            gap=float(np.maximum(0,c.service_target-means.fill_rate).sum()+np.maximum(0,.97-means.a_fill_rate).sum())
            rows.append(dict(risk=risk,dc_scale=dc_scale,mean_cost=frame.relevant_cost_gbp.mean(),worst_scenario_fill=means.fill_rate.min(),worst_scenario_a_fill=means.a_fill_rate.min(),service_gap=gap,service_feasible=gap<1e-9))
    table=pd.DataFrame(rows)
    feasible=table[table.service_feasible]
    best=feasible.sort_values('mean_cost').iloc[0] if len(feasible) else table.sort_values(['service_gap','mean_cost']).iloc[0]
    return {'risk':float(best.risk),'dc_scale':float(best.dc_scale)},table

def evaluate(data,c,forecast,observed,cal,best,seed_offset=2000,replications=None):
    rows=[]
    for scenario in SCENARIOS:
        for k in range(replications or c.replications):
            for policy in POLICIES:
                rows.append(simulate(data,c,forecast,observed,cal,policy,scenario,c.seed+seed_offset+k,**(best if policy=='forecast_optimized' else {}))[0])
    return pd.DataFrame(rows)

def summarize(raw):
    rows=[]
    for (scenario,policy),g in raw.groupby(['scenario','policy']):
        row=dict(scenario=scenario,policy=policy,replications=len(g))
        for name in ['relevant_cost_gbp','fill_rate','a_fill_rate','lost_units','average_inventory_units','worst_material_pair_fill']:
            v=g[name].dropna();row[name]=v.mean()
            row[name+'_ci_half']=student_t.ppf(.975,len(v)-1)*v.std(ddof=1)/np.sqrt(len(v)) if len(v)>1 else np.nan
        rows.append(row)
    paired=[]
    for scenario,g in raw.groupby('scenario'):
        pivot=g.pivot(index='seed',columns='policy',values='relevant_cost_gbp')
        for comparator in ('fixed_cover','rq','periodic'):
            delta=pivot.forecast_optimized-pivot[comparator]
            half=student_t.ppf(.975,len(delta)-1)*delta.std(ddof=1)/np.sqrt(len(delta))
            paired.append(dict(scenario=scenario,comparator=comparator,adaptive_minus_comparator=delta.mean(),ci_low=delta.mean()-half,ci_high=delta.mean()+half))
    return pd.DataFrame(rows),pd.DataFrame(paired)

def sensitivity(data,c,forecast,observed,cal,best):
    from dataclasses import replace
    rows=[]
    for parameter,values in [('budget_days',(2.,4.,8.)),('annual_holding_rate',(.15,.25,.4)),('unobserved_demand_uplift',(0.,.1,.25))]:
        for value in values:
            setting=replace(c,**{parameter:value}) if parameter!='unobserved_demand_uplift' else c
            demand=np.rint(observed*(1+value)) if parameter=='unobserved_demand_uplift' else observed
            for k in range(3):
                m=simulate(data,setting,forecast,demand,cal,'forecast_optimized','combined',c.seed+4000+k,**best)[0]
                rows.append(dict(parameter=parameter,value=value,**m))
    return pd.DataFrame(rows)
