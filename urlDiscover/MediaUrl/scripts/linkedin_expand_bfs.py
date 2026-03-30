#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一入口：以本人 Profile 为默认种子，可选额外 URL；对四类标准 URL 做 BFS 扩展
（profile / company / post / job 各用既有 expand），新链接经 ``standard_canonical_url`` 归一、去重，
再按 ``max_expand_depth`` 控制迭代深度（``None`` = 不限制）。

四类标准形式见 ``doc/进展.md``（无查询串、无子路径标签）。

抓取策略：默认 ``wait_until=load`` 即视为加载完成；``settle_ms``、各步 ``*_delay_ms`` 为 0 时不硬等。
若懒加载链接过少，可增大 ``FETCH_SCROLL_PASSES`` 或 ``FETCH_SCROLL_STEP_DELAY_MS``（毫秒）。
``FETCH_SKIP_ON_TIMEOUT=True`` 时超时不抛错，返回空 HTML，BFS 继续。

运行：
    set PYTHONPATH=d:\\Code\\MediaUrl
    python scripts/linkedin_expand_bfs.py

环境变量：
    LINKEDIN_PROFILE_SEED — 手动指定 profile 种子 URL（可选，覆盖从会话解析的结果）。
    LINKEDIN_BFS_MAX_RUNTIME_SECONDS — 运行时间上限（秒），覆盖脚本内 MAX_RUNTIME_SECONDS。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# 默认从 ``.secrets/linkedin_storage_state.json`` 会话访问 ``/in/me/`` 解析本人主页；
# 仅当需要覆盖时才设置环境变量 LINKEDIN_PROFILE_SEED 或下方 FALLBACK_PROFILE_SEED。
# ---------------------------------------------------------------------------
FALLBACK_PROFILE_SEED: str | None = None

# 额外种子（公司 / 动态 / 职位等任意可解析为四类的 URL）
EXTRA_SEED_URLS: list[str] = ["https://www.linkedin.com/in/jianli-wang-926768a9/"]

# 最大扩展深度：仅对 depth < MAX_EXPAND_DEPTH 的节点执行抓取（根种子 depth=0）。
# 设为 None 表示不限制层数（直至无新节点或全部已处理）。
MAX_EXPAND_DEPTH: int | None = 3

# 总运行时间上限（秒），到时间则停止遍历并保存已有四类 URL；None 表示不限制。
# 也可通过环境变量 LINKEDIN_BFS_MAX_RUNTIME_SECONDS 覆盖（例如 1800）。
MAX_RUNTIME_SECONDS: float | None = 300

OUTPUT_JSON = "linkedin_bfs_output.json"
OUTPUT_SUBDIR = "output/bfs_expand"

PROXY: str | None = None
STATE_PATH: Path | None = None

# 「加载完成」以 wait_until 为准；以下为 0 表示不额外硬等（见 fetch_html_sync 文档）
FETCH_WAIT_UNTIL = "load"
FETCH_SETTLE_MS = 0
FETCH_SCROLL_PASSES = 4
FETCH_SCROLL_STEP_DELAY_MS = 0
FETCH_SCROLL_BOTTOM_DELAY_MS = 0
FETCH_TIMEOUT_MS = 120_000
FETCH_EXPAND_SHOW_MORE = False
FETCH_EXPAND_MAX_ROUNDS = 12
FETCH_EXPAND_POST_DELAY_MS = 0
FETCH_SKIP_ON_TIMEOUT = True

VERBOSE_FETCH = True
VERBOSE_BFS = True
# 子扩展器内部逐步日志（公司多页时很冗长）；仅开 VERBOSE_BFS 时仍可见 [bfs] 与 [fetch]
VERBOSE_INNER_EXPAND = False


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _max_runtime_seconds() -> float | None:
    env = (os.getenv("LINKEDIN_BFS_MAX_RUNTIME_SECONDS") or "").strip()
    if env:
        return float(env)
    return MAX_RUNTIME_SECONDS


def main() -> int:
    root = _project_root()
    sys.path.insert(0, str(root))
    os.environ.setdefault("PYTHONPATH", str(root))

    from linkedin_url.auth.fetch import fetch_html_sync
    from linkedin_url.auth.paths import default_storage_state_path
    from linkedin_url.auth.profile_url import profile_canonical_url_from_storage_state
    from linkedin_url.bfs_expand import run_bfs_expand

    state = STATE_PATH or default_storage_state_path()
    proxy = PROXY or os.getenv("LINKEDIN_PROXY") or os.getenv("HTTPS_PROXY")
    out_dir = root / OUTPUT_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if not state.is_file():
        print("错误：请先 python -m linkedin_url login", file=sys.stderr)
        return 2

    env_profile = (os.getenv("LINKEDIN_PROFILE_SEED") or "").strip()
    if env_profile:
        profile_seed = env_profile
        print("种子 profile（来自 LINKEDIN_PROFILE_SEED）:", profile_seed)
    else:
        print("正在从会话解析当前用户主页（/in/me/ 重定向）…", flush=True)
        profile_seed = profile_canonical_url_from_storage_state(state, proxy=proxy)
        if not profile_seed and FALLBACK_PROFILE_SEED:
            profile_seed = FALLBACK_PROFILE_SEED.strip()
            print("会话解析失败，使用 FALLBACK_PROFILE_SEED:", profile_seed)
        elif not profile_seed:
            print(
                "错误：无法从会话得到主页 URL。请重新 login，或设置环境变量 "
                "LINKEDIN_PROFILE_SEED，或在脚本中设置 FALLBACK_PROFILE_SEED。",
                file=sys.stderr,
            )
            return 2
        else:
            print("种子 profile（来自会话）:", profile_seed)

    seed_urls = [profile_seed]
    seed_urls.extend(u.strip() for u in EXTRA_SEED_URLS if u.strip())
    if EXTRA_SEED_URLS:
        print("额外种子:", EXTRA_SEED_URLS)
    max_runtime = _max_runtime_seconds()
    print("MAX_EXPAND_DEPTH:", MAX_EXPAND_DEPTH, "(None=不限制)")
    print("MAX_RUNTIME_SECONDS:", max_runtime, "(None=不限制)")
    print("会话:", state)
    print("代理:", proxy or "(无)")
    print("-" * 60)

    def fetch(u: str) -> str:
        t0 = time.perf_counter()
        short = u if len(u) <= 120 else u[:117] + "..."
        if VERBOSE_FETCH:
            print(f"    [fetch] {short}", flush=True)
        body = fetch_html_sync(
            u,
            state_path=state,
            proxy=proxy,
            wait_until=FETCH_WAIT_UNTIL,
            settle_ms=FETCH_SETTLE_MS,
            scroll_passes=FETCH_SCROLL_PASSES,
            scroll_step_delay_ms=FETCH_SCROLL_STEP_DELAY_MS,
            scroll_bottom_delay_ms=FETCH_SCROLL_BOTTOM_DELAY_MS,
            timeout_ms=FETCH_TIMEOUT_MS,
            expand_show_more=FETCH_EXPAND_SHOW_MORE,
            expand_max_rounds=FETCH_EXPAND_MAX_ROUNDS,
            expand_post_delay_ms=FETCH_EXPAND_POST_DELAY_MS,
            skip_on_timeout=FETCH_SKIP_ON_TIMEOUT,
        )
        if VERBOSE_FETCH:
            print(
                f"    [fetch] 完成 ({time.perf_counter() - t0:.1f}s) {len(body)} 字符",
                flush=True,
            )
            if not body.strip() and FETCH_SKIP_ON_TIMEOUT:
                print("    [fetch] 提示: 空 HTML（可能导航超时已跳过）", flush=True)
        return body

    t0 = time.perf_counter()
    br, stats = run_bfs_expand(
        seed_urls,
        fetch,
        max_expand_depth=MAX_EXPAND_DEPTH,
        max_runtime_seconds=max_runtime,
        expand_company_kwargs={
            "verbose": VERBOSE_INNER_EXPAND,
            "save_html_dir": None,
        },
        expand_post_kwargs={
            "verbose": VERBOSE_INNER_EXPAND,
            "save_html_dir": None,
        },
        verbose=VERBOSE_BFS,
    )
    print(f"总耗时 {time.perf_counter() - t0:.1f}s", flush=True)

    four = br.as_four_dict()
    payload = {
        "seed_urls": seed_urls,
        "max_expand_depth": MAX_EXPAND_DEPTH,
        "max_runtime_seconds": max_runtime,
        "stopped_by_time_limit": stats.get("stopped_by_time_limit", False),
        "stats": stats,
        "profiles": four["profiles"],
        "companies": four["companies"],
        "jobs": four["jobs"],
        "posts": four["posts"],
    }
    out_path = root / OUTPUT_JSON
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n四类 URL 统计:")
    print("  profiles :", len(four["profiles"]))
    print("  companies:", len(four["companies"]))
    print("  jobs     :", len(four["jobs"]))
    print("  posts    :", len(four["posts"]))
    print("  expansions_run:", stats["expansions_run"])
    print("  elapsed_seconds:", stats.get("elapsed_seconds"))
    if stats.get("stopped_by_time_limit"):
        print("  已因运行时间上限停止；queue_remaining:", stats.get("queue_remaining"))
    if stats.get("errors"):
        print("  errors:", len(stats["errors"]))
    print("\n已写入:", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
