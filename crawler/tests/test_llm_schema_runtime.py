from __future__ import annotations

import json
from pathlib import Path

from crawler.schema_runtime.llm_executor import SchemaExecutionResult, extract_json_object
from crawler.schema_runtime.model_config import load_model_config


def test_load_model_config_reads_json_file(workspace_tmp_path: Path) -> None:
    model_config_path = workspace_tmp_path / "model.json"
    model_config_path.write_text(
        json.dumps({"base_url": "https://api.example.com", "model": "test-model", "api_key": "secret"}),
        encoding="utf-8",
    )

    config = load_model_config(model_config_path)

    assert config["base_url"] == "https://api.example.com"
    assert config["model"] == "test-model"


def test_extract_json_object_parses_markdown_wrapped_json() -> None:
    parsed = extract_json_object('```json\n{"title":"Test","fields":{"price":"$19"}}\n```')

    assert parsed == {"title": "Test", "fields": {"price": "$19"}}


def test_schema_execution_result_to_error_dict() -> None:
    result = SchemaExecutionResult(success=False, data={}, error="llm failed", schema_name="extract-demo")

    assert result.to_error_dict() == {
        "schema_name": "extract-demo",
        "status": "failed",
        "error": "llm failed",
    }
