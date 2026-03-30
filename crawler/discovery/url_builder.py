from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT_DIR / "references" / "url_templates.json"
FIELD_MAPPING_PATH = ROOT_DIR / "references" / "field_mappings.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_field(record: dict, aliases: dict, target_field: str) -> str:
    for candidate in aliases.get(target_field, [target_field]):
        value = record.get(candidate)
        if value:
            return str(value)
    raise KeyError(target_field)


def _normalize_value(field: str, value: str) -> str:
    if field == "title":
        return quote(value.replace(" ", "_"), safe="_()")
    if field in {"query"}:
        return quote(value, safe="")
    if field == "search_type":
        mapping = {
            "company": "companies",
            "companies": "companies",
            "profile": "people",
            "people": "people",
            "job": "jobs",
            "jobs": "jobs",
            "post": "content",
            "content": "content",
        }
        normalized = mapping.get(value.lower().strip())
        if normalized is None:
            raise ValueError(f"unsupported linkedin search_type: {value}")
        return normalized
    return value


def build_url(record: dict) -> dict:
    platform = record["platform"]
    resource_type = record["resource_type"]
    templates = _load_json(TEMPLATE_PATH)
    mappings = _load_json(FIELD_MAPPING_PATH)
    template_config = templates[platform][resource_type]
    alias_config = mappings.get(platform, {}).get(resource_type, {})

    fields: dict[str, str] = {}
    for field_name in template_config.get("required_fields", []):
        value = _find_field(record, alias_config, field_name)
        fields[field_name] = _normalize_value(field_name, value)

    canonical_url = template_config["canonical_template"].format(**fields)
    artifacts = {
        name: template.format(**fields)
        for name, template in template_config.get("artifact_templates", {}).items()
    }

    return {
        "platform": platform,
        "resource_type": resource_type,
        "canonical_url": canonical_url,
        "artifacts": artifacts,
        "fields": fields,
    }
