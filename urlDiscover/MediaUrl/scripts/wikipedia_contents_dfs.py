#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从维基「内容总目录」出发，沿 ``Wikipedia:Contents/...`` **项目页**做深度优先遍历；
**只保存**各目录页链出的 **主命名空间条目**（``ns=0``）的 URL，不保存 ``Wikipedia:Contents/...`` 自身。

URL 为可读形式：``https://{lang}.wikipedia.org/wiki/...`` 中路径对 ``:``、``/`` 不写成 ``%3A``、``%2F``（空格仍为 ``_``）。

种子页示例（英文）：<https://en.wikipedia.org/wiki/Wikipedia:Contents>

扩展规则：从链出中只把 ``Wikipedia`` 命名空间（``ns=4``）且标题以 ``--prefix`` 为前缀的页面继续入栈。

停止条件（均可选；先到先停）：
  * ``--max-seconds`` / ``--time-limit``：墙钟时间
  * ``--max-depth``：目录树深度（根 ``Wikipedia:Contents`` 为 0）
  * ``--max-pages``：最多访问的 **Contents 目录页** 数（不统计主命名空间条目）

默认：**不限制**深度与目录页数量；若不限时则一直爬到栈空。

输出目录（默认 ``output/content/{lang}/``）：
  * ``crawl.json`` — 元数据 + ``articles``（主命名空间条目列表）
  * ``articles/`` 下按条目标题建子目录，``page.json`` 含 ``title``、``url``、``discovered_from``

运行：
    set PYTHONPATH=d:\\Code\\MediaUrl
    python scripts/wikipedia_contents_dfs.py --max-seconds 300
    python scripts/wikipedia_contents_dfs.py --lang en --time-limit 120 --output-dir output/content/en
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import re
import urllib.error
from pathlib import Path

# 主命名空间条目 vs Wikipedia 项目页（Contents 树）
_NS_MAIN_ARTICLE = 0
_NS_WIKIPEDIA_PROJECT = 4

DEFAULT_HTTP_TIMEOUT_S = 60.0
DEFAULT_PREFIX = "Wikipedia:Contents"
DEFAULT_SEED = "Wikipedia:Contents"
DEFAULT_LANG = "en"
OUTPUT_SUBDIR = "output"
CONTENT_SUBDIR = "content"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_package_path() -> None:
    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _resolve_http_timeout(cli_timeout: float | None) -> float:
    if cli_timeout is not None:
        if cli_timeout <= 0:
            raise ValueError("--timeout 须为正数")
        return cli_timeout
    env_t = os.getenv("WIKIPEDIA_HTTP_TIMEOUT")
    if env_t is not None and env_t.strip() != "":
        return float(env_t)
    return DEFAULT_HTTP_TIMEOUT_S


def _under_prefix(title: str, prefix: str) -> bool:
    return title == prefix or title.startswith(prefix + "/")


_WIN_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_path_segment(segment: str) -> str:
    """将维基标题路径段转为可安全用作目录名的字符串。"""
    s = segment.strip().replace(" ", "_")
    s = s.replace(":", "_")
    s = _WIN_INVALID.sub("_", s)
    s = s.strip("._ ") or "_"
    return s[:200]


def _title_to_rel_dir(title: str) -> Path:
    """主命名空间条目标题路径 → 相对目录（段内 ``:``/``/`` 会经 ``_sanitize_path_segment`` 处理）。"""
    parts = [p for p in title.split("/") if p != ""]
    if not parts:
        return Path("_")
    return Path(*(_sanitize_path_segment(p) for p in parts))


def _print_json_utf8(obj: object) -> None:
    """在 Windows GBK 等控制台编码下仍可输出含非 ASCII 的 JSON。"""
    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))


def _dfs_contents(
    *,
    lang: str,
    user_agent: str,
    http_timeout: float,
    seed: str,
    prefix: str,
    max_depth: int | None,
    max_pages: int | None,
    max_seconds: float | None,
) -> tuple[list[dict[str, object]], str]:
    """
    深度优先遍历 Contents 项目页；收集各页链出的主命名空间条目（ns=0）。

    :return: (article_rows, stopped_reason)
    """
    from wikipedia_url.mw_client import query_all_links, query_page_exists
    from wikipedia_url.wiki_url import wiki_article_url_readable

    t0 = time.monotonic()
    stack: list[tuple[str, int]] = [(seed, 0)]
    seen_contents: set[str] = set()
    article_seen: set[str] = set()
    articles: list[dict[str, object]] = []
    stopped = "complete"

    while stack:
        if max_seconds is not None and (time.monotonic() - t0) >= max_seconds:
            stopped = "time_limit"
            break
        if max_pages is not None and max_pages > 0 and len(seen_contents) >= max_pages:
            stopped = "page_limit"
            break

        title, depth = stack.pop()
        if max_depth is not None and depth > max_depth:
            continue

        exists, canonical = query_page_exists(
            lang,
            title,
            user_agent=user_agent,
            timeout=http_timeout,
        )
        if not exists:
            continue

        if not _under_prefix(canonical, prefix):
            continue
        if canonical in seen_contents:
            continue

        seen_contents.add(canonical)

        link_entries = query_all_links(
            lang,
            canonical,
            user_agent=user_agent,
            timeout=http_timeout,
        )

        contents_children: list[str] = []
        for ln in link_entries:
            lt = (ln.get("title") or "").strip()
            if not lt:
                continue
            ns = int(ln.get("ns", -1))
            if ns == _NS_MAIN_ARTICLE:
                if lt not in article_seen:
                    article_seen.add(lt)
                    articles.append(
                        {
                            "title": lt,
                            "url": wiki_article_url_readable(lang, lt),
                            "discovered_from": canonical,
                            "contents_depth": depth,
                        }
                    )
            elif ns == _NS_WIKIPEDIA_PROJECT and _under_prefix(lt, prefix):
                contents_children.append(lt)

        contents_children.sort()
        if max_depth is None or depth < max_depth:
            for lt in reversed(contents_children):
                if lt in seen_contents:
                    continue
                stack.append((lt, depth + 1))

    return articles, stopped


def _write_structured_pages(
    base_dir: Path,
    *,
    payload: dict[str, object],
    articles: list[dict[str, object]],
) -> tuple[Path, list[Path]]:
    """
    写入 ``crawl.json``；在 ``articles/`` 下按**主命名空间条目标题**建目录，``page.json`` 含条目信息与来源目录页。
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    articles_root = base_dir / "articles"
    articles_root.mkdir(exist_ok=True)
    article_files: list[Path] = []
    for r in articles:
        title = str(r["title"])
        url = str(r["url"])
        rel = _title_to_rel_dir(title)
        dir_path = articles_root / rel
        dir_path.mkdir(parents=True, exist_ok=True)
        p = dir_path / "page.json"
        p.write_text(
            json.dumps(
                {
                    "title": title,
                    "url": url,
                    "discovered_from": r.get("discovered_from"),
                    "contents_depth": r.get("contents_depth"),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        article_files.append(p)

    crawl_path = base_dir / "crawl.json"
    crawl_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return crawl_path, article_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="遍历 Wikipedia:Contents 目录树，只保存主命名空间条目 URL 至 output/content/{lang}/articles/",
    )
    parser.add_argument(
        "--lang",
        default=DEFAULT_LANG,
        help=f"语言子域（默认 {DEFAULT_LANG}），用于 API 与 URL",
    )
    parser.add_argument(
        "--seed",
        default=DEFAULT_SEED,
        help=f"起始页面标题（默认 {DEFAULT_SEED}）",
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help=f"只扩展此前缀下的页面（默认 {DEFAULT_PREFIX}）",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        metavar="D",
        help="最大深度：根为 0；达到该深度后不再向下（默认不限制）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        metavar="N",
        help="最多访问的 Wikipedia:Contents 目录页数；0 表示不限制（默认 0）",
    )
    parser.add_argument(
        "--max-seconds",
        "--time-limit",
        type=float,
        default=None,
        dest="max_seconds",
        metavar="SEC",
        help="墙钟时间上限（秒），到点即停并保存已抓取 URL；不设则不限时（直至栈空或遇其它上限）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SEC",
        help=f"单次 HTTP 超时（默认 {DEFAULT_HTTP_TIMEOUT_S:g} 或 WIKIPEDIA_HTTP_TIMEOUT）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="输出根目录（默认 <项目根>/output/content/<lang>/）",
    )
    args = parser.parse_args()

    _ensure_package_path()
    from wikipedia_url.user_agent import get_wikipedia_user_agent

    lang = args.lang.strip().lower() or DEFAULT_LANG

    if args.max_depth is not None and args.max_depth < 0:
        print("错误：--max-depth 不能为负", file=sys.stderr)
        return 2
    if args.max_pages < 0:
        print("错误：--max-pages 不能为负（0=不限制）", file=sys.stderr)
        return 2
    if args.max_seconds is not None and args.max_seconds <= 0:
        print("错误：--max-seconds / --time-limit 须为正数", file=sys.stderr)
        return 2

    try:
        timeout_s = _resolve_http_timeout(args.timeout)
    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2

    ua = get_wikipedia_user_agent()
    max_pages_eff: int | None = None if args.max_pages == 0 else args.max_pages

    try:
        articles, stopped = _dfs_contents(
            lang=lang,
            user_agent=ua,
            http_timeout=timeout_s,
            seed=args.seed,
            prefix=args.prefix,
            max_depth=args.max_depth,
            max_pages=max_pages_eff,
            max_seconds=args.max_seconds,
        )
    except (TimeoutError, OSError, urllib.error.URLError) as e:
        print(f"错误：请求维基 API 失败：{e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1

    root = _project_root()
    base_dir = args.output_dir
    if base_dir is None:
        base_dir = root / OUTPUT_SUBDIR / CONTENT_SUBDIR / lang
    else:
        base_dir = Path(base_dir)
        if not base_dir.is_absolute():
            base_dir = root / base_dir

    payload: dict[str, object] = {
        "lang": lang,
        "seed": args.seed,
        "prefix": args.prefix,
        "stopped_reason": stopped,
        "limits": {
            "max_depth": args.max_depth,
            "max_pages": args.max_pages,
            "max_pages_effective": max_pages_eff,
            "max_seconds": args.max_seconds,
            "http_timeout_sec": timeout_s,
        },
        "count_articles": len(articles),
        "articles": articles,
    }

    crawl_path, article_paths = _write_structured_pages(
        base_dir,
        payload=payload,
        articles=articles,
    )

    _print_json_utf8(payload)
    print("已写入:", crawl_path, file=sys.stderr)
    print(f"  条目 page.json 数: {len(article_paths)}（目录结构见 {base_dir}）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
