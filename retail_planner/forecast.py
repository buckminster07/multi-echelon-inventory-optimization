"""Causal rolling-origin baselines, a global Poisson booster, calibrated buffers."""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

MODELS=('seasonal_naive','moving_average','tsb','global_boosting')
def end_index(data,date):return int(data['dates'].searchsorted(pd.Timestamp(date),side='right'))

def feature_matrix(history,date,active):
    J,N=active.shape;j,i=np.where(active)
    z=history.reshape(len(history),J*N)[:,active.ravel()]
    rolling=z[-28:]
    x=np.column_stack([j,i,np.full(len(j),date.dayofweek),np.full(len(j),date.month),
        z[-1],z[-7],z[-14],z[-28],z[-7:].mean(axis=0),rolling.mean(axis=0),
        rolling.std(axis=0),(rolling==0).mean(axis=0),np.full(len(j),date.day),
        np.full(len(j),date.dayofyear)])
    return x

def train_booster(data,c):
    stop=end_index(data,c.train_end);rng=np.random.default_rng(c.seed)
    per_day=max(1,c.max_ml_rows//max(1,stop-56));features=[];labels=[]
    for t in range(56,stop):
        x=feature_matrix(data['y'][:t],data['dates'][t],data['active'])
        y=data['y'][t][data['active']]
        keep=rng.choice(len(y),min(per_day,len(y)),replace=False)
        features.append(x[keep]);labels.append(y[keep])
    model=HistGradientBoostingRegressor(loss='poisson',max_iter=100,max_leaf_nodes=23,
        learning_rate=.07,l2_regularization=3.,categorical_features=[0,1],
        early_stopping=False,random_state=c.seed)
    with threadpool_limits(limits=2):model.fit(np.concatenate(features),np.concatenate(labels))
    return model,sum(map(len,labels))

def forecast_all(data,model,origin,horizon):
    y=data['y'][:origin];shape=y.shape[1:];active=data['active']
    seasonal=np.array([y[-7+(k%7)] for k in range(horizon)])
    mean=np.repeat(y[-28:].mean(axis=0)[None],horizon,axis=0)
    recent=y[-112:];p=(recent[:28]>0).mean(axis=0)
    z=recent[:28].mean(axis=0)/np.maximum(p,.01)
    for v in recent[28:]:
        p=.1*(v>0)+.9*p;z=np.where(v>0,.1*v+.9*z,z)
    tsb=np.repeat((p*z)[None],horizon,axis=0)
    working=y[-56:].copy();boost=[]
    date=data['dates'][origin-1]+pd.Timedelta(days=1)
    with threadpool_limits(limits=2):
        for k in range(horizon):
            x=feature_matrix(working,date+pd.Timedelta(days=k),active)
            pred=np.zeros(shape);pred[active]=np.maximum(model.predict(x),0)
            boost.append(pred);working=np.concatenate([working[1:],pred[None]])
    return np.array([seasonal,mean,tsb,np.array(boost)])*active[None,None]

def select_models(data,c,model):
    start=end_index(data,c.train_end);stop=end_index(data,c.selection_end)
    scores=np.zeros((4,*data['active'].shape));rows=[]
    for origin in range(start,stop-6,3):
        preds=forecast_all(data,model,origin,7);actual=data['y'][origin:origin+7]
        scores+=np.abs(preds-actual[None]).mean(axis=1)
        for m,name in enumerate(MODELS):
            e=(preds[m]-actual)[:,data['active']];a=actual[:,data['active']]
            rows.append(dict(origin=str(data['dates'][origin].date()),model=name,mae=np.abs(e).mean(),rmse=np.sqrt((e*e).mean()),bias=e.mean(),wape=np.abs(e).sum()/max(a.sum(),1)))
    return scores.argmin(axis=0),pd.DataFrame(rows)

def selected(bank,choice):return np.take_along_axis(bank,choice[None,None],axis=0)[0]

def calibrate(data,c,model,choice):
    start=end_index(data,c.selection_end);stop=end_index(data,c.calibration_end)
    errors={h:[] for h in (1,3,7,14)}
    for origin in range(start,stop-13,3):
        p=selected(forecast_all(data,model,origin,14),choice)
        e=data['y'][origin:origin+14]-p
        for h in errors:errors[h].append(e[:h].sum(axis=0))
    result={}
    for h,blocks in errors.items():
        e=np.array(blocks);lower=np.quantile(e,.05,axis=0);upper=np.quantile(e,.95,axis=0)
        result[h]={'errors':e,'lower':lower,'upper':upper,'buffer':np.maximum(upper,0),
                   'dc_buffer':np.maximum(np.quantile(e.sum(axis=1),.95,axis=0),0)}
    return result

def forecast_window(data,c,model,choice,start,stop,calibration):
    # Weekly forecast publication; daily decisions consume only the forecast
    # available at that date. Horizon 21 supplies 14 days after the next review.
    H=stop-start;J,N=data['active'].shape
    forecasts=np.zeros((H,14,J,N));metrics=[];intervals=[]
    for origin in range(start,stop,7):
        bank=forecast_all(data,model,origin,c.forecast_horizon);p=selected(bank,choice)
        length=min(7,stop-origin)
        for d in range(length):forecasts[origin-start+d]=p[d+1:d+15]
        actual=data['y'][origin:origin+length]
        for mi,name in enumerate((*MODELS,'selected')):
            pred=bank[mi,:length] if mi<4 else p[:length]
            for j,i in zip(*np.where(data['active'])):
                e=pred[:,j,i]-actual[:,j,i];a=actual[:,j,i]
                metrics.append(dict(origin=str(data['dates'][origin].date()),market=data['markets'][j],sku=data['skus'][i],model=name,absolute_error=float(np.abs(e).sum()),squared_error=float((e*e).sum()),signed_error=float(e.sum()),actual_units=float(a.sum()),observations=length))
        for h in (1,3,7,14):
            if origin+h>stop:continue
            expected=p[:h].sum(axis=0);a=data['y'][origin:origin+h].sum(axis=0)
            lower=np.maximum(0,expected+calibration[h]['lower']);upper=np.maximum(lower,expected+calibration[h]['upper'])
            for j,i in zip(*np.where(data['active'])):
                intervals.append(dict(origin=str(data['dates'][origin].date()),market=data['markets'][j],sku=data['skus'][i],horizon=h,covered=bool(lower[j,i]<=a[j,i]<=upper[j,i]),width=float(upper[j,i]-lower[j,i])))
    return forecasts,pd.DataFrame(metrics),pd.DataFrame(intervals)

def summarize_forecasts(metrics):
    s=metrics.groupby('model')[['absolute_error','squared_error','signed_error','actual_units','observations']].sum()
    return pd.DataFrame({'mae':s.absolute_error/s.observations,'rmse':np.sqrt(s.squared_error/s.observations),
        'bias':s.signed_error/s.observations,'wape':s.absolute_error/s.actual_units.replace(0,np.nan)}).reset_index()
