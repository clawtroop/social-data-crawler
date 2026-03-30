from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LinkedInEntityType(str, Enum):
    PROFILE = "profile"
    COMPANY = "company"
    JOB = "job"
    POST = "post"
    """动态（feed update / posts 短链形式均归一为 feed/update + urn）"""

    UNKNOWN = "unknown"
    """无法识别为以上四类（含短链 lnkd.in、非标准路径等）"""


@dataclass(frozen=True)
class NormalizeResult:
    """单条 URL 规范化结果。"""

    entity_type: LinkedInEntityType
    canonical_url: str
    """规范 URL；UNKNOWN 时与输入去碎片后的 best-effort 或空字符串策略见实现。"""

    # 主键分量（按类型仅其一非空；UNKNOWN 时全 None）
    profile_vanity: str | None = None
    company_vanity: str | None = None
    job_id: str | None = None
    activity_id: str | None = None

    original_url: str = ""
    """原始输入（规范化前）"""

    notes: tuple[str, ...] = field(default_factory=tuple)
    """如：丢弃了 query、合并了 posts→feed 形式等说明"""

    def primary_key(self) -> dict[str, Any]:
        """便于写入 DB 或日志的统一主键字典。"""
        if self.entity_type == LinkedInEntityType.PROFILE:
            return {"kind": "profile", "profile_vanity": self.profile_vanity}
        if self.entity_type == LinkedInEntityType.COMPANY:
            return {"kind": "company", "company_vanity": self.company_vanity}
        if self.entity_type == LinkedInEntityType.JOB:
            return {"kind": "job", "job_id": self.job_id}
        if self.entity_type == LinkedInEntityType.POST:
            return {"kind": "post", "activity_id": self.activity_id}
        return {"kind": "unknown"}
