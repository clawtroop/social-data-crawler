from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_TEMPLATES_DIR = Path(__file__).resolve().parent / "prompt_templates"


def render_prompt(template_name: str, source_fields: dict[str, Any]) -> str:
    """Render a Jinja2-style template with simple variable substitution.

    Supports:
      - {% for key, value in source_fields.items() %} ... {% endfor %}
      - {{ key }}, {{ value }}
      - {{ source_fields.get("field") }}
    """
    template_path = _TEMPLATES_DIR / template_name
    if not template_path.exists():
        return _fallback_prompt(template_name, source_fields)

    template_text = template_path.read_text(encoding="utf-8")
    return _expand_template(template_text, source_fields)


def _expand_template(template_text: str, source_fields: dict[str, Any]) -> str:
    """Expand the template by processing for-loops and variable references."""
    # Process for loops: {% for key, value in source_fields.items() %} ... {% endfor %}
    for_pattern = re.compile(
        r"\{%\s*for\s+(\w+),\s*(\w+)\s+in\s+source_fields\.items\(\)\s*%\}(.*?)\{%\s*endfor\s*%\}",
        re.DOTALL,
    )

    def expand_for(match: re.Match[str]) -> str:
        key_var = match.group(1)
        val_var = match.group(2)
        body = match.group(3)
        parts = []
        for k, v in source_fields.items():
            expanded = body
            expanded = expanded.replace(f"{{{{ {key_var} }}}}", str(k))
            expanded = expanded.replace(f"{{{{ {val_var} }}}}", str(v))
            parts.append(expanded)
        return "".join(parts)

    result = for_pattern.sub(expand_for, template_text)

    # Replace remaining {{ source_fields.get("field") }} references
    get_pattern = re.compile(r'\{\{\s*source_fields\.get\(["\'](\w+)["\']\)\s*\}\}')
    result = get_pattern.sub(lambda m: str(source_fields.get(m.group(1), "")), result)

    return result.strip()


def _fallback_prompt(template_name: str, source_fields: dict[str, Any]) -> str:
    """Generate a simple prompt when no template file is found."""
    parts = [f"Field group: {template_name}", "Source fields:"]
    for key, value in source_fields.items():
        parts.append(f"  {key}: {value}")
    parts.append("")
    parts.append("Return a JSON object with the enriched fields based on the source data above.")
    return "\n".join(parts)


def list_templates() -> list[str]:
    """List available prompt template files."""
    if not _TEMPLATES_DIR.exists():
        return []
    return [p.name for p in _TEMPLATES_DIR.iterdir() if p.suffix == ".jinja2"]
