"""Dataset-first, independently runnable EDA cells for the Colab generator."""


def append_eda_cells(md, code):
    md('''## 2.1 First, look at the original dataset

Run this cell before cleaning anything. Each row is a product line on an invoice, not an entire customer order. The preview shows original values with source column names. Customer IDs are omitted from the preview and modeling; only their aggregate missing-value counts are retained. Loading both Excel sheets can take a few minutes.

**Look for:** the product, units, selling price, transaction time and destination country. A country is a sales market, not an observed warehouse.''')
    code('''from retail_planner.data import acquire,clean_transactions,prepare,sql_store
from retail_planner.eda import load_raw,sale_mask,product_mask,seasonality,price_changes,return_rates,cutoff_sensitivity,plot_eda_section,export_eda
archive=acquire('data/cache')
raw,missing=load_raw(archive,'data/cache')
source_names={'invoice':'Invoice','sku':'StockCode','description':'Description','quantity':'Quantity','timestamp':'InvoiceDate','price':'Price','market':'Country'}
print(f'Original rows: {len(raw):,}; original workbook columns: {missing.loc[missing.sheet.eq("ALL")].shape[0]}')
print('First 10 original transaction lines (before cleaning):')
display(raw[list(source_names)].head(10).rename(columns=source_names))''')
    md('''## 2.2 Understand the columns and basic ranges

Inspect data types, coverage, distinct products and markets, and numeric ranges. The loader standardizes identifier strings and adds a parsed `date`, but has not removed transaction rows. Negative quantities and zero prices should prompt investigation, not immediate averaging into demand.''')
    code('''display(pd.DataFrame({'field':list(source_names.values()),'meaning':['Invoice identifier','Product/SKU identifier','Product description','Units on this invoice line','Transaction timestamp','Unit selling price in GBP','Destination market']}))
display(raw[list(source_names)].dtypes.astype(str).rename('loaded_dtype').to_frame())
display(pd.Series({'first_date':raw.date.min(),'last_date':raw.date.max(),'distinct_product_codes':raw.sku.nunique(),'distinct_markets':raw.market.nunique(),'rows':len(raw)}))
display(raw[['quantity','price']].describe(percentiles=[.01,.5,.95,.99]))''')
    md('''## 2.3 Check missing values, then draw the chart

Counts come from every original workbook column, before cleaning, for each sheet and overall. Missing means null or blank text. Customer-ID missingness matters for customer analytics, but the inventory pipeline uses product and market identifiers.

**Read the chart:** bar length is the percentage missing, not the number of rows removed. A present value can still be invalid.''')
    code('''eda_out=out/'eda'
eda_tables={'missing_values':missing}
display(missing.query("sheet == 'ALL'")[['field','rows','missing','missing_pct']])
display(missing.query("sheet != 'ALL'")[['sheet','field','missing','missing_pct']])
display(Image(filename=str(plot_eda_section('missing_values',eda_tables,eda_out))))''')
    md('''## 2.4 Inspect suspicious records before cleaning

Separate cancellations, negative quantities, nonpositive prices and nonproduct codes. These flags overlap. Repeated lines are counted but retained because no invoice-line ID proves an accidental duplicate. Examples below are restricted to the training period; later dates remain reserved for evaluation.''')
    code('''training_raw=raw.loc[raw.date<=c.train_end].copy()
flags=pd.Series({
    'cancel_invoice_prefix':training_raw.invoice.str.upper().str.startswith('C').fillna(False).sum(),
    'negative_quantity':(training_raw.quantity<0).sum(),
    'zero_quantity':(training_raw.quantity==0).sum(),
    'nonpositive_price':(training_raw.price<=0).sum(),
    'nonproduct_code':(~product_mask(training_raw)).sum(),
    'repeated_loaded_lines':training_raw.duplicated().sum(),
    'quantity_above_10000':(training_raw.quantity>10000).sum()})
display(flags.rename('training_rows_flagged').to_frame())
display(training_raw.loc[training_raw.quantity<0,list(source_names)].head(5))
display(training_raw.loc[training_raw.quantity>10000,list(source_names)].head(5))''')
    md('''## 2.5 Clean the sales data and compare before/after

Positive outbound sales are the demand proxy. Exclude cancellations, invalid dates, nonproduct codes, nonpositive quantities/prices and lines above 10,000 units. Keep repeated lines. Returns are analyzed separately, not subtracted from future demand. The audit below covers the whole workbook; the next analysis cells use only training dates.

**Check:** the number of remaining rows, the first cleaned records, and the documented reasons for removal.''')
    code('''transactions,audit=clean_transactions(archive,'data/cache')
display(pd.DataFrame({'stage':['Original','Cleaned'],'rows':[len(raw),len(transactions)]}))
display(pd.Series(audit))
display(transactions[['date','sku','description','quantity','price','market','revenue']].head(10))
eda_sales=training_raw.loc[sale_mask(training_raw)&(training_raw.quantity<=10000)].copy()
print('Behavioral EDA ends at:',c.train_end,'; training sales lines:',len(eda_sales))''')
    md('''## 2.6 Plot daily sales and the underlying trend

Aggregate units by calendar day and include days with zero recorded sales. The 28-day centered average is a descriptive smoother, not a forecast feature. This analysis covers all eligible training products, not just the later selected cohort.

**Read the chart:** isolated spikes may be bulk orders; a sustained rise may reflect trend or seasonality. Zero sales do not prove zero latent demand.''')
    code('''import matplotlib.pyplot as plt
daily,weekly,monthly,seasonality_evidence=seasonality(eda_sales,c.train_end)
eda_tables.update(seasonal_daily=daily,weekday_profile=weekly,monthly_profile=monthly)
display(daily[['date','units','trend_28d']].head(10))
fig,ax=plt.subplots(figsize=(12,4))
ax.plot(daily.date,daily.units,alpha=.45,label='Daily units')
ax.plot(daily.date,daily.trend_28d,color='#a84931',label='28-day centered mean')
ax.set(title='Training-period sales and trend',xlabel='Date',ylabel='Units');ax.legend()
fig.tight_layout();fig.savefig(eda_out/'daily_trend.png',dpi=140)
display(Image(filename=str(eda_out/'daily_trend.png')));plt.close(fig)''')
    md('''## 2.7 Examine weekday seasonality

Compare sales relative to their local trend across weekdays. The Friedman test compares weekdays within complete weeks; Kendall's W summarizes effect size. Serial dependence and business opening schedules limit interpretation of the nominal p-value.

**Read the chart:** 1 means sales equal the local daily trend. A weekday effect does not prove that consumer preferences caused it.''')
    code('''display(weekly)
display(pd.Series(seasonality_evidence))
fig,ax=plt.subplots(figsize=(9,4))
ax.bar(['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],weekly.mean_relative_units,color='#277f8e')
ax.axhline(1,color='gray',linestyle='--')
ax.set(title='Weekday sales relative to local trend',ylabel='Sales / 28-day trend',xlabel='Weekday')
fig.tight_layout();fig.savefig(eda_out/'weekday_pattern.png',dpi=140)
display(Image(filename=str(eda_out/'weekday_pattern.png')));plt.close(fig)''')
    md('''## 2.8 Examine monthly patterns

Compare average units per calendar day, rather than unequal monthly totals. Only complete months enter the plot. The training data contains fewer than two full annual cycles, so this chart alone cannot establish repeatable annual seasonality.

**Look for:** the months with the largest mean daily sales, then distinguish a descriptive peak from evidence that it will repeat.''')
    code('''display(monthly)
complete_months=monthly.loc[monthly.complete_month]
fig,ax=plt.subplots(figsize=(11,4))
ax.bar(complete_months.month,complete_months.mean_daily_units,color='#277f8e')
ax.tick_params(axis='x',rotation=60)
ax.set(title='Monthly sales patterns: complete training months',ylabel='Mean units per calendar day',xlabel='Month')
fig.tight_layout();fig.savefig(eda_out/'monthly_pattern.png',dpi=140)
display(Image(filename=str(eda_out/'monthly_pattern.png')));plt.close(fig)''')
    md('''## 2.9 Analyze selling-price changes

Calculate the median selling price within each product, market and month. Compare consecutive months only when each has at least five sales lines. This controls product/market composition, but not customer or bulk-discount mix.

**Read the plots:** the histogram shows the distribution of monthly changes; the lines index example prices to 100 in their first qualifying month. These are not estimates of price elasticity.''')
    code('''prices=price_changes(eda_sales)
eda_tables['monthly_prices']=prices
display(prices.loc[prices.change_pct.notna()].head(10))
display(prices.change_pct.dropna().describe())
print('Comparisons changing by more than 1%:',f'{100*prices.change_pct.dropna().abs().gt(1).mean():.2f}%')
display(Image(filename=str(plot_eda_section('price_changes',eda_tables,eda_out))))''')
    md('''## 2.10 Compare market return ratios

Use the training records before the bulk cutoff. Divide negative-quantity product units by gross positive outbound units in each market. Returns are not linked to their original purchases; this is not the probability of returning an order.

**Read the plots:** inspect both the ratio and its sales-volume denominator. Investigate large cancellations before attributing a high ratio to market quality.''')
    code('''returns=return_rates(training_raw)
eda_tables['market_returns']=returns
display(returns.head(12))
display(Image(filename=str(plot_eda_section('market_returns',eda_tables,eda_out))))''')
    md('''## 2.11 Test the extreme-order cutoff

Compare maximum line quantities of 1,000, 5,000, 10,000 and no cutoff using the same training history. Measure how much recorded volume and revenue each rule retains and how it changes the biggest daily spike.

**Read the plots:** removing few rows can still remove substantial units. This is data sensitivity, not a rerun of the inventory policies; the existing 10,000-unit rule remains fixed.''')
    code('''cutoffs=cutoff_sensitivity(training_raw,c.train_end)
eda_tables['cutoff_sensitivity']=cutoffs
display(cutoffs)
display(Image(filename=str(plot_eda_section('cutoff_sensitivity',eda_tables,eda_out))))''')
    md('''## 2.12 Save the EDA and connect it to planning

Export the tables and figures already calculated above. No second raw-data read or analysis run is required. Before continuing, explain one finding about data quality, one about demand, and one limitation. Next, select the modeling cohort and build the SQL tables.''')
    code('''export_eda(eda_tables,seasonality_evidence,archive,eda_out,c.train_end)
print('Saved EDA report:',eda_out/'README.md')
display(pd.DataFrame({'finding':['Missing customer IDs','Intermittent/variable demand','Weekday effects','Changing transaction prices','Extreme quantities'],
    'planning_implication':['Use SKU/market aggregation; avoid unsupported customer conclusions','Compare intermittent methods and uncertainty buffers','Test calendar-aware forecasts; inspect opening schedules','Separate selling-price evidence from assumed acquisition costs','Document cutoff sensitivity before interpreting shortages']}))
del raw,training_raw,eda_sales''')
