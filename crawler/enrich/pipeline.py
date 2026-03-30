from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Any

from crawler.enrich.extractive.lookup_enricher import LookupEnricher
from crawler.enrich.extractive.regex_enricher import RegexEnricher
from crawler.enrich.generative.llm_client import parse_json_response
from crawler.enrich.generative.prompt_renderer import render_prompt
from crawler.enrich.models import (
    EnrichedField,
    EnrichedRecord,
    ExtractiveResult,
    FieldGroupResult,
    StructuredFields,
)
from crawler.enrich.schemas.field_group_registry import (
    FIELD_GROUP_REGISTRY,
    FieldGroupSpec,
    get_field_group_spec,
)
from crawler.schema_runtime import LLMExecutor

# Legacy re-export for backward compatibility
from crawler.enrich.templates import FIELD_GROUP_TEMPLATES


class LLMSchemaFieldGroupExecutor:
    def __init__(self, schema_path: Path, model_config: dict[str, Any]):
        self.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.executor = LLMExecutor(model_config)

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await self.executor.execute(
            schema_name=str(self.schema.get("schema_name", "enrich_schema")),
            instruction=str(self.schema.get("instruction", "Extract enrichment fields")),
            payload=payload,
            system_prompt=str(self.schema.get("system_prompt", "Extract only the requested JSON object. Return valid JSON only.")),
        )
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "schema_name": result.schema_name,
            "output_fields": list(self.schema.get("output_fields", [])),
        }


class EnrichPipeline:
    """Enrichment pipeline: extractive-first, generative delegated to agent.

    No external LLM API key is needed. Generative field groups return
    ``pending_agent`` with a ready-to-execute prompt that the orchestrating
    agent (e.g. OpenClaw) fulfills using its own LLM capability.
    """

    def __init__(
        self,
        *,
        enrich_llm_schema_path: Path | None = None,
        model_config: dict[str, Any] | None = None,
    ) -> None:
        self._lookup_cache: dict[str, LookupEnricher] = {}
        self._regex_cache: dict[str, RegexEnricher] = {}
        self._llm_schema_executor = (
            LLMSchemaFieldGroupExecutor(enrich_llm_schema_path, model_config or {})
            if enrich_llm_schema_path is not None
            else None
        )

    def _get_lookup_enricher(self, table_path: str) -> LookupEnricher:
        if table_path not in self._lookup_cache:
            self._lookup_cache[table_path] = LookupEnricher(table_path)
        return self._lookup_cache[table_path]

    def _get_regex_enricher(self, patterns_file: str) -> RegexEnricher:
        if patterns_file not in self._regex_cache:
            self._regex_cache[patterns_file] = RegexEnricher(patterns_file)
        return self._regex_cache[patterns_file]

    async def enrich(
        self,
        document: dict[str, Any],
        field_groups: list[str],
        model_capabilities: dict[str, bool] | None = None,
    ) -> EnrichedRecord:
        """Enrich a document across requested field groups.

        For each field group:
        1. Check if model capabilities match (e.g., vision for multimodal)
        2. Check if required source fields are present
        3. Run extractive enrichment (lookup/regex) — zero cost, instant
        4. If generative is needed, return ``pending_agent`` with prompt

        Args:
            document: The document to enrich.
            field_groups: List of field group names to apply.
            model_capabilities: Optional dict indicating model capabilities.
                - "vision": bool - whether the model supports image analysis.
                If a field group requires vision but model doesn't support it,
                the group will be skipped with an informative message.
        """
        model_capabilities = model_capabilities or {}
        record = EnrichedRecord(
            doc_id=document.get("doc_id", document.get("canonical_url", "")),
            source_url=document.get("canonical_url", ""),
            platform=document.get("platform", "unknown"),
            resource_type=document.get("resource_type", document.get("entity_type", "unknown")),
            structured=StructuredFields(fields=document.get("structured", {})),
        )

        for group_name in field_groups:
            if group_name == "llm_schema" and self._llm_schema_executor is not None:
                result = await self._run_llm_schema_group(document)
                record.merge_field_group_result(result)
                continue
            spec = get_field_group_spec(group_name)
            if spec is None:
                result = self._run_legacy_group(group_name, document)
                record.merge_field_group_result(result)
                continue

            result = await self._run_field_group(spec, document, model_capabilities)
            record.merge_field_group_result(result)

        return record

    async def _run_llm_schema_group(self, document: dict[str, Any]) -> FieldGroupResult:
        start = time.monotonic()
        if self._llm_schema_executor is None:
            return FieldGroupResult(
                field_group="llm_schema",
                status="failed",
                error="llm schema executor not configured",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        result = await self._llm_schema_executor.execute(document)
        if not result.get("success"):
            return FieldGroupResult(
                field_group="llm_schema",
                status="failed",
                error=result.get("error", "llm schema execution failed"),
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        schema_name = str(result.get("schema_name", "enrich_schema"))
        output_fields = result.get("output_fields") or list(result.get("data", {}).keys())
        data = result.get("data", {})
        fields = [
            EnrichedField(
                field_name=field_name,
                value=data.get(field_name),
                source_type="generative",
                source_details=f"llm_schema:{schema_name}",
                confidence=0.8 if data.get(field_name) is not None else 0.0,
                evidence=["llm_schema"],
            )
            for field_name in output_fields
        ]
        return FieldGroupResult(
            field_group="llm_schema",
            status="success",
            fields=fields,
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    async def _run_field_group(
        self,
        spec: FieldGroupSpec,
        document: dict[str, Any],
        model_capabilities: dict[str, bool] | None = None,
    ) -> FieldGroupResult:
        """Execute a single field group according to its strategy."""
        start = time.monotonic()
        model_capabilities = model_capabilities or {}

        # Check vision capability for multimodal field groups
        if spec.requires_vision and not model_capabilities.get("vision", False):
            return FieldGroupResult(
                field_group=spec.name,
                status="skipped",
                error="需要视觉能力但当前模型不支持 (requires_vision=True but model lacks vision capability)",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        source_fields = self._collect_source_fields(spec, document)

        # Check required source fields
        if spec.required_source_fields and not spec.source_fields_present(document):
            return FieldGroupResult(
                field_group=spec.name,
                status="skipped",
                error=f"missing required source fields: {spec.required_source_fields}",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        strategy = spec.strategy

        # ── Step 1: Run extractive if applicable ──
        if strategy in ("extractive_only", "extractive_then_generative"):
            extractive_result = self._run_extractive(spec, source_fields)

            if extractive_result.matched and extractive_result.confidence >= spec.min_extractive_confidence:
                fields = self._extractive_to_fields(spec, extractive_result)
                return FieldGroupResult(
                    field_group=spec.name,
                    status="success",
                    fields=fields,
                    latency_ms=int((time.monotonic() - start) * 1000),
                )

            if strategy == "extractive_only":
                if extractive_result.matched:
                    fields = self._extractive_to_fields(spec, extractive_result)
                    return FieldGroupResult(
                        field_group=spec.name,
                        status="partial",
                        fields=fields,
                        latency_ms=int((time.monotonic() - start) * 1000),
                    )
                return FieldGroupResult(
                    field_group=spec.name,
                    status="failed",
                    error="no extractive match found",
                    latency_ms=int((time.monotonic() - start) * 1000),
                )

        # ── Step 2: Generative needed → return pending_agent for agent execution ──
        if strategy in ("generative_only", "extractive_then_generative"):
            if spec.generative_config is None:
                return FieldGroupResult(
                    field_group=spec.name,
                    status="failed",
                    error="generative strategy but no generative_config",
                    latency_ms=int((time.monotonic() - start) * 1000),
                )

            gen_config = spec.generative_config
            prompt = render_prompt(gen_config.prompt_template, source_fields)
            return FieldGroupResult(
                field_group=spec.name,
                status="pending_agent",
                agent_prompt=prompt,
                agent_system_prompt=gen_config.system_prompt,
                output_fields=[f.name for f in spec.output_fields],
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        return FieldGroupResult(
            field_group=spec.name,
            status="failed",
            error=f"unknown strategy: {strategy}",
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    def _collect_source_fields(self, spec: FieldGroupSpec, document: dict[str, Any]) -> dict[str, Any]:
        """Collect all relevant source fields from the document."""
        source: dict[str, Any] = {}
        for field_name in spec.required_source_fields:
            value = document.get(field_name)
            if value is not None and value != "" and value != [] and value != {}:
                source[field_name] = value
        for key in ("plain_text", "markdown", "title", "summary", "headline", "about", "description"):
            if key not in source and key in document:
                value = document[key]
                if value is not None and value != "" and value != [] and value != {}:
                    source[key] = value
        return source

    def _run_extractive(self, spec: FieldGroupSpec, source_fields: dict[str, Any]) -> ExtractiveResult:
        """Run the extractive enrichment step."""
        if spec.extractive_config is None:
            return ExtractiveResult(matched=False)

        config = spec.extractive_config
        if config.extractor_type == "lookup" and config.lookup_table:
            enricher = self._get_lookup_enricher(config.lookup_table)
            return enricher.enrich(source_fields, config.source_field_key)
        elif config.extractor_type == "regex" and config.patterns_file:
            enricher = self._get_regex_enricher(config.patterns_file)
            return enricher.enrich(source_fields, config.source_field_key)

        return ExtractiveResult(matched=False)

    @staticmethod
    def _extractive_to_fields(spec: FieldGroupSpec, result: ExtractiveResult) -> list[EnrichedField]:
        """Convert an ExtractiveResult into EnrichedField list."""
        fields = []
        for output_spec in spec.output_fields:
            value = result.values.get(output_spec.name)
            if value is None:
                if "extracted_items" in result.values and output_spec.field_type.startswith("array"):
                    value = result.values["extracted_items"]
                elif "categories" in result.values and "categor" in output_spec.name:
                    value = result.values["categories"]
                elif "value" in result.values:
                    value = result.values["value"]
                elif result.values:
                    value = next(iter(result.values.values()))
            fields.append(
                EnrichedField(
                    field_name=output_spec.name,
                    value=value,
                    source_type="lookup" if "lookup" in result.source_details else "extractive",
                    source_details=result.source_details,
                    confidence=result.confidence,
                    evidence=result.evidence,
                )
            )
        return fields

    def _run_legacy_group(self, group_name: str, document: dict[str, Any]) -> FieldGroupResult:
        """Fallback: run enrichment using the legacy FieldGroupTemplate system."""
        from crawler.enrich.templates import get_field_group_template

        template = get_field_group_template(group_name)
        if template is None:
            return FieldGroupResult(
                field_group=group_name,
                status="skipped",
                error=f"unknown field group: {group_name}",
            )

        routed = template.route(document)
        if routed["unsupported_reason"] is not None:
            return FieldGroupResult(
                field_group=group_name,
                status="skipped",
                error=routed["unsupported_reason"],
            )

        fields = []
        for field_name, value in routed["generated_fields"].items():
            fields.append(
                EnrichedField(
                    field_name=field_name,
                    value=value,
                    source_type="passthrough",
                    source_details="legacy_template",
                    confidence=routed["confidence"],
                    evidence=routed["evidence"],
                )
            )

        return FieldGroupResult(
            field_group=group_name,
            status="success" if fields else "failed",
            fields=fields,
        )

    def fill_pending_agent_result(
        self,
        field_group: str,
        llm_response_text: str,
    ) -> FieldGroupResult:
        """Fill a pending_agent result with the LLM response from agent execution.

        Called by the agent after it executes the prompt itself.
        """
        spec = get_field_group_spec(field_group)
        if spec is None:
            return FieldGroupResult(
                field_group=field_group,
                status="failed",
                error=f"unknown field group: {field_group}",
            )

        parsed = parse_json_response(llm_response_text)
        fields = []
        parsed_dict = parsed if isinstance(parsed, dict) else {"raw": parsed}

        for output_spec in spec.output_fields:
            value = parsed_dict.get(output_spec.name)
            if value is None and "raw" in parsed_dict:
                value = parsed_dict["raw"]
            fields.append(
                EnrichedField(
                    field_name=output_spec.name,
                    value=value,
                    source_type="generative",
                    source_details="agent:claude",
                    confidence=0.8 if value is not None else 0.0,
                    evidence=["agent_executed"],
                )
            )

        return FieldGroupResult(
            field_group=field_group,
            status="success" if any(f.value is not None for f in fields) else "failed",
            fields=fields,
        )
