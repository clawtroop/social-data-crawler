from __future__ import annotations

import json
from pathlib import Path

from crawler.cli import main


def test_wikipedia_crawl_end_to_end_fetches_real_page(workspace_tmp_path: Path) -> None:
    """End-to-end integration test using legacy pipeline for predictable output format."""
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps(
            {
                "platform": "wikipedia",
                "resource_type": "article",
                "title": "Artificial intelligence",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["crawl", "--input", str(input_path), "--output", str(output_dir), "--strict", "--use-legacy-pipeline"])

    assert exit_code == 0
    record = json.loads((output_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert record["canonical_url"].endswith("/Artificial_intelligence")
    assert record["metadata"]["title"]
    assert record["plain_text"]
    assert any(artifact["kind"] in {"html", "api_response"} for artifact in record["artifacts"])
