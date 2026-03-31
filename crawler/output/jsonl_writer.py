from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def write_jsonl(path: Path, records: Iterable[dict], *, append: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a" if append else "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return path
