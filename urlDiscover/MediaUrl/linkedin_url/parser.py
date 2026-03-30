"""
基础解析：在 normalize 之上提供便于持久化与 JSON 的视图。

页面级 discover / 字段级 extract 不在此模块实现（见 discover.py / extract.py）。
"""

from __future__ import annotations

from typing import Any

from linkedin_url.models import LinkedInEntityType, NormalizeResult
from linkedin_url.normalize import normalize_linkedin_url


def parse_linkedin_url(url: str) -> NormalizeResult:
    """与 normalize_linkedin_url 相同，命名强调「解析输入 URL」。"""
    return normalize_linkedin_url(url)


def normalize_result_to_observation_row(
    result: NormalizeResult,
    *,
    source_label: str | None = None,
) -> dict[str, Any]:
    """
    映射为 schema/phase1_linkedin.sql 中 linkedin_url_observation 一行的字典（不含 id/observed_at）。
    """
    return {
        "raw_url": result.original_url,
        "normalized_url": result.canonical_url or None,
        "entity_type": result.entity_type.value,
        "profile_vanity": result.profile_vanity,
        "company_vanity": result.company_vanity,
        "job_id": result.job_id,
        "activity_id": result.activity_id,
        "source_label": source_label,
    }


def normalize_result_to_entity_upsert(
    result: NormalizeResult,
) -> tuple[str, dict[str, Any]] | None:
    """
    返回 (table_name, column_dict) 供 Phase 1 四类主表 upsert；
    UNKNOWN 返回 None。
    """
    if result.entity_type == LinkedInEntityType.UNKNOWN:
        return None
    if result.entity_type == LinkedInEntityType.PROFILE and result.profile_vanity:
        return (
            "linkedin_profile",
            {
                "profile_vanity": result.profile_vanity,
                "canonical_url": result.canonical_url,
            },
        )
    if result.entity_type == LinkedInEntityType.COMPANY and result.company_vanity:
        return (
            "linkedin_company",
            {
                "company_vanity": result.company_vanity,
                "canonical_url": result.canonical_url,
            },
        )
    if result.entity_type == LinkedInEntityType.JOB and result.job_id:
        return (
            "linkedin_job",
            {"job_id": result.job_id, "canonical_url": result.canonical_url},
        )
    if result.entity_type == LinkedInEntityType.POST and result.activity_id:
        return (
            "linkedin_post",
            {"activity_id": result.activity_id, "canonical_url": result.canonical_url},
        )
    return None
