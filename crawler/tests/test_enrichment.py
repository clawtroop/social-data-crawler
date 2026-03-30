from __future__ import annotations

import pytest

from crawler.enrich.field_groups import supported_field_groups
from crawler.enrich.orchestrator import initialize_enrichment_envelope, route_enrichment


def test_supported_field_groups_include_core_agent_use_cases() -> None:
    assert {"summaries", "classifications", "linkables"} <= set(supported_field_groups())


def test_initialize_enrichment_envelope_preserves_metadata() -> None:
    envelope = initialize_enrichment_envelope(
        mode="full",
        field_groups=("summaries", "linkables"),
    )
    assert envelope["mode"] == "full"
    assert envelope["status"] == "pending"
    assert envelope["field_groups"] == ["summaries", "linkables"]
    assert envelope["generated_fields"] == {}
    assert envelope["confidence"] == {}
    assert envelope["evidence"] == {}
    assert envelope["source_fields"] == {}
    assert envelope["unsupported_reason"] == {}


def test_route_enrichment_raises_for_generative_groups_in_legacy_pipeline() -> None:
    """Legacy orchestrator raises ValueError for generative groups — use new pipeline instead."""
    with pytest.raises(ValueError, match="AI configuration required for generative field group 'summaries'"):
        route_enrichment(
            {
                "platform": "wikipedia",
                "title": "Artificial intelligence",
                "summary": "Artificial intelligence is a field of computer science.",
            },
            field_groups=("summaries",),
        )


def test_route_enrichment_keeps_extractive_groups_and_reports_unknown_groups() -> None:
    envelope = route_enrichment(
        {
            "platform": "wikipedia",
            "resource_type": "article",
            "canonical_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
        },
        field_groups=("classifications", "imaginary"),
    )

    assert envelope["status"] == "routed"
    assert envelope["field_groups"] == ["classifications", "imaginary"]
    assert "classifications" in envelope["generated_fields"]
    assert envelope["unsupported_reason"]["imaginary"] == "unsupported field group"
