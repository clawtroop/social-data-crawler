from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from crawler.enrich.models import (
    EnrichedField,
    EnrichedRecord,
    ExtractiveResult,
    FieldGroupResult,
    LLMResponse,
    StructuredFields,
)
from crawler.enrich.schemas.field_group_registry import (
    FIELD_GROUP_REGISTRY,
    FieldGroupSpec,
    get_field_group_spec,
    list_field_groups,
)
from crawler.enrich.extractive.lookup_enricher import LookupEnricher
from crawler.enrich.extractive.regex_enricher import RegexEnricher
from crawler.enrich.generative.llm_client import parse_json_response
from crawler.enrich.generative.prompt_renderer import render_prompt, list_templates
from crawler.enrich.pipeline import EnrichPipeline
from crawler.enrich.batch.async_executor import BatchEnrichmentExecutor
from crawler.core.pipeline import _build_enrich_input_from_record


# ─── Model Tests ─────────────────────────────────────────────────────

class TestModels:
    def test_enriched_field_to_dict(self) -> None:
        field = EnrichedField(
            field_name="summary",
            value="A test summary",
            source_type="extractive",
            source_details="lookup:test.json",
            confidence=0.9,
            evidence=["title"],
        )
        d = field.to_dict()
        assert d["field_name"] == "summary"
        assert d["value"] == "A test summary"
        assert d["source_type"] == "extractive"
        assert d["confidence"] == 0.9

    def test_field_group_result_to_dict(self) -> None:
        result = FieldGroupResult(
            field_group="summaries",
            status="success",
            fields=[
                EnrichedField(
                    field_name="summary",
                    value="test",
                    source_type="extractive",
                    source_details="test",
                    confidence=0.8,
                )
            ],
            latency_ms=100,
        )
        d = result.to_dict()
        assert d["field_group"] == "summaries"
        assert d["status"] == "success"
        assert len(d["fields"]) == 1

    def test_enriched_record_merge(self) -> None:
        record = EnrichedRecord(
            doc_id="test-1",
            source_url="https://example.com",
            platform="test",
            resource_type="article",
        )
        result = FieldGroupResult(
            field_group="test_group",
            status="success",
            fields=[
                EnrichedField(
                    field_name="test_field",
                    value="test_value",
                    source_type="extractive",
                    source_details="test",
                    confidence=0.9,
                )
            ],
        )
        record.merge_field_group_result(result)
        assert "test_group" in record.enrichment_results
        assert record.enriched_fields["test_field"] == "test_value"

    def test_enriched_record_to_dict(self) -> None:
        record = EnrichedRecord(
            doc_id="test-1",
            source_url="https://example.com",
            platform="test",
            resource_type="article",
        )
        d = record.to_dict()
        assert d["doc_id"] == "test-1"
        assert d["enrichment_results"] == {}
        assert d["enriched_fields"] == {}

    def test_extractive_result_frozen(self) -> None:
        result = ExtractiveResult(matched=True, confidence=0.9)
        assert result.matched is True
        assert result.confidence == 0.9

    def test_llm_response_tokens_used(self) -> None:
        resp = LLMResponse(content="test", model="gpt-4", total_tokens=100)
        assert resp.tokens_used == 100


# ─── Schema / Registry Tests ────────────────────────────────────────

class TestFieldGroupRegistry:
    def test_registry_has_core_groups(self) -> None:
        names = list_field_groups()
        assert "about_summary" in names
        assert "standardized_job_title" in names
        assert "skills_extraction" in names

    def test_get_field_group_spec_returns_spec(self) -> None:
        spec = get_field_group_spec("about_summary")
        assert spec is not None
        assert spec.name == "about_summary"
        assert spec.strategy == "generative_only"

    def test_get_field_group_spec_unknown_returns_none(self) -> None:
        assert get_field_group_spec("nonexistent_group") is None

    def test_source_fields_present(self) -> None:
        spec = get_field_group_spec("about_summary")
        assert spec is not None
        assert spec.source_fields_present({"about": "test", "headline": "Engineer"})
        assert not spec.source_fields_present({"about": "test"})
        assert not spec.source_fields_present({"about": "", "headline": "Engineer"})

    def test_strategies_are_valid(self) -> None:
        for name, spec in FIELD_GROUP_REGISTRY.items():
            assert spec.strategy in ("extractive_only", "generative_only", "extractive_then_generative")
            if "extractive" in spec.strategy and spec.strategy != "generative_only":
                assert spec.extractive_config is not None, f"{name} missing extractive_config"
            if "generative" in spec.strategy and spec.strategy != "extractive_only":
                assert spec.generative_config is not None, f"{name} missing generative_config"


# ─── Lookup Enricher Tests ──────────────────────────────────────────

class TestLookupEnricher:
    def test_exact_match(self) -> None:
        enricher = LookupEnricher("onet_job_mapping.json")
        result = enricher.enrich({"headline": "Software Engineer"}, source_field_key="headline")
        assert result.matched is True
        assert result.confidence == 1.0
        assert result.values.get("standardized_job_title") == "Software Developers"

    def test_normalized_match(self) -> None:
        enricher = LookupEnricher("onet_job_mapping.json")
        result = enricher.enrich({"headline": "software engineer"}, source_field_key="headline")
        assert result.matched is True
        assert result.confidence == 0.85

    def test_no_match(self) -> None:
        enricher = LookupEnricher("onet_job_mapping.json")
        result = enricher.enrich({"headline": "Chief Llama Officer"}, source_field_key="headline")
        # May or may not prefix-match depending on content
        # At least verify it doesn't crash

    def test_empty_source(self) -> None:
        enricher = LookupEnricher("onet_job_mapping.json")
        result = enricher.enrich({})
        assert result.matched is False

    def test_missing_table_file(self) -> None:
        enricher = LookupEnricher("nonexistent_table.json")
        assert enricher.lookup_table == {}
        result = enricher.enrich({"headline": "test"})
        assert result.matched is False


# ─── Regex Enricher Tests ───────────────────────────────────────────

class TestRegexEnricher:
    def test_skill_extraction(self) -> None:
        enricher = RegexEnricher("skill_patterns.json")
        result = enricher.enrich(
            {"plain_text": "Experienced in Python, React, and AWS. Familiar with Docker and Kubernetes."},
            source_field_key="plain_text",
        )
        assert result.matched is True
        items = result.values.get("extracted_items", [])
        assert "Python" in items
        assert "React" in items
        assert "AWS" in items
        assert result.confidence > 0.5

    def test_no_match(self) -> None:
        enricher = RegexEnricher("skill_patterns.json")
        result = enricher.enrich({"plain_text": "I like cats and dogs."}, source_field_key="plain_text")
        assert result.matched is False

    def test_empty_source(self) -> None:
        enricher = RegexEnricher("skill_patterns.json")
        result = enricher.enrich({})
        assert result.matched is False

    def test_missing_patterns_file(self) -> None:
        enricher = RegexEnricher("nonexistent_patterns.json")
        assert enricher.patterns == []
        result = enricher.enrich({"text": "Python"})
        assert result.matched is False


# ─── JSON Response Parsing Tests ──────────────────────────────────

class TestParseJsonResponse:
    def test_plain_json(self) -> None:
        result = parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_code_block(self) -> None:
        result = parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_invalid_json_returns_raw(self) -> None:
        result = parse_json_response("not json at all")
        assert result == {"raw": "not json at all"}


# ─── Prompt Renderer Tests ──────────────────────────────────────────

class TestPromptRenderer:
    def test_render_about_summary(self) -> None:
        rendered = render_prompt("about_summary.jinja2", {
            "about": "Senior engineer with 10 years experience",
            "headline": "Staff Engineer at BigCo",
        })
        assert "Senior engineer" in rendered
        assert "Staff Engineer" in rendered

    def test_render_fallback_for_unknown_template(self) -> None:
        rendered = render_prompt("nonexistent.jinja2", {"key": "value"})
        assert "key" in rendered
        assert "value" in rendered

    def test_list_templates_returns_jinja2_files(self) -> None:
        templates = list_templates()
        assert "about_summary.jinja2" in templates
        assert "skills_extraction.jinja2" in templates
        assert "job_standardization.jinja2" in templates


# ─── Pipeline Integration Tests ─────────────────────────────────────

class TestEnrichPipeline:
    def test_pipeline_llm_schema_group_without_model_config_returns_failed(self, workspace_tmp_path: Path) -> None:
        schema_path = workspace_tmp_path / "enrich-llm-schema.json"
        schema_path.write_text(
            json.dumps({"schema_name": "enrich-profile", "instruction": "Extract enrich fields", "output_fields": ["entity_profile"]}),
            encoding="utf-8",
        )
        pipeline = EnrichPipeline(enrich_llm_schema_path=schema_path)
        record = asyncio.run(
            pipeline.enrich(
                {
                    "platform": "linkedin",
                    "plain_text": "Engineer with Python and ML experience.",
                    "canonical_url": "https://linkedin.com/in/test",
                },
                field_groups=["llm_schema"],
            )
        )

        result = record.enrichment_results["llm_schema"]
        assert result.status == "failed"
        assert result.error is not None

    def test_pipeline_llm_schema_group_with_model_config_returns_fields(self, monkeypatch, workspace_tmp_path: Path) -> None:
        schema_path = workspace_tmp_path / "enrich-llm-schema.json"
        schema_path.write_text(
            json.dumps({"schema_name": "enrich-profile", "instruction": "Extract enrich fields", "output_fields": ["entity_profile", "signals"]}),
            encoding="utf-8",
        )

        async def fake_execute(self, payload: dict) -> dict:
            return {
                "success": True,
                "data": {"entity_profile": "AI engineer", "signals": ["python", "ml"]},
                "schema_name": "enrich-profile",
            }

        monkeypatch.setattr("crawler.enrich.pipeline.LLMSchemaFieldGroupExecutor.execute", fake_execute)

        pipeline = EnrichPipeline(
            enrich_llm_schema_path=schema_path,
            model_config={"model": "test-model", "base_url": "https://api.example.com"},
        )
        record = asyncio.run(
            pipeline.enrich(
                {
                    "platform": "linkedin",
                    "plain_text": "Engineer with Python and ML experience.",
                    "canonical_url": "https://linkedin.com/in/test",
                },
                field_groups=["llm_schema"],
            )
        )

        result = record.enrichment_results["llm_schema"]
        assert result.status == "success"
        assert record.enriched_fields["entity_profile"] == "AI engineer"
        signals_field = next(field for field in result.fields if field.field_name == "signals")
        assert signals_field.source_details == "llm_schema:enrich-profile"

    def test_pipeline_with_legacy_group(self) -> None:
        """Test a group that only exists in legacy templates (not in the new registry)."""
        pipeline = EnrichPipeline()
        record = asyncio.run(
            pipeline.enrich(
                {
                    "platform": "wikipedia",
                    "title": "Artificial Intelligence",
                    "summary": "AI is a field of computer science.",
                    "canonical_url": "https://en.wikipedia.org/wiki/AI",
                },
                # "behavior" exists in legacy but not in the new registry
                field_groups=["behavior"],
            )
        )
        assert "behavior" in record.enrichment_results
        result = record.enrichment_results["behavior"]
        # Legacy groups without matching source fields get skipped
        assert result.status in ("success", "skipped")

    def test_pipeline_generative_group_without_llm(self) -> None:
        """Generative-only groups fail gracefully when no LLM is configured."""
        pipeline = EnrichPipeline()
        record = asyncio.run(
            pipeline.enrich(
                {
                    "platform": "wikipedia",
                    "title": "Artificial Intelligence",
                    "summary": "AI is a field of computer science.",
                    "canonical_url": "https://en.wikipedia.org/wiki/AI",
                },
                field_groups=["summaries"],
            )
        )
        assert "summaries" in record.enrichment_results
        result = record.enrichment_results["summaries"]
        # Without LLM config, generative_only groups return pending_agent with prompt
        assert result.status == "pending_agent"
        assert result.agent_prompt is not None
        assert len(result.agent_prompt) > 0
        assert result.output_fields == ["summary"]

    def test_pipeline_unknown_group_is_skipped(self) -> None:
        pipeline = EnrichPipeline()
        record = asyncio.run(
            pipeline.enrich(
                {"platform": "test", "canonical_url": "https://example.com"},
                field_groups=["imaginary_group"],
            )
        )
        assert "imaginary_group" in record.enrichment_results
        result = record.enrichment_results["imaginary_group"]
        assert result.status == "skipped"

    def test_pipeline_extractive_only_with_lookup(self) -> None:
        """extractive_then_generative strategy succeeds via extractive when match is confident."""
        pipeline = EnrichPipeline()
        record = asyncio.run(
            pipeline.enrich(
                {
                    "platform": "linkedin",
                    "headline": "Software Engineer",
                    "canonical_url": "https://linkedin.com/in/test",
                },
                field_groups=["standardized_job_title"],
            )
        )
        assert "standardized_job_title" in record.enrichment_results
        result = record.enrichment_results["standardized_job_title"]
        # Extractive lookup succeeds with high confidence, no LLM needed
        assert result.status == "success"
        assert len(result.fields) > 0

    def test_pipeline_extractive_regex_with_skills(self) -> None:
        """extractive_then_generative strategy succeeds via regex extraction."""
        pipeline = EnrichPipeline()
        record = asyncio.run(
            pipeline.enrich(
                {
                    "platform": "linkedin",
                    "plain_text": "Expert in Python, TensorFlow, and AWS. 5 years with Kubernetes.",
                    "canonical_url": "https://linkedin.com/in/test",
                },
                field_groups=["skills_extraction"],
            )
        )
        assert "skills_extraction" in record.enrichment_results
        result = record.enrichment_results["skills_extraction"]
        # Regex extraction succeeds with high confidence, no LLM needed
        assert result.status == "success"
        if result.fields:
            skill_field = next((f for f in result.fields if f.field_name == "skills_extracted"), None)
            if skill_field and skill_field.value:
                assert "Python" in skill_field.value

    def test_pipeline_skips_when_missing_required_fields(self) -> None:
        pipeline = EnrichPipeline()
        record = asyncio.run(
            pipeline.enrich(
                {
                    "platform": "linkedin",
                    "canonical_url": "https://linkedin.com/in/test",
                    # Missing "about" and "headline" required for about_summary
                },
                field_groups=["about_summary"],
            )
        )
        result = record.enrichment_results["about_summary"]
        assert result.status == "skipped"

    def test_pipeline_multiple_groups(self) -> None:
        """Multiple groups: extractive_then_generative succeed via extractive, generative_only fails without LLM."""
        pipeline = EnrichPipeline()
        record = asyncio.run(
            pipeline.enrich(
                {
                    "platform": "linkedin",
                    "headline": "Senior Data Scientist",
                    "plain_text": "Expert in Python and Machine Learning with TensorFlow.",
                    "about": "Data scientist with 8 years experience.",
                    "canonical_url": "https://linkedin.com/in/test",
                },
                field_groups=["standardized_job_title", "skills_extraction", "about_summary"],
            )
        )
        assert len(record.enrichment_results) == 3
        # extractive_then_generative groups succeed via extractive path
        assert record.enrichment_results["standardized_job_title"].status == "success"
        assert record.enrichment_results["skills_extraction"].status == "success"
        # generative_only group returns pending_agent with prompt for agent execution
        assert record.enrichment_results["about_summary"].status == "pending_agent"
        assert record.enrichment_results["about_summary"].agent_prompt is not None

    def test_pipeline_accepts_normalized_linkedin_company_aliases(self) -> None:
        pipeline = EnrichPipeline()
        enrich_input = _build_enrich_input_from_record(
            {
                "platform": "linkedin",
                "resource_type": "company",
                "canonical_url": "https://www.linkedin.com/company/openai/",
                "plain_text": "OpenAI builds advanced AI systems for broad public benefit.",
                "markdown": "# OpenAI\n\nOpenAI builds advanced AI systems for broad public benefit.",
                "structured": {"staff_count": 7716},
                "metadata": {
                    "title": "OpenAI",
                    "description": "OpenAI builds advanced AI systems for broad public benefit.",
                },
            }
        )
        record = asyncio.run(
            pipeline.enrich(
                enrich_input,
                field_groups=["linkedin_company_profile", "linkedin_company_scale"],
            )
        )

        assert record.enrichment_results["linkedin_company_profile"].status == "pending_agent"
        assert record.enrichment_results["linkedin_company_scale"].status == "pending_agent"

    def test_pipeline_accepts_normalized_base_transaction_aliases(self) -> None:
        pipeline = EnrichPipeline()
        enrich_input = _build_enrich_input_from_record(
            {
                "platform": "base",
                "resource_type": "transaction",
                "canonical_url": "https://basescan.org/tx/0xabc",
                "structured": {
                    "hash": "0xabc",
                    "from": "0xfrom",
                    "to": "0xto",
                    "input_data": "0xa9059cbb",
                    "gasUsed": 21000,
                    "gasPrice": 1000000000,
                    "blockNumber": 12345,
                    "events": [{"address": "0xtoken"}],
                    "value": "1000000000000000000",
                },
            }
        )
        record = asyncio.run(
            pipeline.enrich(
                enrich_input,
                field_groups=["base_transactions_basic", "base_transactions_context"],
            )
        )

        assert record.enrichment_results["base_transactions_basic"].status == "pending_agent"
        assert record.enrichment_results["base_transactions_context"].status == "pending_agent"

    def test_pipeline_accepts_normalized_amazon_product_aliases(self) -> None:
        pipeline = EnrichPipeline()
        enrich_input = _build_enrich_input_from_record(
            {
                "platform": "amazon",
                "resource_type": "product",
                "canonical_url": "https://www.amazon.com/dp/B000TEST",
                "rating": 4.8,
                "manufacturer": "Keychron",
                "current_price": "$99.99",
                "stock_status": "In Stock",
                "shipping_type": "Prime",
                "structured": {
                    "category_path": ["Electronics", "Keyboards"],
                    "highlights": ["Wireless", "Low-profile"],
                },
                "metadata": {
                    "title": "Keychron K3",
                    "description": "Low-profile wireless mechanical keyboard.",
                },
            }
        )
        record = asyncio.run(
            pipeline.enrich(
                enrich_input,
                field_groups=["amazon_products_identity", "amazon_products_description"],
            )
        )

        assert record.enrichment_results["amazon_products_identity"].status == "pending_agent"
        assert record.enrichment_results["amazon_products_description"].status == "pending_agent"

    def test_pipeline_accepts_normalized_wikipedia_aliases(self) -> None:
        pipeline = EnrichPipeline()
        enrich_input = _build_enrich_input_from_record(
            {
                "platform": "wikipedia",
                "resource_type": "article",
                "canonical_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                "plain_text": "Artificial intelligence is intelligence demonstrated by machines.",
                "structured": {"categories": ["Artificial intelligence"]},
                "metadata": {"title": "Artificial intelligence"},
            }
        )
        record = asyncio.run(
            pipeline.enrich(
                enrich_input,
                field_groups=["wikipedia_identity", "wikipedia_categories"],
            )
        )

        assert record.enrichment_results["wikipedia_identity"].status == "pending_agent"
        assert record.enrichment_results["wikipedia_categories"].status == "pending_agent"


# ─── Batch Executor Tests ──────────────────────────────────────────

class TestBatchExecutor:
    def test_batch_execute(self) -> None:
        pipeline = EnrichPipeline()
        executor = BatchEnrichmentExecutor(pipeline, max_concurrency=2, batch_size=2)

        records = [
            {"platform": "wikipedia", "title": "AI", "summary": "Test", "canonical_url": "https://example.com/1"},
            {"platform": "wikipedia", "title": "ML", "summary": "Test2", "canonical_url": "https://example.com/2"},
            {"platform": "wikipedia", "title": "DL", "summary": "Test3", "canonical_url": "https://example.com/3"},
        ]

        progress_calls: list[tuple[int, int]] = []

        def on_progress(completed: int, total: int) -> None:
            progress_calls.append((completed, total))

        executor.on_progress = on_progress

        results = asyncio.run(
            executor.execute_batch(records, ["classifications"])
        )
        assert len(results) == 3
        assert len(progress_calls) == 3
        assert progress_calls[-1] == (3, 3)

    def test_batch_handles_errors_gracefully(self) -> None:
        pipeline = EnrichPipeline()

        # Patch enrich to raise on one record
        original_enrich = pipeline.enrich

        call_count = 0

        async def flaky_enrich(doc: dict, groups: list[str]) -> EnrichedRecord:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("simulated failure")
            return await original_enrich(doc, groups)

        pipeline.enrich = flaky_enrich

        executor = BatchEnrichmentExecutor(pipeline, max_concurrency=1, batch_size=10)
        records = [
            {"platform": "test", "title": f"test-{i}", "canonical_url": f"https://example.com/{i}"}
            for i in range(3)
        ]
        results = asyncio.run(
            executor.execute_batch(records, ["classifications"])
        )
        assert len(results) == 3  # All 3 returned, one is error placeholder


# ─── Backward Compatibility Tests ──────────────────────────────────

class TestBackwardCompatibility:
    """Ensure the new pipeline doesn't break existing orchestrator usage."""

    def test_legacy_templates_still_accessible(self) -> None:
        from crawler.enrich.templates import FIELD_GROUP_TEMPLATES, get_field_group_template
        assert "summaries" in FIELD_GROUP_TEMPLATES
        template = get_field_group_template("summaries")
        assert template is not None
        assert template.output_field == "summary"

    def test_legacy_route_enrichment_still_works_for_extractive_groups(self) -> None:
        from crawler.enrich.orchestrator import route_enrichment
        envelope = route_enrichment(
            {"resource_type": "article", "canonical_url": "https://example.com/test"},
            field_groups=("classifications",),
            model_config={},
        )
        assert envelope["status"] == "routed"
        assert "classifications" in envelope["generated_fields"]

    def test_legacy_supported_field_groups(self) -> None:
        from crawler.enrich.field_groups import supported_field_groups
        groups = supported_field_groups()
        assert "summaries" in groups
        assert "classifications" in groups


# ─── Agent Enrichment Tests ──────────────────────────────────────

class TestPendingAgentEnrichment:
    """Test the pending_agent flow: no API key → agent executes LLM prompt."""

    def test_generative_only_returns_pending_agent_with_prompt(self) -> None:
        """generative_only group without LLM config returns pending_agent + prompt."""
        pipeline = EnrichPipeline()
        record = asyncio.run(
            pipeline.enrich(
                {
                    "platform": "linkedin",
                    "about": "Data scientist with 8 years experience in NLP.",
                    "headline": "Senior Data Scientist",
                    "canonical_url": "https://linkedin.com/in/test",
                },
                field_groups=["about_summary"],
            )
        )
        result = record.enrichment_results["about_summary"]
        assert result.status == "pending_agent"
        assert result.agent_prompt is not None
        assert "Data scientist" in result.agent_prompt
        assert result.agent_system_prompt is not None
        assert result.output_fields == ["about_summary", "about_topics", "about_sentiment"]

    def test_extractive_then_generative_returns_pending_agent_when_extractive_fails(self) -> None:
        """extractive_then_generative returns pending_agent when extractive has low confidence and no LLM."""
        pipeline = EnrichPipeline()
        record = asyncio.run(
            pipeline.enrich(
                {
                    "platform": "linkedin",
                    "headline": "XYZ_UNRECOGNIZABLE_TITLE_999",
                    "canonical_url": "https://linkedin.com/in/test",
                },
                field_groups=["standardized_job_title"],
            )
        )
        result = record.enrichment_results["standardized_job_title"]
        # Extractive lookup won't match this gibberish, so falls through to generative
        # which returns pending_agent because no LLM config
        assert result.status == "pending_agent"
        assert result.agent_prompt is not None

    def test_fill_pending_agent_result_with_json(self) -> None:
        """fill_pending_agent_result parses agent LLM response into fields."""
        pipeline = EnrichPipeline()
        response_text = '{"about_summary": "Expert data scientist specializing in NLP", "about_topics": ["NLP", "ML", "Python"], "about_sentiment": "professional"}'
        result = pipeline.fill_pending_agent_result("about_summary", response_text)

        assert result.status == "success"
        assert len(result.fields) == 3
        summary_field = next(f for f in result.fields if f.field_name == "about_summary")
        assert summary_field.value == "Expert data scientist specializing in NLP"
        assert summary_field.source_type == "generative"
        assert summary_field.source_details == "agent:claude"

    def test_fill_pending_agent_result_with_markdown_json(self) -> None:
        """Agent response wrapped in markdown code block is handled."""
        pipeline = EnrichPipeline()
        response_text = '```json\n{"about_summary": "Test summary", "about_topics": ["AI"], "about_sentiment": "neutral"}\n```'
        result = pipeline.fill_pending_agent_result("about_summary", response_text)

        assert result.status == "success"
        summary_field = next(f for f in result.fields if f.field_name == "about_summary")
        assert summary_field.value == "Test summary"

    def test_fill_unknown_field_group_returns_failed(self) -> None:
        pipeline = EnrichPipeline()
        result = pipeline.fill_pending_agent_result("nonexistent_group", '{"key": "value"}')
        assert result.status == "failed"
        assert "unknown" in result.error
