# LLM Schema Extractor Design

## Goal

Add an explicit opt-in LLM schema extraction capability to both the extract stage and the enrich stage without changing the default crawler path.

## Scope

- Extract stage accepts a dedicated schema file and uses LLM output only to extend `structured`.
- Enrich stage accepts a separate schema file and exposes LLM schema extraction as a dedicated enrichment field group.
- Both stages reuse one shared LLM execution core.

## Non-Goals

- No sitemap work.
- No automatic fallback from schema extraction to another extractor.
- No mutation of `plain_text`, `markdown`, or `chunks` from extract-stage schema output.
- No shared business schema file between extract and enrich.

## Architecture

### Shared Runtime

Create one reusable runtime under `crawler/schema_runtime/`:

- `model_config.py` loads OpenAI-compatible config JSON
- `llm_executor.py` handles prompt assembly, API calls, JSON parsing, and normalized failures

### Extract Stage

Create `crawler/extract/structured/llm_schema_extractor.py`.

Input:
- `plain_text`
- `markdown`
- `cleaned_html`
- page metadata
- extract schema JSON

Output:
- title override when explicitly returned
- description override when explicitly returned
- additional `platform_fields`
- `field_sources` entries tagged as `llm_schema:<schema_name>`

Failure behavior:
- if no schema is configured, do nothing
- if LLM execution fails, keep the record and add a structured extraction error marker

### Enrich Stage

Create a dedicated LLM schema field group path that reads an enrich schema file and runs through the existing `EnrichPipeline`.

Input:
- normalized record fields
- enrich schema JSON

Output:
- one `FieldGroupResult`
- fields tagged `source_type="generative"`
- `source_details` tagged with the enrich schema name

Failure behavior:
- if no schema is configured, do nothing
- if configured but model execution fails, return a failed field-group result
- no hidden fallback to another group

## Config Surface

Add these explicit options:

- `--extract-llm-schema <path>`
- `--enrich-llm-schema <path>`
- `--model-config <path>`

These options are independent from `--css-schema`.

## Testing

- contract tests for new config fields
- extract-pipeline tests for LLM schema merge behavior
- enrich-pipeline tests for explicit schema field group behavior
- CLI tests for parsing new options

## Acceptance

- default crawler behavior stays unchanged when no LLM schema options are present
- extract-stage schema only changes `structured`
- enrich-stage schema only changes `enrichment`
- both stages reuse the same LLM runtime
