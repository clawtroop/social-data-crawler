from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from crawler.discovery.contracts import DiscoveryCandidate, DiscoveryRecord


class BaseDiscoveryAdapter(ABC):
    platform: str
    supported_resource_types: tuple[str, ...]

    @abstractmethod
    def can_handle_url(self, url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def build_seed_records(self, input_record: dict[str, Any]) -> list[DiscoveryRecord]:
        raise NotImplementedError

    @abstractmethod
    async def map(self, seed: DiscoveryRecord, context: dict[str, Any]) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def crawl(self, candidate: DiscoveryCandidate, context: dict[str, Any]) -> Any:
        raise NotImplementedError
