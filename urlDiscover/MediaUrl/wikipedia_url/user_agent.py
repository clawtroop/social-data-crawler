"""
解析维基 API 使用的 HTTP User-Agent。

优先级（后者覆盖前者仅当前者未设置）：

1. 环境变量 ``WIKIPEDIA_USER_AGENT``
2. 项目根目录下 ``.secrets/wikipedia_user_agent.txt`` 中第一个非空、非 ``#`` 注释行
3. 内置默认值（开发用；生产环境请用 1 或 2 写明可联系信息）

政策说明：<https://meta.wikimedia.org/wiki/User-Agent_policy>

示例（可复制到 ``.secrets/wikipedia_user_agent.txt``，单行）::

    MediaUrl/1.0 (+https://github.com/your-org/MediaUrl; mailto:you@example.com)
"""

from __future__ import annotations

import os
from pathlib import Path

# 内置兜底：须 ≥5 字符（wikipedia-api 校验）；生产环境请替换为可联系信息
DEFAULT_WIKIPEDIA_USER_AGENT = (
    "MediaUrl/1.0 (Wikipedia API client; +https://example.com/MediaUrl; "
    "mailto:mediaurl-dev@local — replace via WIKIPEDIA_USER_AGENT or .secrets)"
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_user_agent_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        return s
    return None


def get_wikipedia_user_agent() -> str:
    """
    返回用于 MediaWiki API 请求的 ``User-Agent`` 字符串（脚本与 ``mw_client`` 共用）。
    """
    env = os.getenv("WIKIPEDIA_USER_AGENT")
    if env is not None:
        u = env.strip()
        if u:
            return u

    path = _project_root() / ".secrets" / "wikipedia_user_agent.txt"
    from_file = _read_user_agent_file(path)
    if from_file:
        return from_file.strip()

    return DEFAULT_WIKIPEDIA_USER_AGENT
