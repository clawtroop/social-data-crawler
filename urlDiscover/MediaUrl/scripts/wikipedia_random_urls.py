#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 MediaWiki Action API（``list=random``，标准库 ``urllib``）随机获取英文维基主命名空间词条 URL。

不依赖 ``wikipedia-api``/httpx：部分 Windows 环境下 httpx 连接 en.wikipedia.org 会超时，而 urllib 正常。

User-Agent：``wikipedia_url/user_agent.py``（``WIKIPEDIA_USER_AGENT`` 或 ``.secrets/wikipedia_user_agent.txt``）。

运行（项目根目录）：
    set PYTHONPATH=d:\\Code\\MediaUrl
    python scripts/wikipedia_random_urls.py
    python scripts/wikipedia_random_urls.py -n 20

环境变量：
    WIKIPEDIA_HTTP_TIMEOUT — HTTP 超时秒数（默认 60）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
from pathlib import Path
DEFAULT_HTTP_TIMEOUT_S = 60.0
OUTPUT_SUBDIR = "output"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_package_path() -> None:
    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="随机获取 en.wikipedia.org 主命名空间词条 URL（MediaWiki list=random，urllib）",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=10,
        metavar="N",
        help="随机词条数量（1–500，默认 10）",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="写入 JSON 文件路径（默认：output/wikipedia_random_<n>.json）",
    )
    parser.add_argument(
        "--include-redirects",
        action="store_true",
        help="包含重定向页（默认仅非重定向词条）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SEC",
        help=f"请求超时秒数（默认：环境变量 WIKIPEDIA_HTTP_TIMEOUT 或 {DEFAULT_HTTP_TIMEOUT_S:g}）",
    )
    args = parser.parse_args()

    _ensure_package_path()
    from wikipedia_url.mw_client import query_random_titles
    from wikipedia_url.user_agent import get_wikipedia_user_agent
    from wikipedia_url.wiki_url import wiki_article_url_readable

    n = max(1, min(500, args.count))
    if args.timeout is not None and args.timeout <= 0:
        print("错误：--timeout 须为正数", file=sys.stderr)
        return 2
    timeout_s = args.timeout
    if timeout_s is None:
        env_t = os.getenv("WIKIPEDIA_HTTP_TIMEOUT")
        if env_t is not None and env_t.strip() != "":
            try:
                timeout_s = float(env_t)
            except ValueError:
                print("错误：WIKIPEDIA_HTTP_TIMEOUT 须为数字", file=sys.stderr)
                return 2
        else:
            timeout_s = DEFAULT_HTTP_TIMEOUT_S

    ua = get_wikipedia_user_agent()
    rn_f = "all" if args.include_redirects else "nonredirects"

    try:
        raw = query_random_titles(
            "en",
            limit=n,
            user_agent=ua,
            timeout=timeout_s,
            rnfilterredirects=rn_f,
        )
    except (TimeoutError, OSError, urllib.error.URLError) as e:
        print(f"错误：请求维基 API 失败：{e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1

    rows: list[dict[str, object]] = []
    for entry in raw:
        title = entry.get("title", "")
        pid = entry.get("id")
        rows.append(
            {
                "title": title,
                "pageid": int(pid) if pid is not None else -1,
                "url": wiki_article_url_readable("en", title),
            }
        )

    root = _project_root()
    out_path = args.output
    if out_path is None:
        out_dir = root / OUTPUT_SUBDIR
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"wikipedia_random_{n}.json"

    payload = {
        "lang": "en",
        "source": "MediaWiki API list=random (urllib)",
        "http_timeout_sec": timeout_s,
        "count_requested": n,
        "count_returned": len(rows),
        "user_agent_note": "WIKIPEDIA_USER_AGENT env or .secrets/wikipedia_user_agent.txt; see wikipedia_url/user_agent.py",
        "articles": rows,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("已写入:", out_path, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
