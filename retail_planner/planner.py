"""Transactional proposal audit, approval replay, and Colab controls."""
from datetime import datetime,timezone
import hashlib
import pandas as pd
from .simulation import simulate,POLICIES,SCENARIOS

def save_proposals(db,run_id,policy,scenario,seed,proposals):
    with db:
        db.execute('INSERT OR IGNORE INTO experiment VALUES(?,?,?,?,?)',(run_id,policy,scenario,seed,'planner'))
        for row in proposals.itertuples():
            key=f'{run_id}|{row.day}|{row.location}|{row.sku}'
            pid=hashlib.sha256(key.encode()).hexdigest()[:24]
            db.execute('INSERT OR IGNORE INTO proposal(proposal_id,run_id,day,location,sku,qty,position,room,pack,moq) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (pid,run_id,int(row.day),row.location,row.sku,int(row.qty),float(row.position),int(row.room),int(row.pack),int(row.moq)))

def decide(db,proposal_id,action,quantity,actor,reason):
    if action not in ('approved','modified','rejected'):raise ValueError('Unknown action')
    if not actor.strip() or not reason.strip():raise ValueError('Planner name and rationale are required')
    row=db.execute('SELECT qty,room,pack,moq,status FROM proposal WHERE proposal_id=?',(proposal_id,)).fetchone()
    if row is None:raise ValueError('Proposal not found')
    recommended,room,pack,moq,status=row
    if status!='pending':raise ValueError('Proposal already has a decision')
    if action=='rejected':quantity=0
    if int(quantity)!=quantity or quantity<0:raise ValueError('Quantity must be a nonnegative integer')
    if action=='approved' and quantity!=recommended:raise ValueError('Choose modified to change quantity')
    if quantity>recommended:raise ValueError('Increases require batch replanning to reserve additional cash and capacity')
    if quantity and (quantity%pack or quantity<moq or quantity>room):raise ValueError('Quantity violates pack, MOQ or space')
    with db:
        updated=db.execute("UPDATE proposal SET status=? WHERE proposal_id=? AND status='pending'",(action,proposal_id))
        if updated.rowcount!=1:raise ValueError('Proposal changed; reload')
        db.execute('INSERT INTO decision VALUES(NULL,?,?,?,?,?,?)',(proposal_id,datetime.now(timezone.utc).isoformat(),action,int(quantity),actor.strip(),reason.strip()))
    return quantity

def decision_caps(db,run_id):
    rows=db.execute('SELECT p.day,p.location,p.sku,d.quantity FROM proposal p JOIN decision d USING(proposal_id) WHERE p.run_id=?',(run_id,)).fetchall()
    return {(day,location,sku):q for day,location,sku,q in rows}

def interface(data,c,forecast,observed,cal,best,raw,db):
    import ipywidgets as w
    from IPython.display import display,clear_output
    location=w.Dropdown(options=['CENTRAL',*data['markets']],description='Location')
    sku=w.Dropdown(options=data['skus'],description='Product')
    policy=w.Dropdown(options=POLICIES,value='forecast_optimized',description='Policy')
    scenario=w.Dropdown(options=SCENARIOS,description='Scenario')
    review=w.Button(description='Review recommendations',button_style='info')
    proposal=w.Dropdown(options=[],description='Order')
    quantity=w.IntText(value=0,description='Units')
    action=w.Dropdown(options=['approved','modified','rejected'],description='Action')
    actor=w.Text(value='Planner',description='Reviewed by');reason=w.Text(description='Rationale')
    save=w.Button(description='Record decision',button_style='success');replay=w.Button(description='Evaluate decisions')
    out=w.Output();state={}
    def refresh(_):
        with out:
            clear_output();params=best if policy.value=='forecast_optimized' else {}
            seed=c.seed+5000;run_id=f'planner-{policy.value}-{scenario.value}-{seed}'
            metrics,trace,orders,moves,pairs=simulate(data,c,forecast,observed,cal,policy.value,scenario.value,seed,record=True,**params)
            save_proposals(db,run_id,policy.value,scenario.value,seed,orders)
            state.clear();state.update(run_id=run_id,policy=policy.value,scenario=scenario.value,seed=seed,params=params,metrics=metrics,location=location.value,sku=sku.value)
            table=pd.read_sql_query("SELECT proposal_id,day,qty,status FROM proposal WHERE run_id=? AND location=? AND sku=? ORDER BY day",db,params=(run_id,location.value,sku.value))
            proposal.options=[(f'Day {r.day}: {r.qty} units ({r.status})',r.proposal_id) for r in table.itertuples()]
            if len(table):quantity.value=int(table.iloc[0].qty)
            display(raw[raw.scenario==scenario.value].groupby('policy')[['relevant_cost_gbp','fill_rate','lost_units','average_inventory_units']].mean())
            display(pairs[(pairs.sku==sku.value)&(pairs.market==location.value)])
            display(table)
            print('Observed sales replay; operating costs/network are assumptions. Approved increases require a new batch plan. Decisions persist in the experiment SQLite file.')
    def change_order(change):
        if proposal.value:
            row=db.execute('SELECT qty FROM proposal WHERE proposal_id=?',(proposal.value,)).fetchone()
            if row:quantity.value=int(row[0])
    def stale():return not state or any(state[k]!=v for k,v in [('location',location.value),('sku',sku.value),('policy',policy.value),('scenario',scenario.value)])
    def save_decision(_):
        with out:
            try:
                if stale():raise ValueError('Selection changed; review recommendations again')
                print('Recorded quantity:',decide(db,proposal.value,action.value,quantity.value,actor.value,reason.value))
            except ValueError as exc:print(str(exc))
    def evaluate_decisions(_):
        with out:
            if stale():print('Review the selected case first');return
            caps=decision_caps(db,state['run_id'])
            m=simulate(data,c,forecast,observed,cal,state['policy'],state['scenario'],state['seed'],**state['params'],overrides=caps)[0]
            display(pd.DataFrame([state['metrics'],m],index=['Automated plan','Decision replay'])[['relevant_cost_gbp','fill_rate','lost_units']])
            print('Replay caps selected orders by approved quantities. Other orders remain automated. No supplier transmission occurs.')
    proposal.observe(change_order,names='value');review.on_click(refresh);save.on_click(save_decision);replay.on_click(evaluate_decisions)
    display(w.VBox([w.HBox([location,sku]),w.HBox([policy,scenario]),review,proposal,w.HBox([quantity,action]),actor,reason,w.HBox([save,replay]),out]))
    return state
