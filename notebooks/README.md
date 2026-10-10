# Colab workflows

Start with **`02_real_retail_planning.ipynb`** for the complete real-data workflow. It downloads UCI Online Retail II, performs cleaning and SQL integration, trains and evaluates forecasts, tunes stock targets, runs the constrained simulation, opens the planner and exports results/audit files.

`01_inventory_decisions.ipynb` retains the earlier synthetic experiment as a smaller inventory-theory reference. Its results and assumptions are separate from the real-data workflow.

The new notebook defaults to the quick profile for the first successful run. Set `PROFILE='full'` for the published cohort. Runtime and Colab resource availability vary. Export the ZIP before disconnecting; rerun the export cell after making additional planner decisions.
