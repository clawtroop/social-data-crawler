from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

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


def test_load_model_config_uses_openclaw_env_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCLAW_GATEWAY_TOKEN", "env-token")

    config = load_model_config(None, use_openclaw=True)

    assert config == {
        "provider": "openclaw",
        "base_url": "http://127.0.0.1:18789/v1",
        "api_key": "env-token",
        "model": "openclaw/default",
    }


def test_load_model_config_does_not_auto_detect_openclaw_env_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCLAW_GATEWAY_TOKEN", "env-token")

    config = load_model_config(None)

    assert config == {}


def test_load_model_config_uses_openclaw_default_config_file(workspace_tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    openclaw_config_path = workspace_tmp_path / "openclaw.json"
    openclaw_config_path.write_text(
        json.dumps({"gateway": {"auth": {"token": "file-token"}}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENCLAW_GATEWAY_TOKEN", raising=False)
    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(openclaw_config_path))

    config = load_model_config(None, use_openclaw=True)

    assert config == {
        "provider": "openclaw",
        "base_url": "http://127.0.0.1:18789/v1",
        "api_key": "file-token",
        "model": "openclaw/default",
    }


def test_load_model_config_rejects_openclaw_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENCLAW_GATEWAY_TOKEN", raising=False)
    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", os.devnull)

    with pytest.raises(ValueError, match="OpenClaw Gateway token"):
        load_model_config(None, use_openclaw=True)


def test_load_model_config_without_model_or_openclaw_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENCLAW_GATEWAY_TOKEN", raising=False)
    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", os.devnull)

    config = load_model_config(None)

    assert config == {}


def test_load_model_config_resolves_openclaw_file_secretref(workspace_tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secrets_path = workspace_tmp_path / "secrets.json"
    secrets_path.write_text(
        json.dumps({"gateway": {"token": "file-secret-token"}}),
        encoding="utf-8",
    )
    openclaw_config_path = workspace_tmp_path / "openclaw.json"
    openclaw_config_path.write_text(
        json.dumps(
            {
                "gateway": {
                    "auth": {
                        "token": {
                            "source": "file",
                            "provider": "filemain",
                            "id": "/gateway/token",
                        }
                    }
                },
                "secrets": {
                    "providers": {
                        "filemain": {
                            "source": "file",
                            "path": str(secrets_path),
                            "mode": "json",
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENCLAW_GATEWAY_TOKEN", raising=False)
    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(openclaw_config_path))

    config = load_model_config(None, use_openclaw=True)

    assert config["api_key"] == "file-secret-token"


def test_load_model_config_resolves_openclaw_exec_secretref(workspace_tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    helper_script = workspace_tmp_path / "secret_helper.py"
    helper_script.write_text(
        "\n".join(
            [
                "import json, sys",
                "payload = json.load(sys.stdin)",
                "print(json.dumps({",
                '    "protocolVersion": 1,',
                '    "values": {payload["ids"][0]: "exec-secret-token"}',
                "}))",
            ]
        ),
        encoding="utf-8",
    )
    openclaw_config_path = workspace_tmp_path / "openclaw.json"
    openclaw_config_path.write_text(
        json.dumps(
            {
                "gateway": {
                    "auth": {
                        "token": {
                            "source": "exec",
                            "provider": "vault",
                            "id": "gateway/auth/token",
                        }
                    }
                },
                "secrets": {
                    "providers": {
                        "vault": {
                            "source": "exec",
                            "command": sys.executable,
                            "args": [str(helper_script)],
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENCLAW_GATEWAY_TOKEN", raising=False)
    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(openclaw_config_path))

    config = load_model_config(None, use_openclaw=True)

    assert config["api_key"] == "exec-secret-token"


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
