# Data card and reuse

**Source:** Chen, D. (2012). *Online Retail II*. UCI Machine Learning Repository. DOI: https://doi.org/10.24432/C5CG6D. Original download: https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip.

**License:** [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). Repository source code is MIT; source and derived dataset records retain their separate CC BY 4.0 attribution requirements. The original workbook is downloaded on demand and is not committed to GitHub. The pipeline's aggregate result tables describe transformations and cite the source.

**Coverage:** two workbook sheets, 1,067,371 transaction rows from 1 December 2009 through 9 December 2011. A UK-based online giftware retailer with many wholesale customers. Customer country identifies a market; it is not a warehouse identifier.

**Modeling columns:** Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Country. Customer ID is omitted from modeling. The separate full-column missingness audit transiently reads the original workbook including Customer ID, computes aggregate completeness counts, and discards identifiers without exporting them. The modeled cohort ends at 30 November 2011 to avoid the final partial December period.

**Extended EDA:** [charts, tables and interpretation](../examples/retail/eda/README.md) cover missing values, weekday/monthly patterns, transaction-price changes, market returns and cutoff sensitivity. All behavioral analyses use dates through April 2011, across eligible source products and markets; missingness alone covers the complete original workbook. These additions do not change the prior benchmark or its fixed cleaning rule.

**Observed:** positive sale quantities, product codes, dates, selling prices and destination countries. **Derived:** daily panels, training-only product/market selection, ABC/XYZ/ADI, forecasts and errors. **Assumed:** network, inventory, supplier lead times, pack/MOQ, capacity, budgets, acquisition costs, operating charges and demand-spike mechanisms. **Unknown:** actual latent demand, stockout history, availability, actual supplier purchase prices and true historical fulfillment service.

Cleaning audits report overlapping diagnostics; their counts are not mutually exclusive rows of a reconciliation. Exact repeated loaded lines are retained because source line identities are absent. Cancellation/return quantities are not subtracted from outbound demand. Nonproduct codes, nonpositive amounts, invalid dates and lines over 10,000 units are excluded. No in-stock claim is inferred from an observed zero.

Initial cohort selection excludes products with fewer than thirty training sales dates and inactive product-market pairs with fewer than three training invoice lines. This can remove new or niche products and privileges established items. The study does not establish performance across the full retailer catalog or a contemporary retailer without new validation.

Raw source SHA-256 is recorded in every execution manifest. The executed original ZIP hash is `572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb`. If the remote content changes, compare the new hash and audit before treating results as a reproduction. Source-file hashes, configuration, dependency versions and seeds accompany results.
