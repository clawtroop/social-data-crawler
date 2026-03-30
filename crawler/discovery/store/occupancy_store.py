from __future__ import annotations

from crawler.discovery.state.occupancy import OccupancyLease


class InMemoryOccupancyStore:
    def __init__(self) -> None:
        self.leases: dict[str, OccupancyLease] = {}

    def put(self, lease: OccupancyLease) -> OccupancyLease:
        self.leases[lease.lease_id] = lease
        return lease

    def get(self, lease_id: str) -> OccupancyLease | None:
        return self.leases.get(lease_id)

    def list(self) -> list[OccupancyLease]:
        return list(self.leases.values())
