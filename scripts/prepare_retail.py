"""Cache original UCI source and auditable cleaned transactions."""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from retail_planner.data import acquire,clean_transactions
cache=root/'data/cache';archive=acquire(cache);data,audit=clean_transactions(archive,cache)
print(audit)
