"""
以公司主页为种子：抓取 Overview / Jobs / People / Posts 子页，合并链接并从 HTML、职位搜索 URL 中抽取 ``job_id``。

公司 ``/posts/`` 列表与单条动态页中，``discover_from_html_deep`` 可发现：评论者 ``/in/…``、侧栏推荐的其它公司与个人等
（依赖链接出现在 DOM 或内嵌 JSON）。

无法保证集齐 160+ 职位或 1500+ 员工（分页、懒加载、权限）；通过深链提取 + 多轮滚动/展开尽量覆盖。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from linkedin_url.discover import discover_from_html_deep
from linkedin_url.normalize import normalize_linkedin_url
from linkedin_url.profile_expand import bucket_urls_by_category, filter_global_nav_urls


_RE_JOB_VIEW = re.compile(r"/jobs/view/(\d{6,})", re.I)
_RE_CURRENT_JOB = re.compile(r"currentJobId=(\d+)", re.I)
_RE_ORIGIN_POSTINGS = re.compile(r'originToLandingJobPostings=([^&"\s<>]+)', re.I)


def job_ids_from_jobs_search_url(url: str) -> list[str]:
    """从 ``/jobs/search/?...`` 查询串解析 ``currentJobId`` 与 ``originToLandingJobPostings``。"""
    q = parse_qs(urlparse(url).query)
    out: list[str] = []
    for k in ("currentJobId",):
        for v in q.get(k) or []:
            if v.isdigit():
                out.append(v)
    for v in q.get("originToLandingJobPostings") or []:
        blob = unquote(v)
        for part in blob.split(","):
            p = part.strip()
            if p.isdigit():
                out.append(p)
    # 去重保序
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def extract_job_ids_from_html(html: str | None) -> set[str]:
    """从整页文本中提取职位 ID（含内嵌 JSON、href）。"""
    if not html:
        return set()
    ids: set[str] = set()
    for m in _RE_JOB_VIEW.finditer(html):
        ids.add(m.group(1))
    for m in _RE_CURRENT_JOB.finditer(html):
        ids.add(m.group(1))
    for m in _RE_ORIGIN_POSTINGS.finditer(html):
        blob = unquote(m.group(1))
        for part in blob.split(","):
            p = part.strip()
            if p.isdigit():
                ids.add(p)
    return ids


def canonical_job_view_urls(job_ids: set[str]) -> list[str]:
    return sorted({f"https://www.linkedin.com/jobs/view/{jid}/" for jid in job_ids})


def expand_company(
    company_url: str,
    fetch_html: Callable[[str], str],
    *,
    fetch_jobs_tab: bool = True,
    fetch_people_tab: bool = True,
    fetch_posts_tab: bool = True,
    fetch_jobs_search_pages: bool = True,
    max_jobs_search_fetch: int = 5,
    filter_nav: bool = True,
    save_html_dir: Path | None = None,
    save_prefix: str = "company",
    verbose: bool = False,
) -> dict[str, Any]:
    """
    抓取公司主页及 ``/jobs/``、``/people/``、``/posts/``，合并 ``discover_from_html_deep`` 与职位 ID 正则。

    返回 ``buckets``（与 ``classify_linkedin_url`` 一致）以及 ``job_ids``、``job_view_urls``。

    ``verbose=True`` 时向 stdout 打印每步抓取进度（含耗时），并 ``flush``，便于长时间任务观察。
    """
    def _log(msg: str) -> None:
        if verbose:
            print(msg, flush=True)

    seed = normalize_linkedin_url(company_url)
    if seed.entity_type.value != "company" or not seed.company_vanity:
        raise ValueError(f"不是公司主页 URL：{company_url}")

    slug = seed.company_vanity
    base = seed.canonical_url.rstrip("/") + "/"

    urls: list[str] = []
    combined_html: list[str] = []
    jobs_search_pages_fetched = 0

    pages: list[tuple[str, str]] = [(base, "overview")]
    if fetch_jobs_tab:
        pages.append((f"{base}jobs/", "jobs"))
    if fetch_people_tab:
        pages.append((f"{base}people/", "people"))
    if fetch_posts_tab:
        pages.append((f"{base}posts/", "posts"))

    total_main = len(pages)
    for idx, (page_url, label) in enumerate(pages, start=1):
        _log(f"[公司页 {idx}/{total_main}] 开始: {label} → {page_url}")
        t0 = time.perf_counter()
        try:
            h = fetch_html(page_url)
            combined_html.append(h)
            if save_html_dir is not None:
                save_html_dir.mkdir(parents=True, exist_ok=True)
                (save_html_dir / f"{save_prefix}_{label}.html").write_text(
                    h, encoding="utf-8"
                )
            n_before = len(urls)
            urls.extend(discover_from_html_deep(h, base_url=page_url))
            n_new = len(urls) - n_before
            dt = time.perf_counter() - t0
            _log(
                f"[公司页 {idx}/{total_main}] 完成: {label} | "
                f"HTML {len(h)} 字符 | 本页新增链接 {n_new} | {dt:.1f}s"
            )
        except Exception as e:
            dt = time.perf_counter() - t0
            _log(f"[公司页 {idx}/{total_main}] 失败: {label} | {e!r} | {dt:.1f}s")
            continue

    if fetch_jobs_search_pages:
        seen_search: set[str] = set()
        for u in list(dict.fromkeys(urls)):
            if "/jobs/search" not in u:
                continue
            nu = u.split("#", 1)[0].strip()
            if nu in seen_search or len(seen_search) >= max_jobs_search_fetch:
                continue
            seen_search.add(nu)
            k = len(seen_search)
            _log(f"[职位搜索 {k}/{max_jobs_search_fetch}] 开始 → {nu[:120]}{'…' if len(nu) > 120 else ''}")
            t0 = time.perf_counter()
            try:
                h2 = fetch_html(nu)
                combined_html.append(h2)
                jobs_search_pages_fetched += 1
                if save_html_dir is not None:
                    safe = re.sub(r"[^\w\-]+", "_", str(len(seen_search)))[:20]
                    (save_html_dir / f"{save_prefix}_jobs_search_{safe}.html").write_text(
                        h2, encoding="utf-8"
                    )
                n_before = len(urls)
                urls.extend(discover_from_html_deep(h2, base_url=nu))
                n_new = len(urls) - n_before
                dt = time.perf_counter() - t0
                _log(
                    f"[职位搜索 {k}/{max_jobs_search_fetch}] 完成 | "
                    f"HTML {len(h2)} 字符 | 新增链接 {n_new} | {dt:.1f}s"
                )
            except Exception as e:
                dt = time.perf_counter() - t0
                _log(f"[职位搜索 {k}/{max_jobs_search_fetch}] 失败 | {e!r} | {dt:.1f}s")
                continue

    _log("正在合并 HTML、提取 job_id 与分类…")
    job_ids = extract_job_ids_from_html("\n".join(combined_html))
    for u in list(dict.fromkeys(urls)):
        if "/jobs/search" in u:
            job_ids.update(job_ids_from_jobs_search_url(u))

    for jid in job_ids:
        urls.append(f"https://www.linkedin.com/jobs/view/{jid}/")

    if filter_nav:
        urls = filter_global_nav_urls(urls)

    buckets = bucket_urls_by_category(urls, seed_vanity=None)

    jvu = canonical_job_view_urls(job_ids)
    out: dict[str, Any] = {
        "buckets": buckets,
        "job_ids": sorted(job_ids, key=int),
        "job_view_urls": jvu,
        "company_slug": slug,
        "canonical_company_url": base.rstrip("/") + "/",
        "jobs_search_pages_fetched": jobs_search_pages_fetched,
    }
    if save_html_dir is not None:
        save_html_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "canonical_company_url": out["canonical_company_url"],
            "job_id_count": len(job_ids),
            "jobs_search_pages_fetched": jobs_search_pages_fetched,
        }
        (save_html_dir / f"{save_prefix}_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return out


def expand_company_from_saved_html(
    *,
    html_by_label: dict[str, str],
    company_canonical_url: str,
    filter_nav: bool = True,
) -> dict[str, Any]:
    """``html_by_label`` 含 ``overview``、``jobs``、``people``、``posts`` 等键，值为 HTML 字符串。"""
    urls: list[str] = []
    combined: list[str] = []
    base = company_canonical_url.rstrip("/") + "/"

    order = ("overview", "jobs", "people", "posts")
    for key in order:
        h = html_by_label.get(key) or ""
        if not h.strip():
            continue
        combined.append(h)
        page_url = {
            "overview": base,
            "jobs": f"{base}jobs/",
            "people": f"{base}people/",
            "posts": f"{base}posts/",
        }.get(key, base)
        urls.extend(discover_from_html_deep(h, base_url=page_url))

    job_ids = extract_job_ids_from_html("\n".join(combined))
    for u in list(urls):
        if "/jobs/search" in u:
            job_ids.update(job_ids_from_jobs_search_url(u))
    for jid in job_ids:
        urls.append(f"https://www.linkedin.com/jobs/view/{jid}/")

    if filter_nav:
        urls = filter_global_nav_urls(urls)

    seed = normalize_linkedin_url(company_canonical_url)
    slug = seed.company_vanity or ""

    buckets = bucket_urls_by_category(urls, seed_vanity=None)
    jvu = canonical_job_view_urls(job_ids)
    return {
        "buckets": buckets,
        "job_ids": sorted(job_ids, key=int),
        "job_view_urls": jvu,
        "company_slug": slug,
        "canonical_company_url": base.rstrip("/") + "/",
        "jobs_search_pages_fetched": 0,
    }
