import sqlite3
import numpy as np
import pandas as pd
import pytest
from retail_planner.config import Config
from retail_planner.data import SCHEMA,prepare
from retail_planner.forecast import forecast_all,feature_matrix
from retail_planner.simulation import constrained_orders,simulate,scenario_path
from retail_planner.planner import save_proposals,decide,decision_caps

def fixture_data():
    dates=pd.date_range('2009-12-01','2011-11-30');J,N=2,3
    y=np.ones((len(dates),J,N))*4
    return dict(y=y,dates=dates,active=np.ones((J,N),bool),mu=np.ones((J,N))*4,
        prices=np.array([2.,4.,6.]),markets=['UK','France'],skus=['A','B','C'],
        sku_master=pd.DataFrame({'abc':['A','A','C']}))

def test_budget_capacity_and_pack_together():
    c=Config.quick()
    q=constrained_orders(np.array([100,100,100]),np.array([0,0,0]),np.array([100,100,100]),30,50,np.array([3.,2.,1.]),np.array([3.,2.,1.]),6,12)
    assert q.sum()<=30 and q@np.array([3.,2.,1.])<=50
    assert ((q==0)|((q>=12)&(q%6==0))).all()

def test_forecast_uses_no_future_actuals():
    class FakeModel:
        def predict(self,x):return (x[:,4]+x[:,5])/2
    data=fixture_data();before=forecast_all(data,FakeModel(),100,14)
    data['y'][100:]=1e6;after=forecast_all(data,FakeModel(),100,14)
    np.testing.assert_array_equal(before,after)

def test_simulation_accounting_timing_and_shared_paths():
    data=fixture_data();c=Config.quick();H=20
    observed=np.ones((H,2,3),int)*4;forecast=np.ones((H,14,2,3))*4
    cal={7:{'buffer':np.ones((2,3))*4},14:{'buffer':np.ones((2,3))*8,'dc_buffer':np.ones(3)*12}}
    a,tr,orders,moves,pair=simulate(data,c,forecast,observed,cal,'forecast_optimized','combined',99,record=True)
    b=simulate(data,c,forecast,observed,cal,'forecast_optimized','combined',99)[0]
    assert a['relevant_cost_gbp']==b['relevant_cost_gbp']
    assert a['fulfilled_units']+a['lost_units']==a['demand_units']
    assert a['relevant_cost_gbp']==pytest.approx(sum(a[k] for k in ['holding_cost_gbp','ordering_cost_gbp','transport_cost_gbp','lost_margin_cost_gbp']))
    assert (moves.due>moves.placed).all()
    assert (moves.query("source=='SUPPLIER'").due-moves.query("source=='SUPPLIER'").placed>=4).all()
    np.testing.assert_array_equal(scenario_path(observed,'combined',99),scenario_path(observed,'combined',99))

def test_transactional_approval_guards():
    db=sqlite3.connect(':memory:');db.executescript(SCHEMA)
    db.execute("INSERT INTO sku VALUES('A',2,1,'A','Z')");db.execute("INSERT INTO location VALUES('CENTRAL','warehouse',NULL)");db.execute("INSERT INTO assortment VALUES('CENTRAL','A')");db.commit()
    p=pd.DataFrame([dict(day=0,location='CENTRAL',sku='A',qty=24,position=0,room=100,pack=6,moq=12)])
    save_proposals(db,'r','periodic','normal',1,p)
    pid=db.execute('SELECT proposal_id FROM proposal').fetchone()[0]
    with pytest.raises(ValueError):decide(db,pid,'modified',13,'Planner','bad pack')
    with pytest.raises(ValueError):decide(db,pid,'modified',30,'Planner','exceeds allocation')
    with pytest.raises(ValueError):decide(db,pid,'approved',24,'','missing actor')
    assert decide(db,pid,'modified',12,'Planner','reduce exposure')==12
    with pytest.raises(ValueError):decide(db,pid,'approved',24,'Planner','duplicate')
    assert decision_caps(db,'r')=={(0,'CENTRAL','A'):12}
    assert db.execute('SELECT COUNT(*) FROM decision').fetchone()[0]==1

def test_cohort_does_not_use_test_revenue():
    c=Config(sku_count=1,market_count=1)
    dates=pd.date_range('2010-01-01',periods=40)
    rows=[dict(date=d,market='UK',sku=s,quantity=q,price=1.,revenue=q) for d in dates for s,q in [('10001',10),('10002',1)]]
    f=pd.DataFrame(rows);original=prepare(f,c)
    altered=pd.concat([f,pd.DataFrame([dict(date=pd.Timestamp('2011-10-01'),market='UK',sku='10002',quantity=1000000,price=1.,revenue=1000000)])],ignore_index=True)
    assert original['skus']==prepare(altered,c)['skus']==['10001']
