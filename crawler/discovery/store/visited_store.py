from __future__ import annotations

from crawler.discovery.state.visited import VisitRecord


class InMemoryVisitedStore:
    def __init__(self) -> None:
        self.records: dict[str, VisitRecord] = {}

    def put(self, record: VisitRecord) -> VisitRecord:
        self.records[record.url_key] = record
        return record

    def get(self, url_key: str) -> VisitRecord | None:
        return self.records.get(url_key)

    def list(self) -> list[VisitRecord]:
        return list(self.records.values())
