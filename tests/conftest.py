from dataclasses import replace

import pytest

from price_ride.domain import ChargingStation, Instance, Node, Objective, Request, TimeSeries, Vehicle


@pytest.fixture
def tiny():
    """Hand-built test fixture in benchmark units."""
    nodes = tuple(Node(i, 41.0+i/1000, -8.5, {1: 3, 2: 1}.get(i, 0),
                       {1: 1, 2: -1}.get(i, 0), 0, 1440) for i in range(1, 9))
    zero = {(3, 5), (4, 6)}
    matrix = tuple(tuple(0.0 if i == j or (i, j) in zero else 2.0
                         for j in range(1, 9)) for i in range(1, 9))
    grid = (0.2, 0.4) + (0.3,)*94
    station = ChargingStation(7, (7,), 0.5, 1, (1.0,) + (0.0,)*95, (0.1,)*96)
    return Instance("tiny", "synthetic test only", "", 1440, (1, 1), (3, 5), nodes,
                    (Request(1, 1, 2, 60),), (Vehicle(1, 3, 5, 4, 10, 15, 0.4),
                                             Vehicle(2, 4, 6, 4, 10, 15, 0.4)),
                    (station, replace(station, id=8, node_ids=(8,))), TimeSeries(15, grid),
                    0.5, Objective((.75, .25), .36, .31), matrix)
