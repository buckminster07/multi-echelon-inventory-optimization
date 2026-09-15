# Publish this repository on GitHub

Extract the ZIP, then open a terminal in the extracted project folder.
The archive contains the complete source tree, including `.github/workflows`.
It contains no Git history or credentials.

1. Create an empty GitHub repository named `multi-echelon-inventory-optimization`.
   Choose visibility yourself; do not auto-add another README or license.
2. Run the commands below, replacing YOUR_USERNAME with your GitHub username:

```bash
git init -b main
git add .
git commit -m "Add reproducible multi-echelon inventory decision experiment"
git remote add origin https://github.com/YOUR_USERNAME/multi-echelon-inventory-optimization.git
git push -u origin main
```

Authenticate through your normal GitHub credential manager or GitHub CLI.
Never paste tokens into README files or commit them.

Suggested description:

> SQL-driven inventory analysis and Stockpyl optimization with paired scenario
> benchmarking, service metrics and reproducible synthetic experiments.

Suggested topics: `inventory-optimization`, `supply-chain`, `operations-research`,
`data-analytics`, `sql`, `stockpyl`, `simulation`, `python`.

Pin the repository on your profile. Keep the generated example figure and
results visible. Check the Actions tab after pushing; the workflow is provided,
but a green GitHub CI status should be claimed only after it actually runs.

Before describing the project in an interview, reproduce the example and be
ready to explain the baseline, shortage metric, test-seed separation, cost/service
trade-off and fixed-lead-time limitation. Use actual implementation dates and
credit Stockpyl. Do not present these synthetic results as company savings.
