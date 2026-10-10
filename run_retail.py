import argparse
from retail_planner.config import Config
from retail_planner.pipeline import run
if __name__=='__main__':
    p=argparse.ArgumentParser(description='Real-data retail planning pipeline')
    p.add_argument('--profile',choices=['quick','full'],default='quick')
    p.add_argument('--output',default='outputs/retail-run')
    p.add_argument('--cache',default='data/cache')
    a=p.parse_args();run(Config.quick() if a.profile=='quick' else Config(),a.output,a.cache)
