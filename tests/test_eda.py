import numpy as np
import pandas as pd
from retail_planner.eda import cutoff_sensitivity, price_changes, return_rates, seasonality


def fixture():
    return pd.DataFrame(dict(invoice=['1','2','C3','4','C5'],sku=['12345']*5,
        market=['UK']*5,date=pd.to_datetime(['2011-01-01']*4+['2012-01-01']),
        quantity=[10,20000,-4,0,-99999],price=[2]*5))


def test_cutoff_denominator_and_training_boundary():
    frame=fixture()
    result=cutoff_sensitivity(frame,'2011-01-31',(10000,None))
    assert result.retained_units.tolist()==[10,20010]
    assert result.excluded_rows.tolist()==[1,0]
    assert np.isclose(result.unit_retention_pct.iloc[0],100*10/20010)


def test_returns_are_unlinked_units_not_negative_sales():
    result=return_rates(fixture().iloc[:4]).iloc[0]
    assert result.gross_units==20010
    assert result.returned_units==4


def test_price_changes_require_consecutive_supported_months():
    frame=pd.DataFrame([dict(market='UK',sku='12345',date=pd.Timestamp(date),price=price)
        for date,price,n in [('2011-01-01',10,5),('2011-02-01',12,5),('2011-04-01',18,5),('2011-05-01',20,4)] for _ in range(n)])
    result=price_changes(frame)
    assert len(result)==3
    assert np.isclose(result.change_pct.iloc[1],20)
    assert pd.isna(result.change_pct.iloc[2])


def test_weekday_effect_and_incomplete_month():
    dates=pd.date_range('2010-01-01','2010-06-15')
    frame=pd.DataFrame({'date':dates,'quantity':10+dates.dayofweek*3})
    daily,weekly,monthly,evidence=seasonality(frame,'2010-06-15')
    assert evidence['complete_weeks']>10
    assert evidence['p_value']<.001
    assert not bool(monthly.complete_month.iloc[-1])
    assert len(weekly)==7
    assert len(daily)==len(dates)
