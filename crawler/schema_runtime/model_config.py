from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_model_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
