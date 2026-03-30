from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlparse

from linkedin_url.models import LinkedInEntityType, NormalizeResult

_LINKEDIN_HOSTS = frozenset(
    {
        "linkedin.com",
        "www.linkedin.com",
        "cn.linkedin.com",
        "www.cn.linkedin.com",
    }
)

# /in/{vanity}/ — vanity 允许 URL 编码与常见字符
_RE_PROFILE = re.compile(
    r"^/in/([^/]+)/?(?:.*)?$",
    re.IGNORECASE,
)

# /company/{slug}/
_RE_COMPANY = re.compile(
    r"^/company/([^/]+)/?(?:.*)?$",
    re.IGNORECASE,
)

# /jobs/view/{numeric_id}/
_RE_JOB = re.compile(
    r"^/jobs/view/(\d+)/?(?:.*)?$",
    re.IGNORECASE,
)

# /feed/update/urn:li:activity:{id}/  — id 为数字
_RE_FEED_ACTIVITY = re.compile(
    r"^/feed/update/urn:li:activity:(\d+)/?$",
    re.IGNORECASE,
)

# 旧式或变体：路径中含 urn%3Ali%3Aactivity%3A
_RE_FEED_ACTIVITY_ENCODED = re.compile(
    r"feed/update/.*?activity[:%3A]+(\d+)",
    re.IGNORECASE,
)

# /posts/{slug}-activity-{id}-...  或路径任意位置 activity-{id}
_RE_POSTS_ACTIVITY = re.compile(
    r"activity-(\d+)(?:$|[-_/])",
    re.IGNORECASE,
)

# 文本中粗提 LinkedIn URL
_RE_ANY_LINKEDIN_URL = re.compile(
    r"https?://(?:[\w-]+\.)*linkedin\.com[^\s)\"'<>]*",
    re.IGNORECASE,
)


def _host_ok(netloc: str) -> bool:
    host = netloc.lower().split(":")[0]
    return host in _LINKEDIN_HOSTS or host.endswith(".linkedin.com")


def _strip_default_port(netloc: str) -> str:
    if ":443" in netloc:
        return netloc.split(":")[0]
    return netloc


def _canonical_netloc() -> str:
    return "www.linkedin.com"


def _normalize_path_vanity(segment: str) -> str:
    """/in/ 与 /company/ 段：统一解码后再编码路径安全片段（保留 Unicode 如中文）。"""
    s = unquote(segment.strip())
    # LinkedIn vanity 通常不含裸空格
    return s


def _build_profile_url(vanity: str) -> str:
    v = quote(_normalize_path_vanity(vanity), safe="-_.~")
    return f"https://{_canonical_netloc()}/in/{v}/"


def _build_company_url(slug: str) -> str:
    s = quote(_normalize_path_vanity(slug), safe="-_.~")
    return f"https://{_canonical_netloc()}/company/{s}/"


def _build_job_url(job_id: str) -> str:
    return f"https://{_canonical_netloc()}/jobs/view/{job_id}/"


def _build_post_url(activity_id: str) -> str:
    return (
        f"https://{_canonical_netloc()}/feed/update/"
        f"urn:li:activity:{activity_id}/"
    )


def normalize_linkedin_url(url: str) -> NormalizeResult:
    """
    将任意形式的 LinkedIn 主站 URL 归一为四类之一；无法识别则 UNKNOWN。

    - 去掉 tracking query（保留可能语义极少，MVP 一律去掉非必要参数）
    - Profile / Company / Job：规范为 https://www.linkedin.com/.../
    - Post：/posts/...activity-{id}... → 统一为 feed/update/urn:li:activity:{id}/
    """
    raw = (url or "").strip()
    if not raw:
        return NormalizeResult(
            entity_type=LinkedInEntityType.UNKNOWN,
            canonical_url="",
            original_url=raw,
            notes=("empty_input",),
        )

    parsed = urlparse(raw)
    if not parsed.scheme:
        parsed = urlparse("https://" + raw)

    if parsed.scheme not in ("http", "https"):
        return NormalizeResult(
            entity_type=LinkedInEntityType.UNKNOWN,
            canonical_url="",
            original_url=raw,
            notes=("unsupported_scheme",),
        )

    netloc = _strip_default_port(parsed.netloc.lower())
    if not _host_ok(netloc):
        return NormalizeResult(
            entity_type=LinkedInEntityType.UNKNOWN,
            canonical_url="",
            original_url=raw,
            notes=("not_linkedin_host",),
        )

    path = unquote(parsed.path) or "/"
    path = "/" + path.lstrip("/")
    if len(path) > 1 and path.endswith("/"):
        path = path  # keep trailing for consistency
    elif path != "/":
        path = path + "/"

    notes: list[str] = []
    if parsed.query:
        notes.append("stripped_query")

    # --- Profile ---
    m = _RE_PROFILE.match(path)
    if m:
        vanity = _normalize_path_vanity(m.group(1))
        if vanity:
            can = _build_profile_url(vanity)
            return NormalizeResult(
                entity_type=LinkedInEntityType.PROFILE,
                canonical_url=can,
                profile_vanity=vanity,
                original_url=raw,
                notes=tuple(notes),
            )

    # --- Company ---
    m = _RE_COMPANY.match(path)
    if m:
        slug = _normalize_path_vanity(m.group(1))
        if slug:
            can = _build_company_url(slug)
            return NormalizeResult(
                entity_type=LinkedInEntityType.COMPANY,
                canonical_url=can,
                company_vanity=slug,
                original_url=raw,
                notes=tuple(notes),
            )

    # --- Job ---
    m = _RE_JOB.match(path)
    if m:
        jid = m.group(1)
        can = _build_job_url(jid)
        return NormalizeResult(
            entity_type=LinkedInEntityType.JOB,
            canonical_url=can,
            job_id=jid,
            original_url=raw,
            notes=tuple(notes),
        )

    # --- Post: feed/update/urn:li:activity ---
    m = _RE_FEED_ACTIVITY.match(path)
    if m:
        aid = m.group(1)
        can = _build_post_url(aid)
        return NormalizeResult(
            entity_type=LinkedInEntityType.POST,
            canonical_url=can,
            activity_id=aid,
            original_url=raw,
            notes=tuple(notes),
        )

    # 路径可能被编码成单段
    if "feed" in path.lower() and "activity" in path.lower():
        m2 = _RE_FEED_ACTIVITY_ENCODED.search(path)
        if m2:
            aid = m2.group(1)
            can = _build_post_url(aid)
            return NormalizeResult(
                entity_type=LinkedInEntityType.POST,
                canonical_url=can,
                activity_id=aid,
                original_url=raw,
                notes=tuple(notes + ["decoded_embedded_activity_path"]),
            )

    # --- Post: /posts/...activity-{id}... ---
    if "/posts/" in path:
        m3 = _RE_POSTS_ACTIVITY.search(path)
        if m3:
            aid = m3.group(1)
            can = _build_post_url(aid)
            return NormalizeResult(
                entity_type=LinkedInEntityType.POST,
                canonical_url=can,
                activity_id=aid,
                original_url=raw,
                notes=tuple(notes + ["normalized_from_posts_path"]),
            )

    return NormalizeResult(
        entity_type=LinkedInEntityType.UNKNOWN,
        canonical_url="",
        original_url=raw,
        notes=tuple(notes + ["unrecognized_path"]),
    )


def standard_canonical_url(url: str) -> str | None:
    """
    若 ``url`` 可归一为 Profile / Company / Job / Post 四类之一，返回无查询串、无子路径标签的规范 URL；
    否则返回 ``None``（与 ``doc/进展.md`` 中四类标准形式一致）。
    """
    r = normalize_linkedin_url(url)
    if r.entity_type == LinkedInEntityType.UNKNOWN or not r.canonical_url:
        return None
    return r.canonical_url


def extract_linkedin_urls(text: str) -> list[NormalizeResult]:
    """从一段文本中找出所有疑似 linkedin.com URL 并逐个 normalize。"""
    if not text:
        return []
    seen: set[str] = set()
    out: list[NormalizeResult] = []
    for m in _RE_ANY_LINKEDIN_URL.finditer(text):
        u = m.group(0).rstrip(".,;]")
        if u in seen:
            continue
        seen.add(u)
        out.append(normalize_linkedin_url(u))
    return out
