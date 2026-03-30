"""
以单条 LinkedIn 动态（feed/update 或 ``/posts/…activity-…``）为种子：访问详情页 HTML，
经 ``discover_from_html_deep`` 抽取评论者 ``/in/…``、侧栏公司与个人等链接。

与 profile / company 扩展脚本一致：先独立访问该 URL，再归类；不保证权限或懒加载下链接完整。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from linkedin_url.discover import discover_from_html_deep
from linkedin_url.models import LinkedInEntityType
from linkedin_url.normalize import normalize_linkedin_url
from linkedin_url.profile_expand import bucket_urls_by_category, filter_global_nav_urls


def _dedupe_preserve_order(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def expand_post_page(
    post_url: str,
    fetch_html: Callable[[str], str],
    *,
    filter_nav: bool = True,
    verbose: bool = False,
    save_html_dir: Path | None = None,
) -> dict[str, Any]:
    """
    抓取一条动态详情页，归一 URL 后请求 ``canonical``（feed/update/urn:li:activity:…），再发现链接。

    返回 ``buckets``、``urls_discovered``（去重列表）、``canonical_post_url``、``activity_id``。
    """
    seed = normalize_linkedin_url(post_url)
    if seed.entity_type != LinkedInEntityType.POST or not seed.canonical_url:
        raise ValueError(f"不是可识别的动态 URL：{post_url}")

    canonical = seed.canonical_url
    t0 = time.perf_counter()
    if verbose:
        print(f"[post] 开始 fetch: {canonical}", flush=True)
    html = fetch_html(canonical)
    if verbose:
        print(
            f"[post] 完成 fetch ({time.perf_counter() - t0:.1f}s)，HTML {len(html)} 字符",
            flush=True,
        )
    if save_html_dir is not None and seed.activity_id:
        save_html_dir.mkdir(parents=True, exist_ok=True)
        p = save_html_dir / f"activity_{seed.activity_id}_detail.html"
        p.write_text(html, encoding="utf-8")
        if verbose:
            print(f"[post] 已保存 HTML → {p}", flush=True)

    urls = discover_from_html_deep(html, base_url=canonical)
    if filter_nav:
        urls = filter_global_nav_urls(urls)
    urls = _dedupe_preserve_order(urls)
    buckets = bucket_urls_by_category(urls, seed_vanity=None)

    return {
        "buckets": buckets,
        "urls_discovered": urls,
        "canonical_post_url": canonical,
        "activity_id": seed.activity_id,
        "original_input_url": post_url.strip(),
    }


def expand_post_from_saved_html(
    *,
    html: str,
    post_canonical_url: str,
    filter_nav: bool = True,
) -> dict[str, Any]:
    """仅解析已保存的详情页 HTML，不发起网络请求。"""
    seed = normalize_linkedin_url(post_canonical_url)
    if seed.entity_type != LinkedInEntityType.POST or not seed.canonical_url:
        raise ValueError(f"不是可识别的动态 URL：{post_canonical_url}")

    canonical = seed.canonical_url
    urls = discover_from_html_deep(html, base_url=canonical)
    if filter_nav:
        urls = filter_global_nav_urls(urls)
    urls = _dedupe_preserve_order(urls)
    buckets = bucket_urls_by_category(urls, seed_vanity=None)

    return {
        "buckets": buckets,
        "urls_discovered": urls,
        "canonical_post_url": canonical,
        "activity_id": seed.activity_id,
        "original_input_url": post_canonical_url.strip(),
    }


def expand_post_pages_merged(
    post_urls: list[str],
    fetch_html: Callable[[str], str],
    *,
    filter_nav: bool = True,
    verbose: bool = False,
    save_html_dir: Path | None = None,
) -> dict[str, Any]:
    """
    依次抓取多条动态详情页，合并去重后再 ``bucket_urls_by_category``。
    ``per_post`` 保留每条抓取的元信息与单条 ``urls_discovered``。
    """
    merged: list[str] = []
    per_post: list[dict[str, Any]] = []
    for i, raw in enumerate(post_urls, start=1):
        one = expand_post_page(
            raw,
            fetch_html,
            filter_nav=filter_nav,
            verbose=verbose,
            save_html_dir=save_html_dir,
        )
        merged.extend(one["urls_discovered"])
        per_post.append(
            {
                "index": i,
                "original_input_url": one["original_input_url"],
                "canonical_post_url": one["canonical_post_url"],
                "activity_id": one["activity_id"],
                "urls_discovered_count": len(one["urls_discovered"]),
            }
        )
    merged = _dedupe_preserve_order(merged)
    if filter_nav:
        merged = filter_global_nav_urls(merged)
        merged = _dedupe_preserve_order(merged)
    buckets = bucket_urls_by_category(merged, seed_vanity=None)
    return {
        "buckets": buckets,
        "urls_discovered": merged,
        "per_post": per_post,
        "post_count": len(post_urls),
    }


def merge_post_expand_results(
    parts: list[dict[str, Any]],
    *,
    filter_nav: bool = True,
) -> dict[str, Any]:
    """
    将多条 ``expand_post_page`` / ``expand_post_from_saved_html`` 的返回合并为一条
    （去重后再 ``bucket_urls_by_category``），用于离线解析多条 HTML 时。
    """
    merged: list[str] = []
    per_post: list[dict[str, Any]] = []
    for p in parts:
        merged.extend(p.get("urls_discovered") or [])
        per_post.append(
            {
                "original_input_url": p.get("original_input_url"),
                "canonical_post_url": p.get("canonical_post_url"),
                "activity_id": p.get("activity_id"),
                "urls_discovered_count": len(p.get("urls_discovered") or []),
            }
        )
    merged = _dedupe_preserve_order(merged)
    if filter_nav:
        merged = filter_global_nav_urls(merged)
        merged = _dedupe_preserve_order(merged)
    buckets = bucket_urls_by_category(merged, seed_vanity=None)
    return {
        "buckets": buckets,
        "urls_discovered": merged,
        "per_post": per_post,
        "post_count": len(parts),
    }
