"""单条职位页：抓取 HTML 后经 discover 扩展链接（与 profile/company/post 并列）。"""

from __future__ import annotations

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


def expand_job_page(
    job_url: str,
    fetch_html: Callable[[str], str],
    *,
    filter_nav: bool = True,
) -> dict[str, Any]:
    seed = normalize_linkedin_url(job_url)
    if seed.entity_type != LinkedInEntityType.JOB or not seed.canonical_url:
        raise ValueError(f"不是职位 URL：{job_url}")
    canonical = seed.canonical_url
    html = fetch_html(canonical)
    urls = discover_from_html_deep(html, base_url=canonical)
    if filter_nav:
        urls = filter_global_nav_urls(urls)
    urls = _dedupe_preserve_order(urls)
    buckets = bucket_urls_by_category(urls, seed_vanity=None)
    return {
        "buckets": buckets,
        "urls_discovered": urls,
        "canonical_job_url": canonical,
        "job_id": seed.job_id,
    }
