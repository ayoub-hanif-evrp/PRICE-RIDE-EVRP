"""Input interfaces for a later synthetic transfer study."""
from dataclasses import dataclass
from typing import Protocol

from price_ride.domain import Node, Request, TimeSeries


@dataclass(frozen=True)
class AssumedStationSite:
    osm_node: int
    rate_kwh_per_minute: float
    scenario_source: str


class SyntheticDemand(Protocol):
    def generate(self, seed: int) -> tuple[tuple[Node, ...], tuple[Request, ...]]:
        """Produce scenario passenger nodes and request pairs."""


class TariffScenario(Protocol):
    def daily_profile(self) -> TimeSeries:
        """Return a dated, attributed scenario electricity price profile."""
