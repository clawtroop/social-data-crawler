#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从个人 profile 扩展发现 URL：先保存 HTML，再解析；支持仅离线解析已保存文件。

领英为 SPA，请在 fetch 中使用 load + settle + scroll（见下方 FETCH_*）。

运行：
    set PYTHONPATH=d:\\Code\\MediaUrl
    python scripts/profile_expand_test.py

仅解析上次保存的 HTML（不抓网）：
    在脚本中设 PARSE_ONLY = True（需已有 output/profile_expand/*_main.html）
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 在此填入要测试的个人主页
# ---------------------------------------------------------------------------
PROFILE_URL = "https://www.linkedin.com/in/jianli-wang-926768a9/"

# 是否再抓「动态 · 评论」页
FETCH_RECENT_ACTIVITY_COMMENTS = True

# 仅解析本地已保存 HTML，不发起 Playwright（调试解析逻辑时用）
PARSE_ONLY = False

# 输出目录（项目根下）
OUTPUT_SUBDIR = "output/profile_expand"

# 可选代理
PROXY: str | None = None
STATE_PATH: Path | None = None

# 抓取：以 wait_until 为准表示加载完成；以下为 0 则不在该步骤硬等（见 fetch_html_sync）
FETCH_WAIT_UNTIL = "load"  # load | domcontentloaded | networkidle（易超时）
FETCH_SETTLE_MS = 0
FETCH_SCROLL_PASSES = 6
FETCH_SCROLL_STEP_DELAY_MS = 400
FETCH_SCROLL_BOTTOM_DELAY_MS = 300
FETCH_TIMEOUT_MS = 120_000

FETCH_EXPAND_SHOW_MORE = True
FETCH_EXPAND_MAX_ROUNDS = 12
FETCH_EXPAND_POST_DELAY_MS = 400
FETCH_SKIP_ON_TIMEOUT = False


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _slug_from_profile_url(url: str) -> str:
    from linkedin_url.normalize import normalize_linkedin_url

    r = normalize_linkedin_url(url)
    if r.profile_vanity:
        return re.sub(r"[^\w\-]+", "_", r.profile_vanity)[:80]
    return "profile"


def main() -> int:
    root = _project_root()
    sys.path.insert(0, str(root))
    os.environ.setdefault("PYTHONPATH", str(root))

    from linkedin_url.auth.fetch import fetch_html_sync
    from linkedin_url.auth.paths import default_storage_state_path
    from linkedin_url.normalize import normalize_linkedin_url
    from linkedin_url.profile_expand import expand_from_saved_html

    out_dir = root / OUTPUT_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)

    state = STATE_PATH or default_storage_state_path()
    proxy = PROXY or os.getenv("LINKEDIN_PROXY") or os.getenv("HTTPS_PROXY")
    seed = normalize_linkedin_url(PROFILE_URL)
    if not seed.profile_vanity:
        print("错误：不是个人主页 URL", file=sys.stderr)
        return 2
    slug = _slug_from_profile_url(PROFILE_URL)
    path_main = out_dir / f"{slug}_main.html"
    path_activity = out_dir / f"{slug}_activity_comments.html"
    meta_path = out_dir / f"{slug}_meta.json"

    print("种子:", seed.canonical_url)
    print("会话:", state)
    print("代理:", proxy or "(无)")
    print("输出目录:", out_dir)
    print("PARSE_ONLY:", PARSE_ONLY)
    print("-" * 60)

    if PARSE_ONLY:
        if not path_main.is_file():
            print(f"错误：找不到 {path_main}", file=sys.stderr)
            return 2
        main_html = path_main.read_text(encoding="utf-8", errors="replace")
        act_html = None
        if FETCH_RECENT_ACTIVITY_COMMENTS and path_activity.is_file():
            act_html = path_activity.read_text(encoding="utf-8", errors="replace")
        buckets = expand_from_saved_html(
            main_html=main_html,
            activity_html=act_html,
            profile_canonical_url=seed.canonical_url,
            seed_vanity=seed.profile_vanity,
        )
    else:
        if not state.is_file():
            print("错误：请先 python -m linkedin_url login", file=sys.stderr)
            return 2

        def fetch(u: str) -> str:
            return fetch_html_sync(
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

        html_main = fetch(seed.canonical_url)
        path_main.write_text(html_main, encoding="utf-8")

        act_html: str | None = None
        if FETCH_RECENT_ACTIVITY_COMMENTS:
            act_u = f"https://www.linkedin.com/in/{seed.profile_vanity}/recent-activity/comments/"
            try:
                act_html = fetch(act_u)
                path_activity.write_text(act_html, encoding="utf-8")
            except Exception as e:
                print("警告: activity 页抓取失败:", e)

        buckets = expand_from_saved_html(
            main_html=html_main,
            activity_html=act_html,
            profile_canonical_url=seed.canonical_url,
            seed_vanity=seed.profile_vanity,
        )

        meta: dict = {
            "profile_url": PROFILE_URL,
            "canonical": seed.canonical_url,
            "saved_main": str(path_main.relative_to(root)),
            "main_bytes": len(html_main.encode("utf-8", errors="replace")),
            "fetch": {
                "wait_until": FETCH_WAIT_UNTIL,
                "settle_ms": FETCH_SETTLE_MS,
                "scroll_passes": FETCH_SCROLL_PASSES,
                "expand_show_more": FETCH_EXPAND_SHOW_MORE,
                "expand_max_rounds": FETCH_EXPAND_MAX_ROUNDS,
            },
        }
        if act_html is not None:
            meta["saved_activity"] = str(path_activity.relative_to(root))
            meta["activity_bytes"] = len(act_html.encode("utf-8", errors="replace"))
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已保存:", path_main)
        if act_html is not None:
            print("已保存:", path_activity)
        print("元数据:", meta_path)

    # 打印分组
    order = [
        ("【公司】", "company"),
        ("【单条动态】", "post"),
        ("【动态列表页】", "profile_activity"),
        ("【他人主页】", "profiles_others"),
        ("【本人主页】", "profiles_self"),
        ("【职位】", "job"),
        ("【个人子页】", "profile_subpage"),
        ("【其它】", "other"),
    ]
    for title, key in order:
        items = buckets.get(key) or []
        if not items:
            continue
        print(f"\n{title} ({len(items)})")
        for u in items:
            print(" ", u)

    printed = {k for _, k in order}
    for k, v in sorted(buckets.items()):
        if k in printed or not v:
            continue
        print(f"\n【{k}】 ({len(v)})")
        for u in v:
            print(" ", u)

    out_json = root / "profile_expand_output.json"
    payload = {
        "profile_url": PROFILE_URL,
        "canonical_url": seed.canonical_url,
        "parse_only": PARSE_ONLY,
        "buckets": buckets,
        "saved_files": {
            "main_html": str(path_main.relative_to(root)) if path_main.is_file() else None,
            "activity_html": str(path_activity.relative_to(root)) if path_activity.is_file() else None,
        },
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n已写入:", out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
