import numpy as np
import pytest
from inventory_lab.simulator import Network, simulate


def net(lead=(1,)):
    return Network(
        (0, 1),
        (1,),
        (0,),
        {1: 0},
        {0: 0.3, 1: 1},
        10,
        {0: np.array(lead), 1: np.array([1])},
    )


def test_deterministic_accounting_against_hand_calculation():
    m, counts, trace = simulate(
        net(), {0: 10, 1: 5}, {1: np.array([3] * 10)}, record=True
    )
    assert m["fill_rate"] == 1 and m["cost_per_day"] == pytest.approx(4.1)
    assert all(r["on_hand"] == 9 and r["backlog"] == 0 for r in trace)
    assert counts[1] == (30, 30)


def test_zero_stock_immediate_shortages_not_later_fulfillment():
    m, _, _ = simulate(net(), {0: 0, 1: 0}, {1: np.array([3] * 10)})
    assert m["immediate_units"] == 0 and m["shortage_units"] == m["demand_units"] == 30
    assert m["backlog_unit_days"] > 0


def test_warmup_excluded_from_counts():
    m, _, trace = simulate(
        net(), {0: 100, 1: 100}, {1: np.array([10, 10, 1, 2, 3])}, warmup=2, record=True
    )
    assert m["demand_units"] == 6 and len(trace) == 3 and trace[0]["day"] == 0


def test_zero_demand_has_defined_service_and_no_backlog():
    m, _, _ = simulate(net(), {0: 2, 1: 2}, {1: np.zeros(10, dtype=int)})
    assert m["fill_rate"] == 1 and m["backlog_unit_days"] == 0
    assert m["cost_per_day"] == pytest.approx(2.6)


def test_stochastic_simulation_reproducible():
    args = (net((1, 2, 4)), {0: 10, 1: 5}, {1: np.array([3] * 40)})
    assert simulate(*args, seed=17, record=True) == simulate(
        *args, seed=17, record=True
    )
    assert simulate(*args, seed=17, record=True) != simulate(
        *args, seed=18, record=True
    )


def test_supplier_delay_changes_physical_results():
    args = (net(), {0: 6, 1: 4}, {1: np.array([3] * 40)})
    a = simulate(*args, warmup=10)[0]
    b = simulate(*args, warmup=10, supplier_delay=5)[0]
    assert b["backlog_unit_days"] > a["backlog_unit_days"]


@pytest.mark.parametrize("bad", [[-1, 2], [1.5, 2]])
def test_invalid_demand_rejected(bad):
    with pytest.raises(ValueError, match="demand"):
        simulate(net(), {0: 10, 1: 5}, {1: np.array(bad)})
