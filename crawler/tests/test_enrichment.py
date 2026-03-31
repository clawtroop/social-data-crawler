from __future__ import annotations

from crawler.enrich.field_groups import supported_field_groups


def test_supported_field_groups_include_core_agent_use_cases() -> None:
    groups = set(supported_field_groups())
    assert {"summaries", "classifications", "linkables"} <= groups


def test_supported_field_groups_include_passthrough_groups() -> None:
    groups = set(supported_field_groups())
    assert {"behavior", "risk", "code", "figures", "multimodal"} <= groups
