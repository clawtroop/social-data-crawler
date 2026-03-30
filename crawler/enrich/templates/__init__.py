from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping


def _has_value(value: Any) -> bool:
    return value not in (None, "", [], {}, ())


@dataclass(frozen=True, slots=True)
class FieldGroupTemplate:
    name: str
    output_field: str
    source_fields: tuple[str, ...]
    prompt: str
    confidence: float = 0.6

    def collect_sources(self, record: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
        collected: dict[str, Any] = {}
        evidence: list[str] = []
        for source_field in self.source_fields:
            value = record.get(source_field)
            if _has_value(value):
                collected[source_field] = value
                evidence.append(source_field)
        return collected, evidence

    def route(self, record: Mapping[str, Any]) -> dict[str, Any]:
        source_payload, evidence = self.collect_sources(record)
        if source_payload:
            first_field = evidence[0]
            return {
                "generated_fields": {self.output_field: source_payload[first_field]},
                "confidence": self.confidence,
                "evidence": [first_field],
                "source_fields": {first_field: source_payload[first_field]},
                "unsupported_reason": None,
                "prompt": self.render_prompt(source_payload),
            }

        return {
            "generated_fields": {},
            "confidence": 0.0,
            "evidence": [],
            "source_fields": {},
            "unsupported_reason": f"no routable source fields for {self.name}",
            "prompt": None,
        }

    def render_prompt(self, source_payload: Mapping[str, Any]) -> str:
        return (
            f"Field group: {self.name}\n"
            f"Instruction: {self.prompt}\n"
            f"Output field: {self.output_field}\n"
            f"Source payload:\n{json.dumps(source_payload, ensure_ascii=False, indent=2, default=str)}"
        )


FIELD_GROUP_TEMPLATES: dict[str, FieldGroupTemplate] = {
    "summaries": FieldGroupTemplate(
        name="summaries",
        output_field="summary",
        source_fields=("title", "summary", "abstract", "description"),
        prompt="Produce a concise factual summary using the available source fields only.",
    ),
    "classifications": FieldGroupTemplate(
        name="classifications",
        output_field="classification",
        source_fields=("resource_type", "category", "tags", "label"),
        prompt="Classify the record into the most specific category supported by the source fields.",
    ),
    "linkables": FieldGroupTemplate(
        name="linkables",
        output_field="linkable_identifier",
        source_fields=("canonical_url", "url", "id", "identifier"),
        prompt="Return the strongest cross-system identifier for this record.",
    ),
    "multimodal": FieldGroupTemplate(
        name="multimodal",
        output_field="multimodal_signal",
        source_fields=("image_url", "media_url", "thumbnail"),
        prompt="Describe the primary multimodal signal available in the source fields.",
    ),
    "behavior": FieldGroupTemplate(
        name="behavior",
        output_field="behavior_signal",
        source_fields=("behavior", "activity", "actions"),
        prompt="Summarize the most relevant behavioral signal from the source fields.",
    ),
    "risk": FieldGroupTemplate(
        name="risk",
        output_field="risk_signal",
        source_fields=("risk", "severity", "issue"),
        prompt="Summarize the highest-signal risk based on the source fields.",
    ),
    "code": FieldGroupTemplate(
        name="code",
        output_field="code_signal",
        source_fields=("code_url", "repo", "language", "filename"),
        prompt="Describe the primary code-related signal from the source fields.",
    ),
    "figures": FieldGroupTemplate(
        name="figures",
        output_field="figure_signal",
        source_fields=("figure_url", "figure_caption", "figure_id"),
        prompt="Summarize the primary figure or chart signal from the source fields.",
    ),
}


def get_field_group_template(field_group: str) -> FieldGroupTemplate | None:
    return FIELD_GROUP_TEMPLATES.get(field_group)


def route_field_group(
    field_group: str,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    template = get_field_group_template(field_group)
    if template is None:
        return {
            "generated_fields": {},
            "confidence": 0.0,
            "evidence": [],
            "source_fields": {},
            "unsupported_reason": "unsupported field group",
        }
    return template.route(record)
