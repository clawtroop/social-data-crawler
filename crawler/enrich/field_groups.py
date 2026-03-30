from __future__ import annotations

from crawler.enrich.templates import FIELD_GROUP_TEMPLATES


def supported_field_groups() -> list[str]:
    return list(FIELD_GROUP_TEMPLATES)
