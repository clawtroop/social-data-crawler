"""
按广度优先迭代：对 Profile / Company / Post / Job 四类标准 URL 分别调用既有扩展逻辑，
将新发现的链接再归一为四类标准形式，去重后继续扩展，直至队列为空或达到最大深度。

``max_expand_depth``：仅对 ``depth < max_expand_depth`` 的节点执行抓取与扩展；
``None`` 表示不限制层数（直至无新节点或全部已扩展过）。

``max_runtime_seconds``：从进入主循环起计时，超时则停止遍历并返回已收集的四类 URL 与统计；
``None`` 表示不限总运行时间。
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from linkedin_url.company_expand import expand_company
from linkedin_url.job_expand import expand_job_page
from linkedin_url.models import LinkedInEntityType
from linkedin_url.normalize import normalize_linkedin_url, standard_canonical_url
from linkedin_url.post_expand import expand_post_page
from linkedin_url.profile_expand import expand_profile_page


def _flatten_buckets(buckets: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for vs in buckets.values():
        out.extend(vs)
    return out


def _raw_urls_from_expand(
    entity: LinkedInEntityType,
    result: dict[str, Any],
) -> list[str]:
    if entity == LinkedInEntityType.PROFILE:
        return _flatten_buckets(result)
    if entity == LinkedInEntityType.COMPANY:
        u = _flatten_buckets(result["buckets"])
        u.extend(result.get("job_view_urls") or [])
        return u
    if entity == LinkedInEntityType.POST:
        return list(result.get("urls_discovered") or [])
    if entity == LinkedInEntityType.JOB:
        return list(result.get("urls_discovered") or [])
    return []


def _expand_one(
    canonical: str,
    fetch_html: Callable[[str], str],
    *,
    expand_profile_kwargs: dict[str, Any],
    expand_company_kwargs: dict[str, Any],
    expand_post_kwargs: dict[str, Any],
    expand_job_kwargs: dict[str, Any],
) -> dict[str, Any]:
    seed = normalize_linkedin_url(canonical)
    et = seed.entity_type
    if et == LinkedInEntityType.PROFILE:
        return expand_profile_page(
            canonical,
            fetch_html=fetch_html,
            **expand_profile_kwargs,
        )
    if et == LinkedInEntityType.COMPANY:
        return expand_company(
            canonical,
            fetch_html,
            **expand_company_kwargs,
        )
    if et == LinkedInEntityType.POST:
        return expand_post_page(
            canonical,
            fetch_html,
            **expand_post_kwargs,
        )
    if et == LinkedInEntityType.JOB:
        return expand_job_page(
            canonical,
            fetch_html,
            **expand_job_kwargs,
        )
    raise ValueError(f"无法扩展非四类 URL：{canonical}")


@dataclass
class BfsExpandResult:
    profiles: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)
    jobs: list[str] = field(default_factory=list)
    posts: list[str] = field(default_factory=list)
    expansions_run: int = 0
    max_depth_seen: int = 0
    errors: list[str] = field(default_factory=list)
    stopped_by_time_limit: bool = False

    def as_four_dict(self) -> dict[str, list[str]]:
        return {
            "profiles": self.profiles,
            "companies": self.companies,
            "jobs": self.jobs,
            "posts": self.posts,
        }


def run_bfs_expand(
    seed_urls: list[str],
    fetch_html: Callable[[str], str],
    *,
    max_expand_depth: int | None = None,
    max_runtime_seconds: float | None = None,
    expand_profile_kwargs: dict[str, Any] | None = None,
    expand_company_kwargs: dict[str, Any] | None = None,
    expand_post_kwargs: dict[str, Any] | None = None,
    expand_job_kwargs: dict[str, Any] | None = None,
    verbose: bool = False,
) -> tuple[BfsExpandResult, dict[str, Any]]:
    """
    ``seed_urls``：任意可解析为四类的 URL；会先去重并归一。

    ``max_expand_depth``：仅扩展深度 ``d`` 满足 ``d < max_expand_depth`` 的节点（根种子深度为 0）。
    ``None`` 表示不限制。

    ``max_runtime_seconds``：总运行时间上限（秒），从即将处理队列中第一个待扩展节点前开始计时；
    超时则立即停止，保留已发现的四类 URL 与已入队但未扩展的节点（见 ``stats['queue_remaining']``）。

    返回 ``(BfsExpandResult, stats_dict)``。
    """
    t_start = time.perf_counter()
    ep = dict(expand_profile_kwargs or {})
    ep.setdefault("also_fetch_activity", True)
    ep.setdefault("filter_nav", True)

    ec = dict(expand_company_kwargs or {})
    ec.setdefault("fetch_jobs_tab", True)
    ec.setdefault("fetch_people_tab", True)
    ec.setdefault("fetch_posts_tab", True)
    ec.setdefault("fetch_jobs_search_pages", True)
    ec.setdefault("max_jobs_search_fetch", 5)
    ec.setdefault("filter_nav", True)
    ec.setdefault("save_html_dir", None)
    ec.setdefault("verbose", False)

    epo = dict(expand_post_kwargs or {})
    epo.setdefault("filter_nav", True)
    epo.setdefault("verbose", False)
    epo.setdefault("save_html_dir", None)

    ej = dict(expand_job_kwargs or {})
    ej.setdefault("filter_nav", True)

    profiles: set[str] = set()
    companies: set[str] = set()
    jobs: set[str] = set()
    posts: set[str] = set()

    queue: deque[tuple[str, int]] = deque()
    expanded: set[str] = set()
    errors: list[str] = []

    for raw in seed_urls:
        std = standard_canonical_url(raw)
        if not std:
            errors.append(f"无法归一为四类标准 URL，已跳过: {raw!r}")
            continue
        r = normalize_linkedin_url(std)
        if r.entity_type == LinkedInEntityType.PROFILE:
            profiles.add(std)
        elif r.entity_type == LinkedInEntityType.COMPANY:
            companies.add(std)
        elif r.entity_type == LinkedInEntityType.JOB:
            jobs.add(std)
        elif r.entity_type == LinkedInEntityType.POST:
            posts.add(std)
        queue.append((std, 0))

    expansions_run = 0
    max_depth_seen = 0
    stopped_by_time_limit = False

    while queue:
        if max_runtime_seconds is not None:
            if time.perf_counter() - t_start >= max_runtime_seconds:
                stopped_by_time_limit = True
                if verbose:
                    print(
                        f"[bfs] 已达运行时间上限 {max_runtime_seconds}s，停止遍历",
                        flush=True,
                    )
                break

        canonical, depth = queue.popleft()
        if canonical in expanded:
            continue
        expanded.add(canonical)
        max_depth_seen = max(max_depth_seen, depth)

        if max_expand_depth is not None and depth >= max_expand_depth:
            continue

        seed = normalize_linkedin_url(canonical)
        et = seed.entity_type
        if et == LinkedInEntityType.UNKNOWN:
            continue

        if verbose:
            print(
                f"[bfs] 扩展 depth={depth} type={et.value} url={canonical[:100]}",
                flush=True,
            )

        try:
            result = _expand_one(
                canonical,
                fetch_html,
                expand_profile_kwargs=ep,
                expand_company_kwargs=ec,
                expand_post_kwargs=epo,
                expand_job_kwargs=ej,
            )
            expansions_run += 1
        except Exception as e:
            errors.append(f"{canonical}: {e!r}")
            continue

        if et == LinkedInEntityType.PROFILE:
            out = _flatten_buckets(result)
        elif et == LinkedInEntityType.COMPANY:
            out = _raw_urls_from_expand(et, result)
        elif et == LinkedInEntityType.POST:
            out = _raw_urls_from_expand(et, result)
        elif et == LinkedInEntityType.JOB:
            out = _raw_urls_from_expand(et, result)
        else:
            out = []

        next_depth = depth + 1
        for raw_u in out:
            std = standard_canonical_url(raw_u)
            if not std:
                continue
            r2 = normalize_linkedin_url(std)
            if r2.entity_type == LinkedInEntityType.PROFILE:
                profiles.add(std)
            elif r2.entity_type == LinkedInEntityType.COMPANY:
                companies.add(std)
            elif r2.entity_type == LinkedInEntityType.JOB:
                jobs.add(std)
            elif r2.entity_type == LinkedInEntityType.POST:
                posts.add(std)
            if std not in expanded:
                queue.append((std, next_depth))

    elapsed = time.perf_counter() - t_start
    br = BfsExpandResult(
        profiles=sorted(profiles),
        companies=sorted(companies),
        jobs=sorted(jobs),
        posts=sorted(posts),
        expansions_run=expansions_run,
        max_depth_seen=max_depth_seen,
        errors=errors,
        stopped_by_time_limit=stopped_by_time_limit,
    )
    stats = {
        "expansions_run": expansions_run,
        "max_depth_seen": max_depth_seen,
        "max_expand_depth": max_expand_depth,
        "max_runtime_seconds": max_runtime_seconds,
        "elapsed_seconds": round(elapsed, 3),
        "stopped_by_time_limit": stopped_by_time_limit,
        "queue_remaining": len(queue),
        "profiles_count": len(profiles),
        "companies_count": len(companies),
        "jobs_count": len(jobs),
        "posts_count": len(posts),
        "errors": errors,
    }
    return br, stats
