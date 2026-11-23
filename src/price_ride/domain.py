"""Immutable model, explicit schedule and evaluator outputs. Times are in minutes."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Node:
    id: int
    latitude: float
    longitude: float
    service: float
    load: int
    earliest: float
    latest: float


@dataclass(frozen=True, slots=True)
class Request:
    id: int
    pickup: int
    dropoff: int
    max_ride: float


@dataclass(frozen=True, slots=True)
class Vehicle:
    id: int
    origin: int
    destination: int
    capacity: int
    initial_kwh: float
    battery_kwh: float
    final_ratio: float


@dataclass(frozen=True, slots=True)
class ChargingStation:
    id: int
    node_ids: tuple[int, ...]
    rate: float
    max_visits: int
    surplus: tuple[float, ...]
    mmr: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class TimeSeries:
    minutes_per_period: float
    grid: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Objective:
    legacy_weights: tuple[float, float]
    travel_eur_per_min: float
    excess_eur_per_min: float


@dataclass(frozen=True, slots=True)
class Instance:
    name: str
    source: str
    sha256: str
    horizon: float
    depot_counts: tuple[int, int]
    common_depots: tuple[int, int]
    nodes: tuple[Node, ...]
    requests: tuple[Request, ...]
    vehicles: tuple[Vehicle, ...]
    stations: tuple[ChargingStation, ...]
    electricity: TimeSeries
    consumption: float
    objective: Objective
    matrix: tuple[tuple[float, ...], ...]

    def node(self, node_id: int) -> Node:
        if type(node_id) is not int or not 1 <= node_id <= len(self.nodes):
            raise ValueError(f"unknown node {node_id!r}")
        return self.nodes[node_id - 1]

    def travel(self, origin: int, destination: int) -> float:
        return self.matrix[origin - 1][destination - 1]


@dataclass(frozen=True, slots=True)
class ChargeEvent:
    duration: float
    kwh: float
    wait_before: float = 0.0


@dataclass(frozen=True, slots=True)
class Stop:
    node: int
    service_start: float | None = None
    wait_after: float = 0.0
    charge: ChargeEvent | None = None


@dataclass(frozen=True, slots=True)
class Route:
    vehicle: int
    stops: tuple[Stop, ...]


@dataclass(frozen=True, slots=True)
class Schedule:
    routes: tuple[Route, ...]


@dataclass(frozen=True, slots=True)
class Violation:
    code: str
    explanation: str
    vehicle: int | None = None
    request: int | None = None
    stop: int | None = None
    magnitude: float | None = None


@dataclass(frozen=True, slots=True)
class StopState:
    node: int
    arrival: float
    service_start: float
    departure: float
    load: int
    arrival_kwh: float
    departure_kwh: float
    passengers: tuple[int, ...]
    slack_minutes: float


@dataclass(frozen=True, slots=True)
class Ride:
    request: int
    vehicle: int
    pickup_complete: float
    dropoff_start: float
    minutes: float
    excess_minutes: float


@dataclass(frozen=True, slots=True)
class ChargeAllocation:
    station: int
    period: int
    vehicle: int
    stop: int
    start: float
    end: float
    grid_kwh: float
    lec_kwh: float
    cost_eur: float


@dataclass(frozen=True, slots=True)
class VehicleState:
    vehicle: int
    stops: tuple[StopState, ...]
    initial_kwh: float
    final_kwh: float
    minimum_kwh: float
    station_visits: tuple[int, ...]
    within_horizon: bool


@dataclass(frozen=True, slots=True)
class Metrics:
    travel_minutes: float
    excess_ride_minutes: float
    service_minutes: float
    waiting_minutes: float
    charging_minutes: float
    charged_kwh: float
    grid_kwh: float
    lec_kwh: float
    travel_eur: float
    user_eur: float
    energy_eur: float
    objective_eur: float
    legacy_weighted_minutes: float


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    feasible: bool
    violations: tuple[Violation, ...]
    vehicles: tuple[VehicleState, ...]
    rides: tuple[Ride, ...]
    allocations: tuple[ChargeAllocation, ...]
    metrics: Metrics
