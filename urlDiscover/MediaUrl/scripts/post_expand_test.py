#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
以单条或多条 LinkedIn **动态详情页** 为种子：单独访问 feed/update（或 /posts/…activity-…），
再经 discover 扩展出评论者 /in/、公司 /company/、其它动态等 URL。

与 ``profile_expand_test`` / ``company_expand_test`` 相同模式：可在线 Playwright 抓取并保存 HTML，
或 ``PARSE_ONLY = True`` 仅解析 ``output/post_expand/activity_{id}_detail.html``。

运行：
    set PYTHONPATH=d:\\Code\\MediaUrl
    python scripts/post_expand_test.py

离线解析：``PARSE_ONLY = True``，且已存在与 activity_id 对应的 ``*_detail.html``。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# 一条或多条动态 URL（feed/update 或含 activity- 的 posts 短链均可）
# ---------------------------------------------------------------------------
POST_URLS = [
    "https://www.linkedin.com/feed/update/urn:li:activity:7440626974185840640/"
]

OUTPUT_SUBDIR = "output/post_expand"

PARSE_ONLY = False

PROXY: str | None = None
STATE_PATH: Path | None = None

FETCH_WAIT_UNTIL = "load"
FETCH_SETTLE_MS = 0
FETCH_SCROLL_PASSES = 12
FETCH_SCROLL_STEP_DELAY_MS = 400
FETCH_SCROLL_BOTTOM_DELAY_MS = 300
FETCH_TIMEOUT_MS = 120_000
FETCH_EXPAND_SHOW_MORE = True
FETCH_EXPAND_MAX_ROUNDS = 16
FETCH_EXPAND_POST_DELAY_MS = 400
FETCH_SKIP_ON_TIMEOUT = False

VERBOSE_PROGRESS = True


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _detail_html_path(out_dir: Path, activity_id: str | None) -> Path:
    aid = activity_id or "unknown"
    return out_dir / f"activity_{aid}_detail.html"


def main() -> int:
    root = _project_root()
    sys.path.insert(0, str(root))
    os.environ.setdefault("PYTHONPATH", str(root))

    from linkedin_url.auth.fetch import fetch_html_sync
    from linkedin_url.auth.paths import default_storage_state_path
    from linkedin_url.normalize import normalize_linkedin_url
    from linkedin_url.post_expand import (
        expand_post_from_saved_html,
        expand_post_page,
        expand_post_pages_merged,
        merge_post_expand_results,
    )

    out_dir = root / OUTPUT_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    state = STATE_PATH or default_storage_state_path()
    proxy = PROXY or os.getenv("LINKEDIN_PROXY") or os.getenv("HTTPS_PROXY")

    seeds = []
    for raw in POST_URLS:
        s = normalize_linkedin_url(raw.strip())
        seeds.append((raw.strip(), s))

    for raw, s in seeds:
        if s.entity_type.value != "post" or not s.canonical_url:
            print(f"错误：无法识别为动态 URL：{raw}", file=sys.stderr)
            return 2

    print("种子条数:", len(POST_URLS))
    for raw, s in seeds:
        print(" ", raw)
        print("   → canonical:", s.canonical_url, "| activity_id:", s.activity_id)
    print("会话:", state)
    print("代理:", proxy or "(无)")
    print("输出目录:", out_dir)
    print("PARSE_ONLY:", PARSE_ONLY)
    print("-" * 60)

    meta_path = out_dir / "post_expand_meta.json"

    if PARSE_ONLY:
        parts = []
        for raw, s in seeds:
            path = _detail_html_path(out_dir, s.activity_id)
            if not path.is_file():
                print(f"错误：缺少已保存 HTML：{path}", file=sys.stderr)
                return 2
            html = path.read_text(encoding="utf-8", errors="replace")
            parts.append(
                expand_post_from_saved_html(
                    html=html,
                    post_canonical_url=s.canonical_url,
                )
            )
        result: dict = (
            parts[0]
            if len(parts) == 1
            else merge_post_expand_results(parts)
        )
    else:
        if not state.is_file():
            print("错误：请先 python -m linkedin_url login", file=sys.stderr)
            return 2

        def fetch(u: str) -> str:
            t0 = time.perf_counter()
            short = u if len(u) <= 140 else u[:137] + "..."
            print(f"    [fetch] 开始: {short}", flush=True)
            try:
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
            except Exception as e:
                print(f"    [fetch] 异常 ({time.perf_counter() - t0:.1f}s): {e!r}", flush=True)
                raise
            print(
                f"    [fetch] 结束 ({time.perf_counter() - t0:.1f}s)，HTML {len(body)} 字符",
                flush=True,
            )
            return body

        urls_only = [raw for raw, _ in seeds]
        t0 = time.perf_counter()
        if len(urls_only) == 1:
            result = expand_post_page(
                urls_only[0],
                fetch,
                verbose=VERBOSE_PROGRESS,
                save_html_dir=out_dir,
            )
        else:
            result = expand_post_pages_merged(
                urls_only,
                fetch,
                verbose=VERBOSE_PROGRESS,
                save_html_dir=out_dir,
            )
        print(f"expand_post 总耗时 {time.perf_counter() - t0:.1f}s", flush=True)

        meta: dict = {
            "post_urls": POST_URLS,
            "fetch": {
                "wait_until": FETCH_WAIT_UNTIL,
                "settle_ms": FETCH_SETTLE_MS,
                "scroll_passes": FETCH_SCROLL_PASSES,
                "expand_show_more": FETCH_EXPAND_SHOW_MORE,
                "expand_max_rounds": FETCH_EXPAND_MAX_ROUNDS,
            },
            "saved_detail_globs": [
                str(_detail_html_path(out_dir, s.activity_id).relative_to(root))
                for _, s in seeds
            ],
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print("元数据:", meta_path, flush=True)

    buckets = result["buckets"]
    order = [
        ("【公司】", "company"),
        ("【公司子页】", "company_tab"),
        ("【单条动态】", "post"),
        ("【个人主页】", "profile"),
        ("【个人子页/动态列表】", "profile_activity"),
        ("【profile_subpage】", "profile_subpage"),
        ("【职位搜索】", "jobs_search"),
        ("【单职位】", "job"),
        ("【其它】", "other"),
    ]
    for title, key in order:
        items = buckets.get(key) or []
        if not items:
            continue
        print(f"\n{title} ({len(items)})")
        for u in items[:80]:
            print(" ", u)
        if len(items) > 80:
            print(f"  ... 共 {len(items)} 条，见 JSON")

    printed = {k for _, k in order}
    for k, v in sorted(buckets.items()):
        if k in printed or not v:
            continue
        print(f"\n【{k}】 ({len(v)})")
        for u in v[:40]:
            print(" ", u)
        if len(v) > 40:
            print(f"  ... 共 {len(v)} 条")

    print(f"\n【发现 URL 去重数量】{len(result.get('urls_discovered') or [])}")

    out_json = root / "post_expand_output.json"
    payload = {
        "post_urls": POST_URLS,
        "parse_only": PARSE_ONLY,
        "result": result,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n已写入:", out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
