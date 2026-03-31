from __future__ import annotations

import json
from pathlib import Path

from crawler.normalize.canonical import build_canonical_record
from crawler.output import read_json_file, read_jsonl_file
from crawler.output.artifact_writer import write_artifact_bytes, write_artifact_json, write_artifact_text
from crawler.output.jsonl_writer import write_jsonl
from crawler.output.summary_writer import build_summary


def test_canonical_record_contains_agent_control_fields() -> None:
    record = build_canonical_record(
        platform="wikipedia",
        entity_type="article",
        canonical_url="https://en.wikipedia.org/wiki/AI",
    )
    assert record["status"] == "success"
    assert record["stage"] == "normalized"
    assert record["retryable"] is False
    assert record["next_action"] == "none"


def test_write_jsonl_creates_records_file(workspace_tmp_path: Path) -> None:
    path = workspace_tmp_path / "outputs" / "records.jsonl"

    write_jsonl(path, [{"id": 1}, {"id": 2}])

    assert path.exists()
    assert path.read_text(encoding="utf-8").splitlines() == [json.dumps({"id": 1}), json.dumps({"id": 2})]


def test_build_summary_distinguishes_partial_success() -> None:
    summary = build_summary([{"id": 1}], [{"error": "boom"}])

    assert summary["status"] == "partial_success"
    assert summary["records_total"] == 2
    assert summary["records_failed"] == 1
    assert summary["next_action"] == "inspect errors.jsonl"


def test_artifact_writers_persist_text_json_and_bytes(workspace_tmp_path: Path) -> None:
    text_path = workspace_tmp_path / "artifacts" / "page.html"
    json_path = workspace_tmp_path / "artifacts" / "metadata.json"
    bytes_path = workspace_tmp_path / "artifacts" / "image.png"

    write_artifact_text(text_path, "<html>ok</html>")
    write_artifact_json(json_path, {"title": "Example"})
    write_artifact_bytes(bytes_path, b"PNG")

    assert text_path.read_text(encoding="utf-8") == "<html>ok</html>"
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"title": "Example"}
    assert bytes_path.read_bytes() == b"PNG"


def test_output_package_exposes_json_read_helpers(workspace_tmp_path: Path) -> None:
    json_path = workspace_tmp_path / "manifest.json"
    jsonl_path = workspace_tmp_path / "records.jsonl"
    json_path.write_text('{"status":"ok"}', encoding="utf-8")
    jsonl_path.write_text('{"id":1}\n{"id":2}\n', encoding="utf-8")

    assert read_json_file(json_path) == {"status": "ok"}
    assert read_jsonl_file(jsonl_path) == [{"id": 1}, {"id": 2}]
