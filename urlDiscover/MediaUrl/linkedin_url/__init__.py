"""
LinkedIn URL 规范化与类型解析（Phase 1 MVP）。

discover / extract 解耦：本包仅处理「从任意字符串中识别 LinkedIn URL 并归一化」，
不包含页面抓取或结构化字段抽取。
"""

from linkedin_url.models import LinkedInEntityType, NormalizeResult
from linkedin_url.normalize import extract_linkedin_urls, normalize_linkedin_url
from linkedin_url.parser import (
    normalize_result_to_entity_upsert,
    normalize_result_to_observation_row,
    parse_linkedin_url,
)

__all__ = [
    "LinkedInEntityType",
    "NormalizeResult",
    "normalize_linkedin_url",
    "extract_linkedin_urls",
    "parse_linkedin_url",
    "normalize_result_to_observation_row",
    "normalize_result_to_entity_upsert",
]
