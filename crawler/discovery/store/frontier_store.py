from __future__ import annotations

from dataclasses import replace

from crawler.discovery.state.frontier import FrontierEntry, FrontierStatus


class InMemoryFrontierStore:
    def __init__(self) -> None:
        self.entries: dict[str, FrontierEntry] = {}

    def put(self, entry: FrontierEntry) -> FrontierEntry:
        self.entries[entry.frontier_id] = entry
        return entry

    def get(self, frontier_id: str) -> FrontierEntry | None:
        return self.entries.get(frontier_id)

    def list(self) -> list[FrontierEntry]:
        return list(self.entries.values())

    def list_queued(self) -> list[FrontierEntry]:
        return [entry for entry in self.entries.values() if entry.status is FrontierStatus.QUEUED]

    def lease(self, frontier_id: str) -> FrontierEntry | None:
        entry = self.entries.get(frontier_id)
        if entry is None or entry.status is not FrontierStatus.QUEUED:
            return None
        leased = replace(entry, status=FrontierStatus.LEASED, attempt=entry.attempt + 1)
        self.entries[frontier_id] = leased
        return leased
