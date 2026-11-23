"""Time feasibility for fixed orders and fixed lengths of charging events."""
from math import isfinite

from price_ride.domain import Route, Stop
from price_ride.evaluation import EPS


class Timing:
    def __init__(self, instance, nodes, vehicle):
        self.nodes = tuple(instance.node(n) for n in nodes)
        self.ids = nodes
        self.vehicle = vehicle.id
        self.arcs = tuple(instance.travel(i, j) for i, j in zip(nodes, nodes[1:]))
        self.travel = sum(self.arcs)
        self.service = tuple(n.service for n in self.nodes)
        self.lower = tuple(n.earliest for n in self.nodes)
        self.upper = [n.latest for n in self.nodes]
        self.upper[-1] = min(self.upper[-1], instance.horizon-self.service[-1])
        self.rides = []
        self.valid = (nodes[0] == vehicle.origin and nodes[-1] == vehicle.destination and
                      len(set(nodes)) == len(nodes) and isfinite(self.travel))
        req = {r.pickup: r for r in instance.requests}
        pos = {n: i for i, n in enumerate(nodes)}
        load = 0
        for i, node in enumerate(self.nodes):
            load += node.load
            self.valid &= 0 <= load <= vehicle.capacity
            if node.id in req:
                request = req[node.id]
                drop = pos.get(request.dropoff, -1)
                if drop <= i:
                    self.valid = False
                else:
                    self.rides.append((i, drop, request.max_ride, instance.travel(node.id, request.dropoff)))
        self.valid &= load == 0 and sum(n.load < 0 for n in self.nodes) == len(self.rides)
        self.station_indices = tuple(i for i, node in enumerate(self.nodes)
                                     if any(node.id in s.node_ids for s in instance.stations)
                                     and 0 < i < len(self.nodes)-1)

    def _weights(self, charges):
        return tuple(arc+self.service[i]+(charges[i].duration if i in charges else 0)
                     for i, arc in enumerate(self.arcs))

    def bounds(self, charges, fixed=None, latest=True):
        if not self.valid:
            return None
        lower, upper = list(self.lower), list(self.upper)
        for i, t in (fixed or {}).items():
            service_start = t-self.service[i]
            lower[i], upper[i] = max(lower[i], service_start), min(upper[i], service_start)
        weights = self._weights(charges)
        for _ in self.ids:
            changed = False
            for i, elapsed in enumerate(weights):
                after = lower[i]+elapsed
                if after > lower[i+1]+EPS/10:
                    lower[i+1] = after
                    changed = True
            for p, d, ride, _ in self.rides:
                start = lower[d]-ride-self.service[p]
                if start > lower[p]+EPS/10:
                    lower[p] = start
                    changed = True
            if any(a > b+EPS/2 for a, b in zip(lower, upper)):
                return None
            if not changed:
                break
        else:
            return None
        if not latest:
            return lower, upper
        for _ in self.ids:
            changed = False
            for i in reversed(range(len(weights))):
                before = upper[i+1]-weights[i]
                if before < upper[i]-EPS/10:
                    upper[i] = before
                    changed = True
            for p, d, ride, _ in self.rides:
                end = upper[p]+ride+self.service[p]
                if end < upper[d]-EPS/10:
                    upper[d] = end
                    changed = True
            if not changed:
                return lower, upper
        return None

    def schedule(self, charges, fixed=None):
        result = self.bounds(charges, fixed, latest=False)
        if result is None:
            return None
        lower, upper = result
        weights = self._weights(charges)
        # Delaying a pickup while keeping all later starts fixed can only
        # improve that pickup's own ride. Sweep backwards to reuse any slack.
        for p, _, _, _ in reversed(self.rides):
            lower[p] = max(lower[p], min(upper[p], lower[p+1]-weights[p]))
        excess = sum(lower[d]-lower[p]-self.service[p]-direct for p, d, _, direct in self.rides)
        return (Route(self.vehicle, tuple(Stop(n, t, charge=charges.get(i))
                                          for i, (n, t) in enumerate(zip(self.ids, lower)))), excess)

    def window(self, i, bounds):
        return bounds[0][i]+self.service[i], bounds[1][i]+self.service[i]
