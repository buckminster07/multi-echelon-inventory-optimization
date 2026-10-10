"""UCI acquisition, auditable cleaning, train-only cohort, SQL integration."""
from pathlib import Path
import hashlib,json,sqlite3,urllib.request,zipfile
import numpy as np
import pandas as pd

URL='https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip'
DOI='https://doi.org/10.24432/C5CG6D'

def acquire(cache):
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    archive=cache/'online_retail_ii.zip'
    if not archive.exists():
        temporary=archive.with_suffix('.partial')
        urllib.request.urlretrieve(URL,temporary)
        with zipfile.ZipFile(temporary) as z:
            if z.testzip() is not None:raise ValueError('Dataset ZIP failed integrity check')
        temporary.replace(archive)
    return archive

def clean_transactions(archive,cache):
    cache=Path(cache);clean_path=cache/'clean_transactions.parquet';audit_path=cache/'cleaning_audit.json'
    if clean_path.exists() and audit_path.exists():
        return pd.read_parquet(clean_path),json.loads(audit_path.read_text())
    with zipfile.ZipFile(archive) as z:
        member=next(n for n in z.namelist() if n.lower().endswith('.xlsx'))
        workbook=cache/'online_retail_II.xlsx'
        if not workbook.exists():workbook.write_bytes(z.read(member))
    frames=pd.read_excel(workbook,sheet_name=None,usecols=['Invoice','StockCode','Description','Quantity','InvoiceDate','Price','Country'],engine='openpyxl')
    frame=pd.concat(frames.values(),ignore_index=True)
    audit={'source':URL,'doi':DOI,'license':'CC BY 4.0','raw_rows':len(frame),
           'sha256':hashlib.sha256(Path(archive).read_bytes()).hexdigest()}
    frame.columns=['invoice','sku','description','quantity','timestamp','price','market']
    for name in ['invoice','sku','market']:frame[name]=frame[name].astype(str).str.strip()
    frame['timestamp']=pd.to_datetime(frame.timestamp,errors='coerce')
    frame['date']=frame.timestamp.dt.normalize()
    # Returns/cancellations are recorded in audit, never subtracted from future demand.
    cancellation=frame.invoice.str.upper().str.startswith('C')|(frame.quantity<0)
    audit['cancellation_rows']=int(cancellation.sum())
    audit['returned_units']=float(-frame.loc[frame.quantity<0,'quantity'].sum())
    valid_date=frame.date.notna()
    product=frame.sku.str.match(r'^\d{5}[A-Za-z]*$')
    positive=(frame.quantity>0)&(frame.price>0)
    audit['nonproduct_rows']=int((~product).sum())
    audit['nonpositive_rows']=int((~positive).sum())
    # Exact repeated invoice lines are retained: these can be separate legitimate lines.
    # No invoice-line identifier exists to establish that they are accidental duplicates.
    audit['exact_repeated_lines_retained']=int(frame.duplicated().sum())
    frame=frame[valid_date&product&positive&~cancellation].copy()
    audit['extreme_bulk_rows_excluded']=int((frame.quantity>10000).sum())
    frame=frame[frame.quantity<=10000].copy()
    frame['revenue']=frame.quantity*frame.price
    audit.update(clean_rows=len(frame),first_date=str(frame.date.min().date()),last_date=str(frame.date.max().date()),
        privacy='Customer identifiers are never loaded or exported.',
        returns_treatment='Excluded from outbound sales demand; no assumed resale recovery.',
        outlier_rule='Exclude a line exceeding 10,000 units; retain all other observed quantities.')
    frame.to_parquet(clean_path,index=False)
    audit_path.write_text(json.dumps(audit,indent=2))
    return frame,audit

def prepare(frame,c):
    train=frame[frame.date<=c.train_end]
    markets=train.groupby('market').revenue.sum().nlargest(c.market_count).index.tolist()
    eligible=train[train.market.isin(markets)].groupby('sku').agg(revenue=('revenue','sum'),days=('date','nunique'),first=('date','min'))
    skus=eligible[eligible.days>=30].nlargest(c.sku_count,'revenue').index.tolist()
    train=train[train.market.isin(markets)&train.sku.isin(skus)]
    dates=pd.date_range(frame.date.min(),c.test_end)
    index=pd.MultiIndex.from_product([dates,markets,skus],names=['date','market','sku'])
    selected=frame[frame.market.isin(markets)&frame.sku.isin(skus)&(frame.date<=c.test_end)]
    daily=selected.groupby(['date','market','sku']).quantity.sum().reindex(index,fill_value=0)
    y=daily.to_numpy().reshape(len(dates),len(markets),len(skus)).astype(float)
    # Assortment only uses initial training information; no future popularity filter.
    pairs=train.groupby(['market','sku']).size().reindex(pd.MultiIndex.from_product([markets,skus]),fill_value=0).to_numpy().reshape(len(markets),len(skus))
    active=pairs>=3;y*=active[None]
    cutoff=int(dates.searchsorted(pd.Timestamp(c.train_end),side='right'))
    train_y=y[:cutoff];mu=train_y.mean(axis=0)
    prices=train.groupby('sku').price.median().reindex(skus).to_numpy()
    value=(train_y.sum(axis=(0,1))*prices)
    order=np.argsort(-value);prior=(np.cumsum(value[order])-value[order])/value.sum()
    abc=np.empty(len(skus),dtype=object);abc[order]=np.where(prior<.8,'A',np.where(prior<.95,'B','C'))
    total=train_y.sum(axis=1);cv=total.std(axis=0)/np.maximum(total.mean(axis=0),1e-9)
    xyz=np.where(cv<.5,'X',np.where(cv<1,'Y','Z'))
    zero=(train_y==0).mean(axis=0);adi=cutoff/np.maximum((train_y>0).sum(axis=0),1)
    sku_master=pd.DataFrame({'sku':skus,'median_selling_price_gbp':prices,'acquisition_cost_assumed_gbp':prices*c.acquisition_fraction,'abc':abc,'xyz':xyz,'train_revenue':value})
    pairs_frame=pd.DataFrame([dict(market=markets[j],sku=skus[i],active=bool(active[j,i]),mean_daily_units=mu[j,i],zero_fraction=zero[j,i],adi=adi[j,i]) for j in range(len(markets)) for i in range(len(skus))])
    return dict(y=y,dates=dates,markets=markets,skus=skus,active=active,mu=mu,prices=prices,
                sku_master=sku_master,pairs=pairs_frame,selection_rule='Top training-revenue markets and SKUs with >=30 training sales days; pair has >=3 training transaction lines.')

SCHEMA='''
PRAGMA foreign_keys=ON;
CREATE TABLE sku(sku TEXT PRIMARY KEY,selling_price_gbp REAL,acquisition_cost_gbp REAL,abc TEXT,xyz TEXT);
CREATE TABLE location(location TEXT PRIMARY KEY,kind TEXT,parent TEXT REFERENCES location);
CREATE TABLE assortment(location TEXT REFERENCES location,sku TEXT REFERENCES sku,PRIMARY KEY(location,sku));
CREATE TABLE daily_sales(date TEXT,location TEXT,sku TEXT,units REAL CHECK(units>=0),PRIMARY KEY(date,location,sku),FOREIGN KEY(location,sku) REFERENCES assortment);
CREATE TABLE experiment(run_id TEXT PRIMARY KEY,policy TEXT,scenario TEXT,seed INTEGER,split TEXT);
CREATE TABLE proposal(proposal_id TEXT PRIMARY KEY,run_id TEXT REFERENCES experiment,day INTEGER,location TEXT,sku TEXT,qty INTEGER CHECK(qty>=0),position REAL,room INTEGER,pack INTEGER,moq INTEGER,status TEXT DEFAULT 'pending',FOREIGN KEY(location,sku) REFERENCES assortment);
CREATE TABLE decision(decision_id INTEGER PRIMARY KEY,proposal_id TEXT REFERENCES proposal,created_utc TEXT,action TEXT CHECK(action IN ('approved','modified','rejected')),quantity INTEGER CHECK(quantity>=0),actor TEXT,reason TEXT);
CREATE UNIQUE INDEX one_decision_per_proposal ON decision(proposal_id);
CREATE TABLE assumptions(name TEXT PRIMARY KEY,value TEXT,provenance TEXT);
'''
def sql_store(data,c,path):
    path=Path(path)
    if path.exists():raise FileExistsError('Use a new output directory; preserve existing planner audit records.')
    db=sqlite3.connect(path);db.executescript(SCHEMA)
    db.executemany('INSERT INTO sku VALUES(?,?,?,?,?)',[(r.sku,r.median_selling_price_gbp,r.acquisition_cost_assumed_gbp,r.abc,r.xyz) for r in data['sku_master'].itertuples()])
    db.execute("INSERT INTO location VALUES('CENTRAL','warehouse',NULL)")
    db.executemany("INSERT INTO location VALUES(?,'market_hub','CENTRAL')",[(m,) for m in data['markets']])
    db.executemany('INSERT INTO assortment VALUES(?,?)',[(m,s) for j,m in enumerate(data['markets']) for i,s in enumerate(data['skus']) if data['active'][j,i]]+[('CENTRAL',s) for s in data['skus']])
    rows=((str(d.date()),m,s,float(data['y'][t,j,i])) for t,d in enumerate(data['dates']) for j,m in enumerate(data['markets']) for i,s in enumerate(data['skus']) if data['active'][j,i])
    db.executemany('INSERT INTO daily_sales VALUES(?,?,?,?)',rows)
    db.executemany('INSERT INTO assumptions VALUES(?,?,?)',[(k,json.dumps(v),'planning assumption') for k,v in c.dict().items()])
    db.commit();assert not db.execute('PRAGMA foreign_key_check').fetchall()
    # Analytical extract is used to reconstruct the modeling panel, not just shown.
    result=np.zeros_like(data['y']);dm={str(v.date()):i for i,v in enumerate(data['dates'])};jm={s:j for j,s in enumerate(data['markets'])};im={s:i for i,s in enumerate(data['skus'])}
    for day,market,sku,units in db.execute('SELECT date,location,sku,units FROM daily_sales JOIN assortment USING(location,sku) ORDER BY date,location,sku'):
        result[dm[day],jm[market],im[sku]]=units
    np.testing.assert_array_equal(result,data['y']);data['y']=result
    return db
