"""Enrichment orchestrator - legacy interface.

This module provides backward-compatible functions for the legacy
dispatcher pipeline. Generative field groups raise ValueError because
the legacy pipeline does not support agent-delegated enrichment.

For new code, use EnrichPipeline directly — generative groups return
``pending_agent`` instead of raising.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from crawler.enrich.schemas.field_group_registry import get_field_group_spec
from crawler.enrich.templates import get_field_group_template, route_field_group


def initialize_enrichment_envelope(
    mode: str,
    model: str = "",
    field_groups: Sequence[str] | None = None,
    model_config: Mapping[str, Any] | None = None,
) -> dict:
    """Initialize an enrichment result envelope."""
    return {
        "status": "pending",
        "mode": mode,
        "field_groups": list(field_groups or []),
        "generated_fields": {},
        "evidence": {},
        "confidence": {},
        "source_fields": {},
        "unsupported_reason": {},
        "model": model,
        "model_config": dict(model_config or {}),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def route_enrichment(
    record: Mapping[str, Any],
    field_groups: Sequence[str] | None = None,
    model_config: Mapping[str, Any] | None = None,
    mode: str = "planned",
) -> dict:
    """Route enrichment through field groups (legacy interface).

    Extractive groups are executed locally. Generative groups raise
    ValueError — use the new pipeline for agent-delegated generative
    enrichment.
    """
    requested_field_groups = list(field_groups or [])
    envelope = initialize_enrichment_envelope(
        mode=mode,
        field_groups=requested_field_groups,
        model_config=model_config,
    )
    envelope["status"] = "routed"

    for field_group in requested_field_groups:
        routed = route_field_group(field_group, record)
        if routed["unsupported_reason"] == "unsupported field group":
            envelope["unsupported_reason"][field_group] = routed["unsupported_reason"]
            continue

        spec = get_field_group_spec(field_group)
        if spec is not None and spec.strategy in {"generative_only", "extractive_then_generative"}:
            raise ValueError(
                f"AI configuration required for generative field group '{field_group}'. "
                "Use the new pipeline (default) which delegates to the agent."
            )

        if routed["unsupported_reason"] is not None:
            envelope["unsupported_reason"][field_group] = routed["unsupported_reason"]
        envelope["generated_fields"][field_group] = routed["generated_fields"]
        envelope["confidence"][field_group] = routed["confidence"]
        envelope["evidence"][field_group] = routed["evidence"]
        envelope["source_fields"][field_group] = routed["source_fields"]

    return envelope
