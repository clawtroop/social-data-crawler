from __future__ import annotations

from datetime import datetime, timezone

from crawler.discovery.state.frontier import FrontierEntry, FrontierStatus
from crawler.discovery.state.occupancy import OccupancyLease
from crawler.discovery.store.frontier_store import InMemoryFrontierStore
from crawler.discovery.store.occupancy_store import InMemoryOccupancyStore


class DiscoveryScheduler:
    def __init__(
        self,
        frontier_store: InMemoryFrontierStore | None = None,
        occupancy_store: InMemoryOccupancyStore | None = None,
    ) -> None:
        self.frontier_store = frontier_store or InMemoryFrontierStore()
        self.occupancy_store = occupancy_store or InMemoryOccupancyStore()

    def enqueue(self, entry: FrontierEntry) -> FrontierEntry:
        return self.frontier_store.put(entry)

    def lease_next(self, worker_id: str) -> FrontierEntry | None:
        queued = self.frontier_store.list_queued()
        if not queued:
            return None

        entry = max(queued, key=lambda item: item.priority)
        leased = self.frontier_store.lease(entry.frontier_id)
        if leased is None:
            return None

        lease = OccupancyLease(
            lease_id=f"{leased.frontier_id}:{worker_id}",
            job_id=leased.job_id,
            frontier_id=leased.frontier_id,
            worker_id=worker_id,
            leased_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        )
        self.occupancy_store.put(lease)
        return leased
