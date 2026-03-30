"""
从个人主页 HTML（及可选的 recent-activity 页）抽取并归类 LinkedIn URL。

说明：归类主要依据 **路径模式**（不依赖易变的 DOM class），便于与 normalize 配合。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable
from urllib.parse import unquote, urlparse

from linkedin_url.discover import discover_from_html_deep
from linkedin_url.normalize import normalize_linkedin_url


def filter_global_nav_urls(urls: list[str]) -> list[str]:
    """
    去掉全局导航 / 页脚 / 帮助等高频链，减轻 ``other`` 桶噪声（不改变公司/个人/post 等路径）。
    """
    out: list[str] = []
    for u in urls:
        if _is_global_nav_or_footer(u):
            continue
        out.append(u)
    return out


def _is_global_nav_or_footer(url: str) -> bool:
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower()
        path = (p.path or "").lower()
        q = (p.query or "").lower()
        if "about.linkedin.com" in host or "business.linkedin.com" in host:
            return True
        if "careers.linkedin.com" in host or "mobile.linkedin.com" in host or "safety.linkedin.com" in host:
            return True
        if path in ("/", "/feed", "/feed/") or (path.startswith("/feed") and "nis=" in q):
            return True
        if path.startswith("/mynetwork") or path.startswith("/notifications"):
            return True
        if path.startswith("/messaging"):
            return True
        if path.startswith("/help/") or path.startswith("/legal/") or path.startswith("/accessibility"):
            return True
        if path.startswith("/mypreferences"):
            return True
        if path.startswith("/ad/") or path.startswith("/jobs/?"):
            return True
        if path == "/jobs" or path == "/jobs/":
            return True
    except Exception:
        return False
    return False


def _path_parts(path: str) -> list[str]:
    return [p for p in path.strip().split("/") if p]


def classify_linkedin_url(url: str) -> str:
    """
    粗分类，便于与业务板块对应：

    - ``jobs_search`` — ``/jobs/search?…``（含公司筛选、多职位 ID）
    - ``company`` — ``/company/{slug}/`` 主页
    - ``company_tab`` — ``/company/{slug}/jobs|people|posts|life/``
    - ``post`` — 单条动态 ``feed/update``、``/posts/…activity-…``（详情页常含评论者主页、侧栏推荐实体）
    - ``profile_activity`` — ``/in/{vanity}/recent-activity/…``（动态列表/评论列表等）
    - ``profile`` — ``/in/{vanity}/`` 仅两段路径，视为个人主页
    - ``profile_subpage`` — ``/in/{vanity}/其它/…``（如 skills、details，非 recent-activity）
    - ``job`` — ``/jobs/view/…``
    - ``other`` — 其余 linkedin.com 路径（含 Sales Navigator 等）
    """
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return "other"
        path = unquote(p.path or "")
        low = path.lower()

        if "/jobs/search" in low:
            return "jobs_search"
        if "/jobs/view/" in low or "/jobs/collections/" in low:
            return "job"
        if "/company/" in low:
            parts = [p for p in path.strip("/").split("/") if p]
            if (
                len(parts) >= 3
                and parts[0].lower() == "company"
                and parts[2].lower() in ("jobs", "people", "posts", "life")
            ):
                return "company_tab"
            return "company"
        if "feed/update" in low and "activity" in low:
            return "post"
        if "/posts/" in low and "activity-" in low:
            return "post"

        parts = _path_parts(path)
        if len(parts) >= 2 and parts[0].lower() == "in":
            if len(parts) == 2:
                return "profile"
            if len(parts) >= 3 and parts[2].lower() == "recent-activity":
                return "profile_activity"
            return "profile_subpage"

        return "other"
    except Exception:
        return "other"


def bucket_urls_by_category(urls: list[str], *, seed_vanity: str | None = None) -> dict[str, list[str]]:
    """
    将 URL 列表按 ``classify_linkedin_url`` 分组；可选 ``seed_vanity`` 用于标注他人主页。

    额外键：

    - ``profiles_others`` — ``profile`` 类型且 vanity ≠ seed
    - ``profiles_self`` — vanity = seed（通常可忽略）
    """
    buckets: dict[str, list[str]] = defaultdict(list)
    profiles_others: list[str] = []
    profiles_self: list[str] = []

    seen: set[str] = set()
    for raw in urls:
        u = raw.split("#", 1)[0].strip()
        if not u or u in seen:
            continue
        seen.add(u)
        cat = classify_linkedin_url(u)
        buckets[cat].append(u)

        if cat == "profile" and seed_vanity:
            r = normalize_linkedin_url(u)
            v = (r.profile_vanity or "").lower()
            if v == seed_vanity.lower():
                profiles_self.append(u)
            else:
                profiles_others.append(u)

    if profiles_others:
        buckets["profiles_others"] = sorted(set(profiles_others))
    if profiles_self:
        buckets["profiles_self"] = sorted(set(profiles_self))

    # 已有拆分后不再保留笼统的 profile 键，避免与上面重复
    if seed_vanity:
        buckets.pop("profile", None)

    return {k: sorted(v) for k, v in buckets.items()}


def expand_profile_page(
    profile_url: str,
    *,
    fetch_html: Callable[[str], str],
    also_fetch_activity: bool = True,
    filter_nav: bool = True,
) -> dict[str, list[str]]:
    """
    抓取个人主页；可选再抓 ``…/recent-activity/comments/``，合并去重后分类。

    ``fetch_html`` 通常为 ``linkedin_url.auth.fetch.fetch_html_sync`` 绑定会话后传入。
    请在绑定参数时使用 ``wait_until='load'``、``settle_ms``、``scroll_passes``，否则 SPA 未注水会只有页脚链接。
    """
    seed = normalize_linkedin_url(profile_url)
    if seed.entity_type.value != "profile" or not seed.profile_vanity:
        raise ValueError(f"不是个人主页 URL：{profile_url}")

    vanity = seed.profile_vanity
    all_urls: list[str] = []

    html_main = fetch_html(seed.canonical_url)
    all_urls.extend(discover_from_html_deep(html_main, base_url=seed.canonical_url))

    if also_fetch_activity:
        act = f"https://www.linkedin.com/in/{vanity}/recent-activity/comments/"
        try:
            html_act = fetch_html(act)
            all_urls.extend(discover_from_html_deep(html_act, base_url=act))
        except Exception:
            # 无权限或风控时仍返回主页结果
            pass

    if filter_nav:
        all_urls = filter_global_nav_urls(all_urls)

    return bucket_urls_by_category(all_urls, seed_vanity=vanity)


def expand_from_saved_html(
    *,
    main_html: str,
    activity_html: str | None = None,
    profile_canonical_url: str,
    seed_vanity: str,
    filter_nav: bool = True,
) -> dict[str, list[str]]:
    """仅解析已保存的 HTML 字符串，不发起网络请求。"""
    all_urls: list[str] = []
    all_urls.extend(discover_from_html_deep(main_html, base_url=profile_canonical_url))
    if activity_html:
        act_url = f"https://www.linkedin.com/in/{seed_vanity}/recent-activity/comments/"
        all_urls.extend(discover_from_html_deep(activity_html, base_url=act_url))
    if filter_nav:
        all_urls = filter_global_nav_urls(all_urls)
    return bucket_urls_by_category(all_urls, seed_vanity=seed_vanity)
