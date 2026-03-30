from __future__ import annotations

import json
from pathlib import Path

from crawler.cli import main
from crawler.submission_export import build_submission_request


def test_build_submission_request_maps_canonical_record_to_platform_payload() -> None:
    record = {
        "canonical_url": "https://www.linkedin.com/company/openai/",
        "plain_text": "OpenAI company profile",
        "structured": {
            "title": "OpenAI",
            "company_slug": "openai",
        },
        "crawl_timestamp": "2026-03-29T09:00:00Z",
    }

    payload = build_submission_request([record], dataset_id="ds_linkedin")

    assert payload == {
        "dataset_id": "ds_linkedin",
        "entries": [
            {
                "url": "https://www.linkedin.com/company/openai/",
                "cleaned_data": "OpenAI company profile",
                "structured_data": {
                    "title": "OpenAI",
                    "company_slug": "openai",
                },
                "crawl_timestamp": "2026-03-29T09:00:00Z",
            }
        ],
    }


def test_build_submission_request_falls_back_to_manifest_timestamp_when_record_is_missing_it() -> None:
    record = {
        "canonical_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
        "plain_text": "AI article",
        "structured": {"title": "Artificial intelligence"},
    }

    payload = build_submission_request(
        [record],
        dataset_id="ds_wiki",
        generated_at="2026-03-29T10:30:00Z",
    )

    assert payload["entries"][0]["crawl_timestamp"] == "2026-03-29T10:30:00Z"


def test_export_submissions_command_writes_payload_json(workspace_tmp_path: Path) -> None:
    records_path = workspace_tmp_path / "records.jsonl"
    output_path = workspace_tmp_path / "submissions.json"
    records_path.write_text(
        json.dumps(
            {
                "canonical_url": "https://www.linkedin.com/in/john-doe-ai/",
                "plain_text": "AI at Self",
                "structured": {"public_identifier": "john-doe-ai"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "export-submissions",
            "--input",
            str(records_path),
            "--dataset-id",
            "ds_people",
            "--generated-at",
            "2026-03-29T11:00:00Z",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["dataset_id"] == "ds_people"
    assert payload["entries"][0]["url"] == "https://www.linkedin.com/in/john-doe-ai/"
    assert payload["entries"][0]["cleaned_data"] == "AI at Self"
    assert payload["entries"][0]["crawl_timestamp"] == "2026-03-29T11:00:00Z"
