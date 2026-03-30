from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from crawler.discovery.state.frontier import FrontierEntry, FrontierStatus


class InMemoryFrontierStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self.entries: dict[str, FrontierEntry] = {}
        self._load()

    def put(self, entry: FrontierEntry) -> FrontierEntry:
        self.entries[entry.frontier_id] = entry
        self._save()
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
        self._save()
        return leased

    def mark_done(self, frontier_id: str) -> FrontierEntry | None:
        entry = self.entries.get(frontier_id)
        if entry is None:
            return None
        done = replace(entry, status=FrontierStatus.DONE)
        self.entries[frontier_id] = done
        self._save()
        return done

    def has(self, frontier_id: str) -> bool:
        return frontier_id in self.entries

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        for item in payload:
            item["status"] = FrontierStatus(item["status"])
            entry = FrontierEntry(**item)
            self.entries[entry.frontier_id] = entry

    def _save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(entry) for entry in self.entries.values()]
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
