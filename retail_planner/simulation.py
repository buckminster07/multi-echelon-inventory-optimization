"""Capacity/budget-constrained central DC and market-hub lost-sales simulator."""
import time
import numpy as np
import pandas as pd

POLICIES=('fixed_cover','rq','periodic','forecast_optimized')
SCENARIOS=('normal','demand_spike','supplier_delay','combined')

def constrained_orders(raw,position,item_capacity,total_room,budget,cost,priority,pack,moq):
    """Deterministic priority heuristic; jointly enforce packs, room and cash budget."""
    room=np.maximum(0,item_capacity-position)
    wanted=np.where(raw>0,np.ceil(np.maximum(raw,moq)/pack)*pack,0)
    wanted=np.minimum(wanted,np.floor(room/pack)*pack).astype(int)
    out=np.zeros_like(wanted);remaining=float(max(0,total_room));cash=float(max(0,budget))
    for i in np.argsort(-priority,kind='stable'):
        q=int(min(wanted[i],np.floor(remaining/pack)*pack,np.floor(cash/max(cost[i],.001)/pack)*pack))
        if q<moq:continue
        out[i]=q;remaining-=q;cash-=q*cost[i]
    assert out.sum()<=total_room+1e-6 and np.dot(out,cost)<=budget+1e-6
    return out

def scenario_path(observed,scenario,seed):
    demand=np.rint(observed).astype(int).copy();rng=np.random.default_rng(seed)
    H,J,N=demand.shape
    if scenario in ('demand_spike','combined'):
        # Same random SKU shock across policies, supplier draws use a separate stream.
        chosen=rng.random(N)<.3;start=H//3;end=min(H,start+14)
        demand[start:end,:,chosen]*=2
    return demand

def simulate(data,c,forecast,observed,cal,policy,scenario,seed,risk=1.,dc_scale=1.,record=False,overrides=None):
    started=time.perf_counter();D=scenario_path(observed,scenario,seed);H,J,N=D.shape
    active=data['active'];mu=data['mu'];prices=data['prices'];cost=prices*c.acquisition_fraction
    margin=prices-cost;holding=cost*c.annual_holding_rate/365
    item_cap=np.maximum(c.moq,np.ceil(mu*c.store_capacity_days)).astype(int)*active
    total_cap=np.maximum(c.moq,(mu.sum(axis=1)*c.store_capacity_days*.8).astype(int))
    dc_item_cap=np.maximum(c.moq,np.ceil(mu.sum(axis=0)*c.dc_capacity_days)).astype(int)
    dc_total_cap=max(c.moq,int(mu.sum()*c.dc_capacity_days*.8))
    store=np.minimum(np.ceil(mu*8).astype(int),item_cap)
    dc=np.minimum(np.ceil(mu.sum(axis=0)*12).astype(int),dc_item_cap)
    for j in range(J):
        if store[j].sum()>total_cap[j]:store[j]=np.floor(store[j]*total_cap[j]/store[j].sum()).astype(int)
    if dc.sum()>dc_total_cap:dc=np.floor(dc*dc_total_cap/dc.sum()).astype(int)
    initial=int(store.sum()+dc.sum())
    pending=np.zeros((J,N),int);transit=np.zeros((J,N),int);supplier=np.zeros(N,int)
    incoming=np.zeros((H+30,J,N),int);external=np.zeros((H+30,N),int)
    rng=np.random.default_rng(np.random.SeedSequence([seed,91]))
    leads=rng.integers(4,9,(H,N));transfer=rng.integers(2,4,(H,J,N))
    if scenario in ('supplier_delay','combined'):leads[H//3:min(H,H//3+14)]+=5
    cost_parts=dict(holding=0.,ordering=0.,transport=0.,lost_margin=0.)
    cash=received=served=lost=blocked=0;stockout_periods=0;inventory_days=0
    demand_pair=D.sum(axis=0);served_pair=np.zeros((J,N));inventory_pair=np.zeros((J,N))
    cycle_started=np.zeros((J,N),bool);cycle_failed=np.zeros((J,N),bool);cycles=good=0
    history=[];proposals=[];movements=[]
    spending=np.zeros((H,J+1))
    buffer4=cal[7]['buffer']*np.sqrt(4/7);buffer10=cal[14]['buffer']*np.sqrt(10/14)
    dc_buffer=cal[14]['dc_buffer']*np.sqrt(9/14)
    for t in range(H):
        # Opening receipts; no zero lead times, no future demand in decisions.
        rec=incoming[t];receiving=rec>0;complete=receiving&cycle_started
        cycles+=int(complete.sum());good+=int((complete&~cycle_failed).sum())
        cycle_started|=receiving;cycle_failed[receiving]=False
        store+=rec;transit-=rec;dc+=external[t];supplier-=external[t]
        received+=int(external[t].sum());cash+=float(np.dot(external[t],cost))
        sold=np.minimum(store,D[t]);short=D[t]-sold;store-=sold
        served+=int(sold.sum());lost+=int(short.sum());served_pair+=sold
        stockout_periods+=int((short>0).sum());cycle_failed|=short>0
        cost_parts['lost_margin']+=float((short*margin).sum())
        ip=store+pending+transit
        if policy=='fixed_cover':raw=np.maximum(0,mu*10-ip) if t%7==0 else np.zeros_like(ip)
        elif policy=='rq':
            trigger=mu*4+buffer4;Q=np.sqrt(2*c.transfer_order_fee*np.maximum(mu,0)/np.maximum(holding,.0001))
            raw=np.where(ip<=trigger,Q,0)
        elif policy=='periodic':raw=np.maximum(0,mu*10+buffer10-ip) if t%7==0 else np.zeros_like(ip)
        elif policy=='forecast_optimized':
            # React to already observed demand, with a capped multiplicative signal.
            previous=D[max(0,t-6):t+1].sum(axis=0)
            expected=forecast[max(0,t-6):t+1,0].sum(axis=0)
            signal=np.clip((previous+7)/(expected+7),.7,1.6)
            target=forecast[t,:4].sum(axis=0)*signal+risk*buffer4
            raw=np.maximum(0,target-ip)
        else:raise ValueError(policy)
        q=np.zeros((J,N),int)
        for j in range(J):
            priority=raw[j]*margin/np.maximum(mu[j]*4,1)
            allowance=max(c.moq*float(cost.max()),float(np.dot(mu[j],cost))*c.budget_days)
            budget=max(0,7*allowance-spending[max(0,t-6):t,j].sum())
            q[j]=constrained_orders(raw[j]*active[j],ip[j],item_cap[j],total_cap[j]-ip[j].sum(),budget,cost,priority,c.pack,c.moq)
            if overrides:
                for i,sku in enumerate(data['skus']):
                    cap=overrides.get((t,data['markets'][j],sku))
                    if cap is not None:q[j,i]=min(q[j,i],cap)
            spending[t,j]=np.dot(q[j],cost)
            assert spending[max(0,t-6):t+1,j].sum()<=7*allowance+1e-6
            blocked+=int(((raw[j]>0)&(q[j]==0)&active[j]).sum())
            if record:
                for i in np.flatnonzero(q[j]):
                    proposals.append(dict(day=t,location=data['markets'][j],sku=data['skus'][i],qty=int(q[j,i]),position=int(ip[j,i]),room=int(min(item_cap[j,i]-ip[j,i],total_cap[j]-ip[j].sum())),pack=c.pack,moq=c.moq,
                        rationale='Target gap ranked by shortage exposure, with pack, space and purchasing-budget constraints.'))
        pending+=q;cost_parts['ordering']+=float((q>0).sum())*c.transfer_order_fee
        # Proportional allocation by SKU; a rotating remainder rule avoids fixed priority.
        total=pending.sum(axis=0)
        fraction=np.minimum(1,dc/np.maximum(total,1))
        ships=np.floor(pending*fraction[None]).astype(int)
        left=dc-ships.sum(axis=0)
        for j in [(t+k)%J for k in range(J)]:
            extra=np.minimum(pending[j]-ships[j],left);ships[j]+=extra;left-=extra
        for j in range(J):
            ship=ships[j];pending[j]-=ship;dc-=ship;transit[j]+=ship
            for i in np.flatnonzero(ship):
                due=t+int(transfer[t,j,i]);incoming[due,j,i]+=ship[i]
                if record:movements.append(dict(placed=t,due=due,source='CENTRAL',destination=data['markets'][j],sku=data['skus'][i],units=int(ship[i])))
        cost_parts['transport']+=float((ships*prices*c.freight_fraction).sum())
        dc_position=dc+supplier-pending.sum(axis=0)
        mult=dc_scale if policy=='forecast_optimized' else 1.
        dc_target=mult*(forecast[t,:9].sum(axis=(0,1))+dc_buffer*(risk if policy=='forecast_optimized' else 1.))
        rawdc=np.maximum(0,dc_target-dc_position)
        dc_allowance=max(c.moq*float(cost.max()),float(np.dot(mu.sum(axis=0),cost))*c.budget_days)
        dc_budget=max(0,7*dc_allowance-spending[max(0,t-6):t,J].sum())
        dq=constrained_orders(rawdc,dc+supplier,dc_item_cap,dc_total_cap-(dc+supplier).sum(),dc_budget,cost,rawdc*margin/np.maximum(mu.sum(axis=0)*9,1),c.pack,c.moq)
        if overrides:
            for i,sku in enumerate(data['skus']):
                cap=overrides.get((t,'CENTRAL',sku))
                if cap is not None:dq[i]=min(dq[i],cap)
        spending[t,J]=np.dot(dq,cost)
        assert spending[max(0,t-6):t+1,J].sum()<=7*dc_allowance+1e-6
        if record:
            for i in np.flatnonzero(dq):
                proposals.append(dict(day=t,location='CENTRAL',sku=data['skus'][i],qty=int(dq[i]),position=int(dc_position[i]),room=int(min(dc_item_cap[i]-dc[i]-supplier[i],dc_total_cap-(dc+supplier).sum())),pack=c.pack,moq=c.moq,rationale='Aggregate nine-day forecast and calibrated buffer; subtract owed hub requests.'))
        supplier+=dq;cost_parts['ordering']+=float((dq>0).sum())*c.supplier_order_fee
        for i in np.flatnonzero(dq):
            due=t+int(leads[t,i]);external[due,i]+=dq[i]
            if record:movements.append(dict(placed=t,due=due,source='SUPPLIER',destination='CENTRAL',sku=data['skus'][i],units=int(dq[i])))
        cost_parts['holding']+=float((store*holding).sum()+np.dot(dc,holding*.7))
        inventory_days+=int(store.sum()+dc.sum());inventory_pair+=store
        if record:history.append(dict(day=t,demand=int(D[t].sum()),served=int(sold.sum()),lost=int(short.sum()),store_stock=int(store.sum()),dc_stock=int(dc.sum()),internal_transit=int(transit.sum()),supplier_pipeline=int(supplier.sum()),pending=int(pending.sum()),cumulative_cost=sum(cost_parts.values())))
        assert int(store.sum()+dc.sum()+transit.sum())==initial+received-served
        assert np.all(store>=0) and np.all(dc>=0) and np.all(pending>=0)
        assert np.all((store+transit+pending).sum(axis=1)<=total_cap)
        assert (dc+supplier).sum()<=dc_total_cap
        assert np.all(store+transit+pending<=item_cap)
        assert np.all(dc+supplier<=dc_item_cap)
        assert np.array_equal(incoming[t+1:].sum(axis=0),transit)
        assert np.array_equal(external[t+1:].sum(axis=0),supplier)
    assert served+lost==int(D.sum())
    pairfill=np.divide(served_pair,demand_pair,out=np.full_like(served_pair,np.nan),where=demand_pair>0)
    a_mask=data['sku_master'].abc.to_numpy()=='A'
    A_demand=demand_pair[:,a_mask].sum();A_served=served_pair[:,a_mask].sum()
    metrics=dict(policy=policy,scenario=scenario,seed=seed,relevant_cost_gbp=sum(cost_parts.values()),
        **{k+'_cost_gbp':v for k,v in cost_parts.items()},procurement_cash_gbp=cash,
        demand_units=int(D.sum()),fulfilled_units=served,lost_units=lost,fill_rate=served/D.sum() if D.sum() else np.nan,
        a_fill_rate=A_served/A_demand if A_demand else np.nan,
        worst_material_pair_fill=float(np.nanmin(pairfill[demand_pair>=30])) if np.any(demand_pair>=30) else np.nan,
        average_inventory_units=inventory_days/H,stockout_pair_days=stockout_periods,
        cycle_service=good/cycles if cycles else np.nan,completed_cycles=cycles,
        ending_inventory_value_gbp=float(((store.sum(axis=0)+dc+transit.sum(axis=0))*cost).sum()),
        ending_pending_units=int(pending.sum()),ending_supplier_units=int(supplier.sum()),
        constrained_order_events=blocked,feasible=True,runtime_seconds=time.perf_counter()-started)
    pair=pd.DataFrame([dict(market=data['markets'][j],sku=data['skus'][i],demand=demand_pair[j,i],fulfilled=served_pair[j,i],fill_rate=pairfill[j,i],average_stock=inventory_pair[j,i]/H) for j,i in zip(*np.where(active))])
    return metrics,pd.DataFrame(history),pd.DataFrame(proposals),pd.DataFrame(movements),pair
