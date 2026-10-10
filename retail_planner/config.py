from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Config:
    sku_count:int=150
    market_count:int=6
    seed:int=73
    replications:int=20
    tune_replications:int=3
    max_ml_rows:int=160000
    train_end:str='2011-04-30'
    selection_end:str='2011-05-31'
    calibration_end:str='2011-07-31'
    tuning_end:str='2011-08-31'
    validation_end:str='2011-09-30'
    test_end:str='2011-11-30'
    forecast_horizon:int=21
    service_target:float=.95
    acquisition_fraction:float=.45
    annual_holding_rate:float=.25
    pack:int=6
    moq:int=12
    supplier_order_fee:float=8.
    transfer_order_fee:float=2.
    freight_fraction:float=.04
    store_capacity_days:int=35
    dc_capacity_days:int=45
    budget_days:float=4.
    def __post_init__(self):
        if not 1<=self.sku_count<=250:raise ValueError('Use 1–250 products with the categorical boosting configuration')
        if self.market_count<1 or self.replications<2:raise ValueError('Require markets and at least two evaluation replications')
        if self.forecast_horizon<21:raise ValueError('Need 21 forecast days to support weekly publication and protection intervals')
    @classmethod
    def quick(cls):return cls(sku_count=24,market_count=3,replications=5,tune_replications=1,max_ml_rows=45000)
    def dict(self):return asdict(self)
