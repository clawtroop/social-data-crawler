"""PostgreSQL 连接与 DDL 执行。"""

from __future__ import annotations

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA = _PROJECT_ROOT / "schema"


def get_database_url(explicit: str | None = None) -> str:
    url = (explicit or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise ValueError(
            "未设置数据库连接串：请设置环境变量 DATABASE_URL 或传入 --database-url"
        )
    return url


def connect(dsn: str | None = None):
    try:
        import psycopg
    except ImportError as e:
        raise ImportError(
            "需要安装：pip install 'psycopg[binary]>=3.1'"
        ) from e
    return psycopg.connect(dsn or get_database_url())


def apply_sql_files(conn, paths: list[Path]) -> None:
    """顺序执行多个 .sql 文件（整文件提交）。"""
    for path in paths:
        sql = path.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
    conn.commit()


def run_phase1_phase2_schema(conn) -> None:
    """应用仓库内 phase1 + phase2 DDL。"""
    apply_sql_files(
        conn,
        [
            _SCHEMA / "phase1_linkedin.sql",
            _SCHEMA / "phase2_linkedin.sql",
        ],
    )
