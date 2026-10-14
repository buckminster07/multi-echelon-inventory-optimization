"""Auditable descriptive EDA. Modeling diagnostics use the training window only."""
from pathlib import Path
import hashlib
import json
import zipfile
import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare


def load_raw(archive, cache):
    cache = Path(cache)
    workbook = cache / 'online_retail_II.xlsx'
    if not workbook.exists():
        with zipfile.ZipFile(archive) as z:
            workbook.write_bytes(z.read(next(n for n in z.namelist() if n.lower().endswith('.xlsx'))))
    # Inspect customer-ID completeness without retaining or exporting identifiers.
    frames, completeness = [], []
    for sheet, frame in pd.read_excel(workbook, sheet_name=None).items():
        for column in frame:
            absent = frame[column].isna() | frame[column].astype('string').str.strip().eq('').fillna(False)
            completeness.append(dict(sheet=sheet, field=column, rows=len(frame), missing=int(absent.sum())))
        frames.append(frame.drop(columns=['Customer ID'], errors='ignore'))
    missing = pd.DataFrame(completeness)
    overall = missing.groupby('field', as_index=False)[['rows', 'missing']].sum()
    overall['sheet'] = 'ALL'
    missing = pd.concat([missing, overall], ignore_index=True)
    missing['missing_pct'] = 100 * missing.missing / missing.rows
    raw = pd.concat(frames, ignore_index=True).rename(columns={
        'Invoice':'invoice', 'StockCode':'sku', 'Description':'description',
        'Quantity':'quantity', 'InvoiceDate':'timestamp', 'Price':'price', 'Country':'market'})
    raw['date'] = pd.to_datetime(raw.timestamp, errors='coerce').dt.normalize()
    for col in ['invoice', 'sku', 'market']:
        raw[col] = raw[col].astype('string').str.strip()
    return raw, missing


def product_mask(raw):
    return raw.sku.str.match(r'^\d{5}[A-Za-z]*$').fillna(False)


def sale_mask(raw):
    return (product_mask(raw) & raw.date.notna() & raw.market.notna()
            & (raw.quantity > 0) & (raw.price > 0)
            & ~raw.invoice.str.upper().str.startswith('C').fillna(False))


def return_rates(raw):
    """Unlinked negative-quantity units / gross positive outbound units, not order return probability."""
    product = raw[product_mask(raw) & raw.market.notna() & raw.date.notna()]
    sales = product[sale_mask(product)]
    returns = product[product.quantity < 0].copy()
    returns['returned_units'] = -returns.quantity
    gross = sales.groupby('market').agg(gross_units=('quantity','sum'), sales_lines=('quantity','size'))
    negative = returns.groupby('market').agg(returned_units=('returned_units','sum'), return_lines=('quantity','size'))
    result = gross.join(negative, how='outer').fillna(0).reset_index()
    result['returned_to_gross_unit_pct'] = np.where(result.gross_units > 0, 100 * result.returned_units / result.gross_units, np.nan)
    return result.sort_values('gross_units', ascending=False)


def cutoff_sensitivity(raw, cutoff_date, thresholds=(1000, 5000, 10000, None)):
    sales = raw[sale_mask(raw) & (raw.date <= cutoff_date)].copy()
    sales['revenue'] = sales.quantity * sales.price
    total_units, total_revenue = sales.quantity.sum(), sales.revenue.sum()
    dates = pd.date_range(sales.date.min(), cutoff_date)
    rows = []
    for limit in thresholds:
        kept = sales if limit is None else sales[sales.quantity <= limit]
        daily = kept.groupby('date').quantity.sum().reindex(dates, fill_value=0)
        rows.append(dict(cutoff='No cutoff' if limit is None else str(limit),
            retained_rows=len(kept), excluded_rows=len(sales)-len(kept),
            retained_units=kept.quantity.sum(), unit_retention_pct=100*kept.quantity.sum()/total_units,
            revenue_retention_pct=100*kept.revenue.sum()/total_revenue,
            max_daily_units=daily.max(), daily_cv=daily.std(ddof=0)/daily.mean()))
    return pd.DataFrame(rows)


def seasonality(sales, end):
    daily = sales.groupby('date').quantity.sum().reindex(pd.date_range(sales.date.min(), end), fill_value=0)
    table = pd.DataFrame({'date':daily.index, 'units':daily.values})
    table['trend_28d'] = daily.rolling(28, center=True, min_periods=28).mean().to_numpy()
    table['relative_units'] = table.units / table.trend_28d.replace(0, np.nan)
    table['weekday'] = table.date.dt.dayofweek
    table['week'] = table.date - pd.to_timedelta(table.weekday, unit='D')
    weeks = table.pivot(index='week', columns='weekday', values='relative_units').reindex(columns=range(7)).dropna()
    statistic, pvalue = friedmanchisquare(*(weeks[i].to_numpy() for i in range(7))) if len(weeks)>=3 else (np.nan, np.nan)
    weekly = table.groupby('weekday').agg(mean_units=('units','mean'), mean_relative_units=('relative_units','mean'), days=('units','size')).reset_index()
    table['month'] = table.date.dt.to_period('M').astype(str)
    monthly = table.groupby('month').agg(units=('units','sum'), observed_days=('units','size')).reset_index()
    monthly['calendar_days'] = pd.to_datetime(monthly.month).dt.days_in_month
    monthly['complete_month'] = monthly.observed_days == monthly.calendar_days
    monthly['mean_daily_units'] = monthly.units / monthly.observed_days
    evidence = dict(test='Friedman weekday effect; complete weeks; 28-day detrended sales',
        complete_weeks=len(weeks), statistic=float(statistic), p_value=float(pvalue),
        kendalls_w=float(statistic/(len(weeks)*6)) if len(weeks) else None,
        interpretation='Exploratory weekday association, not proof of customer-demand seasonality. Serial dependence and ordering/closure schedules affect inference. Monthly plot is descriptive; less than two complete annual cycles in training cannot establish annual seasonality.')
    return table, weekly, monthly, evidence


def price_changes(sales):
    frame = sales.copy()
    frame['month'] = frame.date.dt.to_period('M').astype(str)
    monthly = frame.groupby(['market','sku','month']).agg(median_price=('price','median'), lines=('price','size')).reset_index()
    monthly = monthly[monthly.lines >= 5].sort_values(['market','sku','month']).copy()
    grouped = monthly.groupby(['market','sku'])
    monthly['previous_price'] = grouped.median_price.shift()
    monthly['previous_month'] = grouped.month.shift()
    month_number = pd.PeriodIndex(monthly.month, freq='M').asi8
    previous_number = pd.PeriodIndex(monthly.previous_month, freq='M').asi8
    consecutive = monthly.previous_month.notna() & (month_number-previous_number == 1)
    monthly['change_pct'] = np.where(consecutive, 100*(monthly.median_price/monthly.previous_price-1), np.nan)
    return monthly


def run_eda(archive, cache, output, train_end):
    out = Path(output); out.mkdir(parents=True, exist_ok=True)
    raw, missing = load_raw(archive, cache)
    training = raw[raw.date <= train_end]
    sales = training[sale_mask(training) & (training.quantity <= 10000)].copy()
    returns = return_rates(training)
    sensitivity = cutoff_sensitivity(raw, train_end)
    daily, weekly, monthly, evidence = seasonality(sales, train_end)
    prices = price_changes(sales)
    tables = dict(missing_values=missing, market_returns=returns, cutoff_sensitivity=sensitivity,
                  seasonal_daily=daily, weekday_profile=weekly, monthly_profile=monthly, monthly_prices=prices)
    export_eda(tables, evidence, archive, out, train_end)
    return tables, evidence


def plot_eda_section(section, tables, output):
    """Render one already-computed EDA topic; usable independently in a notebook."""
    import matplotlib.pyplot as plt
    out = Path(output); out.mkdir(parents=True, exist_ok=True)
    missing=tables.get('missing_values');daily=tables.get('seasonal_daily')
    weekly=tables.get('weekday_profile');monthly=tables.get('monthly_profile')
    prices=tables.get('monthly_prices');returns=tables.get('market_returns')
    sensitivity=tables.get('cutoff_sensitivity')
    plt.rcParams.update({'font.size':10})
    def save(fig, name):
        fig.tight_layout(); fig.savefig(out/(name+'.png'), dpi=140); plt.close(fig)
    if section == 'missing_values':
        fig, ax = plt.subplots(figsize=(9,4))
        overall = missing[missing.sheet=='ALL'].sort_values('missing_pct')
        ax.barh(overall.field, overall.missing_pct, color='#277f8e')
        for i, value in enumerate(overall.missing_pct): ax.text(value+.15, i, f'{value:.2f}%', va='center')
        ax.set(xlabel='Missing or blank (%)', title='Original workbook: completeness before cleaning', xlim=(0,max(5,overall.missing_pct.max()*1.25)))
        save(fig,'missing_values')
        return out / (section+'.png')
    if section == 'seasonality':
        fig, axes = plt.subplots(3,1,figsize=(11,10))
        axes[0].plot(daily.date,daily.units,alpha=.4,label='Daily sales')
        axes[0].plot(daily.date,daily.trend_28d,color='#a84931',label='28-day centered mean')
        axes[0].set(title='Training data: trend and spikes',ylabel='Units');axes[0].legend()
        axes[1].bar(['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],weekly.mean_relative_units,color='#277f8e')
        axes[1].axhline(1,color='gray',linestyle='--');axes[1].set(ylabel='Sales / local trend',title='Weekday profile after detrending (descriptive)')
        full = monthly[monthly.complete_month]
        axes[2].bar(full.month,full.mean_daily_units,color='#277f8e');axes[2].tick_params(axis='x',rotation=60)
        axes[2].set(ylabel='Mean units per day',title='Complete calendar months; annual seasonality not established')
        save(fig,'seasonality')
        return out / (section+'.png')
    if section == 'price_changes':
        fig, axes = plt.subplots(1,2,figsize=(12,4.5))
        changes = prices.change_pct.dropna()
        axes[0].hist(changes.clip(-100,100),bins=40,color='#277f8e')
        axes[0].set(xlabel='Consecutive-month median price change (%)',ylabel='Product–market comparisons',title='Display clipped to ±100%; CSV retains full values')
        candidates = prices.groupby(['market','sku']).size().sort_values(ascending=False).head(4).index
        for market, sku in candidates:
            group = prices[(prices.market==market)&(prices.sku==sku)]
            axes[1].plot(pd.to_datetime(group.month),100*group.median_price/group.median_price.iloc[0],label=f'{market}: {sku}')
        axes[1].set(title='Four pairs with most qualifying months',ylabel='Price index (first qualifying month = 100)');axes[1].legend(fontsize=7);axes[1].tick_params(axis='x',rotation=35)
        save(fig,'price_changes')
        return out / (section+'.png')
    if section == 'market_returns':
        fig, axes = plt.subplots(1,2,figsize=(12,5))
        top = returns.head(12).sort_values('gross_units')
        axes[0].barh(top.market,top.returned_to_gross_unit_pct,color='#a84931')
        axes[0].set(xlabel='Negative-quantity units / gross outbound units (%)',title='Twelve largest training sales markets')
        axes[1].scatter(returns.gross_units,returns.returned_to_gross_unit_pct,color='#277f8e',alpha=.7)
        axes[1].set_xscale('log');axes[1].set(xlabel='Gross outbound units (log scale)',ylabel='Returned-to-gross units (%)',title='Small denominators can inflate ratios')
        save(fig,'market_returns')
        return out / (section+'.png')
    if section == 'cutoff_sensitivity':
        fig, axes = plt.subplots(1,2,figsize=(11,4))
        axes[0].plot(sensitivity.cutoff,sensitivity.unit_retention_pct,'o-',label='Units')
        axes[0].plot(sensitivity.cutoff,sensitivity.revenue_retention_pct,'s-',label='Revenue');axes[0].legend()
        axes[0].set(ylabel='Retained relative to no cutoff (%)',xlabel='Maximum units per invoice line',title='Cleaning-rule sensitivity: training data')
        axes[1].bar(sensitivity.cutoff,sensitivity.max_daily_units,color='#277f8e')
        axes[1].set(ylabel='Maximum total daily units',xlabel='Maximum units per invoice line',title='Impact on observed demand spikes')
        save(fig,'cutoff_sensitivity')
        return out / (section+'.png')
    raise ValueError('Unknown EDA section: '+section)


def export_eda(tables, evidence, archive, output, train_end):
    """Export previously computed tables, plots and interpretation without rereading data."""
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    prices=tables['monthly_prices'];changes=prices.change_pct.dropna()
    for name, frame in tables.items(): frame.to_csv(out/(name+'.csv'), index=False)
    (out/'seasonality_test.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    for section in ['missing_values','seasonality','price_changes','market_returns','cutoff_sensitivity']:
        plot_eda_section(section,tables,out)
    report = f'''# Extended exploratory data analysis

Missingness covers both original workbook sheets, before cleaning. Customer identifiers are inspected transiently for completeness and immediately discarded; no IDs are exported. All behavioral analyses use only data through {train_end}, across all eligible products and markets, not only the 150-product benchmark cohort. They do not tune or change the published replenishment benchmark.

## 1. Missing values
Full per-sheet and overall counts: [missing_values.csv](missing_values.csv). Missing means null or whitespace; sentinel strings and incorrect-but-present values need separate validation. Missing descriptions do not automatically invalidate a product identifier. Missing customer IDs do not prevent product-level inventory analysis.

![Missingness](missing_values.png)

## 2. Seasonality and trend
The weekday test uses {evidence['complete_weeks']} complete weeks after dividing sales by a centered 28-day moving average. Friedman statistic: {evidence['statistic']:.3f}; p-value: {evidence['p_value']:.3g}; Kendall's W: {evidence['kendalls_w']:.3f}. W is an effect-size summary, not a forecasting score. Centered smoothing is descriptive only and never used as a forecast feature. Serial dependence weakens the nominal p-value interpretation; ordering and closure schedules can create weekday effects.

Monthly means normalize for calendar exposure and omit incomplete months. Training history has fewer than two complete annual cycles; this analysis does not establish annual seasonality. Zero recorded sales are not confirmed zero latent demand.

![Seasonality](seasonality.png)

## 3. Price changes
Monthly transaction-line median selling prices are compared within the same product and market, only for consecutive months with at least five valid sales lines each. There are {len(changes):,} qualifying comparisons; {(changes.abs()>1).mean()*100:.2f}% change by more than 1% in magnitude. Prices can reflect discounts, quantity mix and customer mix; these are not proven list-price changes or causal elasticity estimates. Charts clip the histogram for readability; CSV values remain unmodified.

![Prices](price_changes.png)

## 4. Market returns
Negative-quantity product units are divided by gross positive outbound product units in the same training window, before the bulk-order cutoff. Returns are not linked to original purchases; a ratio can exceed 100%, and cancellation records do not establish physical resale recovery. Invalid or nonproduct lines are excluded. Positive cancellation lines are excluded from sales and are not counted as returned units.

![Returns](market_returns.png)

## 5. Extreme-order sensitivity
Compare maximum invoice-line quantities of 1,000, 5,000, 10,000 and no cap. The table reports excluded rows, retained units/revenue, maximum daily volume and daily coefficient of variation. This measures data sensitivity, not policy-cost or service sensitivity: no alternative-threshold inventory experiment is claimed. The existing 10,000-unit rule remains unchanged.

![Cutoffs](cutoff_sensitivity.png)

For each chart, explain the denominator, time window, business implication and what the data cannot establish. Numerical source tables and `eda_manifest.json` accompany the figures.
'''
    (out/'README.md').write_text(report,encoding='utf-8')
    manifest = dict(train_end=str(train_end), source_sha256=hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
                    eda_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    files_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='eda_manifest.json'})
    (out/'eda_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return tables, evidence
