"""Agent Enrichment Executor - 自动执行 LLM 补全字段

提供 Agent Integration Layer，让 OpenClaw agent 可以一步完成 enrichment，
无需手动协调 pending_agent 回填流程。

使用方式：

    from crawler.enrich.agent_executor import AgentEnrichmentExecutor

    # 方式 1: 传入 LLM 调用函数
    executor = AgentEnrichmentExecutor(llm_call=my_llm_function)
    result = await executor.enrich(document, field_groups)

    # 方式 2: 传入 Agent 实例（需要有 generate 方法）
    executor = AgentEnrichmentExecutor(agent=my_agent)
    result = await executor.enrich(document, field_groups)

    # 方式 3: 使用 subagent 并行执行
    executor = AgentEnrichmentExecutor(
        agent=my_agent,
        use_subagents=True,
        spawn_subagent=my_agent.spawn_subagent
    )
    result = await executor.enrich(document, field_groups)
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Protocol

from crawler.enrich.pipeline import EnrichPipeline
from crawler.enrich.models import EnrichedRecord, FieldGroupResult


class LLMCallable(Protocol):
    """LLM 调用协议"""
    async def __call__(
        self,
        prompt: str,
        system: str | None = None
    ) -> str:
        """执行 LLM 调用，返回响应文本"""
        ...


class AgentProtocol(Protocol):
    """Agent 协议（可选）"""
    async def generate(
        self,
        prompt: str,
        system: str | None = None
    ) -> str:
        """生成响应"""
        ...

    def supports_vision(self) -> bool:
        """是否支持视觉能力"""
        ...


class AgentEnrichmentExecutor:
    """Agent Enrichment 执行器

    封装 EnrichPipeline，自动处理 pending_agent 字段组的 LLM 调用和回填。
    """

    def __init__(
        self,
        *,
        llm_call: LLMCallable | None = None,
        agent: AgentProtocol | None = None,
        use_subagents: bool = False,
        spawn_subagent: Callable[[str, str, str | None], Awaitable[str]] | None = None,
        model_capabilities: dict[str, bool] | None = None,
    ):
        """
        初始化执行器。

        Args:
            llm_call: LLM 调用函数，签名为 async (prompt, system) -> str
            agent: Agent 实例，需要有 generate() 方法
            use_subagents: 是否使用 subagent 并行执行
            spawn_subagent: spawn subagent 的函数，签名为 async (name, prompt, system) -> str
            model_capabilities: 模型能力，如 {"vision": True}

        必须提供 llm_call 或 agent 之一。
        如果 use_subagents=True，必须提供 spawn_subagent。
        """
        if llm_call is None and agent is None:
            raise ValueError("必须提供 llm_call 或 agent 之一")

        if use_subagents and spawn_subagent is None:
            raise ValueError("use_subagents=True 时必须提供 spawn_subagent")

        self._llm_call = llm_call
        self._agent = agent
        self._use_subagents = use_subagents
        self._spawn_subagent = spawn_subagent
        self._model_capabilities = model_capabilities or {}
        self._pipeline = EnrichPipeline()

    @property
    def model_capabilities(self) -> dict[str, bool]:
        """获取模型能力"""
        if self._model_capabilities:
            return self._model_capabilities
        if self._agent and hasattr(self._agent, "supports_vision"):
            return {"vision": self._agent.supports_vision()}
        return {}

    async def _call_llm(self, prompt: str, system: str | None = None) -> str:
        """执行单次 LLM 调用"""
        if self._llm_call:
            return await self._llm_call(prompt, system)
        if self._agent:
            return await self._agent.generate(prompt, system)
        raise RuntimeError("无可用的 LLM 调用方式")

    async def enrich(
        self,
        document: dict[str, Any],
        field_groups: list[str],
        parallel: bool = True,
    ) -> EnrichedRecord:
        """
        执行 enrichment 并自动补全所有字段。

        Args:
            document: 要补全的文档
            field_groups: 要生成的字段组列表
            parallel: 是否并行执行多个字段组（仅在 use_subagents=True 时有效）

        Returns:
            EnrichedRecord: 包含所有补全字段的结果
        """
        # Step 1: 调用 pipeline
        result = await self._pipeline.enrich(
            document,
            field_groups,
            model_capabilities=self.model_capabilities,
        )

        # Step 2: 收集需要 LLM 的字段组
        pending_groups = [
            fg for fg in result.field_groups
            if fg.status == "pending_agent"
        ]

        if not pending_groups:
            return result

        # Step 3: 执行 LLM 调用
        if self._use_subagents and parallel and len(pending_groups) > 1:
            # 并行执行（使用 subagent）
            responses = await self._execute_parallel(pending_groups)
        else:
            # 串行执行
            responses = await self._execute_serial(pending_groups)

        # Step 4: 回填结果
        for fg, response in zip(pending_groups, responses):
            filled = self._pipeline.fill_pending_agent_result(
                fg.field_group,
                response
            )
            # 更新 result 中的字段组结果
            self._update_field_group_result(result, fg.field_group, filled)

        return result

    async def _execute_serial(
        self,
        pending_groups: list[FieldGroupResult]
    ) -> list[str]:
        """串行执行 LLM 调用"""
        responses = []
        for fg in pending_groups:
            response = await self._call_llm(
                fg.agent_prompt or "",
                fg.agent_system_prompt
            )
            responses.append(response)
        return responses

    async def _execute_parallel(
        self,
        pending_groups: list[FieldGroupResult]
    ) -> list[str]:
        """并行执行 LLM 调用（使用 subagent）"""
        if not self._spawn_subagent:
            # fallback 到串行
            return await self._execute_serial(pending_groups)

        tasks = [
            self._spawn_subagent(
                f"enrich_{fg.field_group}",
                fg.agent_prompt or "",
                fg.agent_system_prompt
            )
            for fg in pending_groups
        ]
        return await asyncio.gather(*tasks)

    def _update_field_group_result(
        self,
        record: EnrichedRecord,
        field_group: str,
        filled: FieldGroupResult
    ) -> None:
        """更新 EnrichedRecord 中的字段组结果"""
        for i, fg in enumerate(record.field_groups):
            if fg.field_group == field_group:
                record.field_groups[i] = filled
                break

        # 合并字段到 structured
        if filled.fields:
            for field in filled.fields:
                if field.value is not None:
                    record.structured.fields[field.field_name] = field.value

    async def auto_enrich(
        self,
        document: dict[str, Any],
    ) -> EnrichedRecord:
        """
        自动选择字段组并执行 enrichment。

        根据 document 的 platform 和 resource_type 自动选择适用的字段组。

        Args:
            document: 要补全的文档，必须包含 platform 字段

        Returns:
            EnrichedRecord: 包含所有补全字段的结果
        """
        from crawler.enrich.schemas.field_group_registry import FIELD_GROUP_REGISTRY

        platform = document.get("platform", "").lower()
        resource_type = document.get("resource_type", "").lower()

        # 自动选择适用的字段组
        field_groups = []
        for name, spec in FIELD_GROUP_REGISTRY.items():
            # 匹配平台
            if spec.platform and spec.platform.lower() != platform:
                continue
            # 匹配子数据集（如果指定）
            if spec.subdataset and spec.subdataset.lower() != resource_type:
                continue
            # 检查视觉能力
            if spec.requires_vision and not self.model_capabilities.get("vision"):
                continue
            field_groups.append(name)

        return await self.enrich(document, field_groups, parallel=True)


# 便捷函数
async def enrich_with_llm(
    document: dict[str, Any],
    field_groups: list[str],
    llm_call: LLMCallable,
    model_capabilities: dict[str, bool] | None = None,
) -> EnrichedRecord:
    """
    便捷函数：使用 LLM 函数执行 enrichment。

    Args:
        document: 要补全的文档
        field_groups: 要生成的字段组列表
        llm_call: LLM 调用函数
        model_capabilities: 模型能力

    Returns:
        EnrichedRecord: 包含所有补全字段的结果

    示例:
        async def my_llm(prompt, system=None):
            # 调用 Claude/GPT/本地模型
            return await call_claude(prompt, system)

        result = await enrich_with_llm(
            document={"platform": "linkedin", "about": "..."},
            field_groups=["linkedin_profiles_about"],
            llm_call=my_llm
        )
    """
    executor = AgentEnrichmentExecutor(
        llm_call=llm_call,
        model_capabilities=model_capabilities
    )
    return await executor.enrich(document, field_groups)
