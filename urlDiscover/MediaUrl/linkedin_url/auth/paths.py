"""会话文件路径（可通过环境变量覆盖）。"""

from __future__ import annotations

import os
from pathlib import Path


def default_storage_state_path() -> Path:
    """
    默认：项目根下 `.secrets/linkedin_storage_state.json`（已在 .gitignore 中忽略）。

    覆盖：环境变量 `LINKEDIN_STORAGE_STATE=/abs/path/state.json`
    """
    env = os.getenv("LINKEDIN_STORAGE_STATE", "").strip()
    if env:
        return Path(env)
    return Path(".secrets") / "linkedin_storage_state.json"
