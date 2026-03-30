from __future__ import annotations

import asyncio
from typing import Any, Callable

from crawler.enrich.models import EnrichedRecord


class BatchEnrichmentExecutor:
    """Execute enrichment across many records with controlled concurrency."""

    def __init__(
        self,
        pipeline: Any,  # EnrichPipeline - forward ref to avoid circular import
        max_concurrency: int = 10,
        batch_size: int = 50,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.max_concurrency = max_concurrency
        self.batch_size = batch_size
        self.on_progress = on_progress

    async def execute_batch(
        self,
        records: list[dict[str, Any]],
        field_groups: list[str],
    ) -> list[EnrichedRecord]:
        """Enrich all records in batches with bounded concurrency."""
        results: list[EnrichedRecord] = []
        total = len(records)
        completed = 0

        for batch_start in range(0, total, self.batch_size):
            batch = records[batch_start : batch_start + self.batch_size]
            semaphore = asyncio.Semaphore(self.max_concurrency)

            async def _enrich_one(record: dict[str, Any]) -> EnrichedRecord:
                async with semaphore:
                    return await self.pipeline.enrich(record, field_groups)

            batch_results = await asyncio.gather(
                *[_enrich_one(rec) for rec in batch],
                return_exceptions=True,
            )

            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    rec = batch[i]
                    results.append(
                        EnrichedRecord(
                            doc_id=rec.get("doc_id", f"error-{batch_start + i}"),
                            source_url=rec.get("canonical_url", ""),
                            platform=rec.get("platform", "unknown"),
                            resource_type=rec.get("resource_type", "unknown"),
                        )
                    )
                else:
                    results.append(result)

                completed += 1
                if self.on_progress:
                    self.on_progress(completed, total)

        return results

    async def execute_single(
        self,
        record: dict[str, Any],
        field_groups: list[str],
    ) -> EnrichedRecord:
        """Enrich a single record."""
        return await self.pipeline.enrich(record, field_groups)
