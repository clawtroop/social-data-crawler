#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
以 LinkedIn 公司页为种子，抓取 Overview + Jobs + People + Posts（及页面内 jobs/search 落地页），
抽取职位 ID、员工 /in、动态等 URL。Posts 列表与可选的单条动态详情中可出现评论者 /in/、侧栏推荐的公司与个人。

运行：
    set PYTHONPATH=d:\\Code\\MediaUrl
    python scripts/company_expand_test.py

离线解析：PARSE_ONLY = True，并放置 output/company_expand/{SAVE_PREFIX}_overview.html 等。
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
COMPANY_URL = "https://www.linkedin.com/company/pop-mart/"

OUTPUT_SUBDIR = "output/company_expand"
SAVE_PREFIX = "pop-mart"

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

FETCH_JOBS_SEARCH_PAGES = True
MAX_JOBS_SEARCH_FETCH = 5

# 为 True 时 expand_company 逐步打印进度；fetch 包装器再打印每次网络请求的耗时
VERBOSE_PROGRESS = True


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = _project_root()
    sys.path.insert(0, str(root))
    os.environ.setdefault("PYTHONPATH", str(root))

    from linkedin_url.auth.fetch import fetch_html_sync
    from linkedin_url.auth.paths import default_storage_state_path
    from linkedin_url.company_expand import expand_company, expand_company_from_saved_html
    from linkedin_url.normalize import normalize_linkedin_url

    out_dir = root / OUTPUT_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    state = STATE_PATH or default_storage_state_path()
    proxy = PROXY or os.getenv("LINKEDIN_PROXY") or os.getenv("HTTPS_PROXY")

    seed = normalize_linkedin_url(COMPANY_URL)
    if not seed.company_vanity:
        print("错误：不是公司 URL", file=sys.stderr)
        return 2

    slug = re.sub(r"[^\w\-]+", "_", seed.company_vanity)[:60]

    print("公司:", seed.canonical_url)
    print("会话:", state)
    print("代理:", proxy or "(无)")
    print("PARSE_ONLY:", PARSE_ONLY)
    print("-" * 60)

    if PARSE_ONLY:

        def load(name: str) -> str:
            p = out_dir / f"{SAVE_PREFIX}_{name}.html"
            if not p.is_file():
                return ""
            return p.read_text(encoding="utf-8", errors="replace")

        html_by_label = {
            "overview": load("overview"),
            "jobs": load("jobs"),
            "people": load("people"),
            "posts": load("posts"),
        }
        if not html_by_label["overview"].strip():
            print(f"错误：缺少 {out_dir / (SAVE_PREFIX + '_overview.html')}", file=sys.stderr)
            return 2
        result = expand_company_from_saved_html(
            html_by_label=html_by_label,
            company_canonical_url=seed.canonical_url,
        )
    else:
        if not state.is_file():
            print("错误：请先 python -m linkedin_url login", file=sys.stderr)
            return 2

        def fetch(u: str) -> str:
            """底层一次 Playwright 请求（含 settle + 滚动 + 展开），可能耗时数分钟。"""
            t0 = time.perf_counter()
            short = u if len(u) <= 140 else u[:137] + "..."
            print(f"    [fetch] 开始 Playwright: {short}", flush=True)
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
                dt = time.perf_counter() - t0
                print(f"    [fetch] 异常 ({dt:.1f}s): {e!r}", flush=True)
                raise
            dt = time.perf_counter() - t0
            print(
                f"    [fetch] 结束 ({dt:.1f}s)，HTML {len(body)} 字符",
                flush=True,
            )
            return body

        print(
            "开始 expand_company：依次抓取 overview → jobs → people → posts，"
            "再抓取 jobs/search；单页含滚动/展开，请耐心等待。",
            flush=True,
        )
        t_expand = time.perf_counter()
        result = expand_company(
            COMPANY_URL,
            fetch,
            fetch_jobs_search_pages=FETCH_JOBS_SEARCH_PAGES,
            max_jobs_search_fetch=MAX_JOBS_SEARCH_FETCH,
            save_html_dir=out_dir,
            save_prefix=slug,
            verbose=VERBOSE_PROGRESS,
        )
        print(
            f"expand_company 总耗时 {time.perf_counter() - t_expand:.1f}s；"
            f"已保存 HTML / meta 至: {out_dir}",
            flush=True,
        )

    buckets = result["buckets"]
    order = [
        ("【公司主页】", "company"),
        ("【公司子页 tabs】", "company_tab"),
        ("【职位搜索页】", "jobs_search"),
        ("【单职位 job】", "job"),
        ("【个人 profile】", "profile"),
        ("【动态 post】", "post"),
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

    print(f"\n【职位 ID 去重数量】{len(result['job_ids'])}")
    print(f"【规范职位 URL 数量】{len(result['job_view_urls'])}")
    print(f"【额外抓取 jobs/search 页数】{result.get('jobs_search_pages_fetched', 0)}")

    out_json = root / "company_expand_output.json"
    out_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("\n已写入:", out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
