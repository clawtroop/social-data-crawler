# arXiv PDF Extraction and Catalog Coverage Design

## Goal

Upgrade `social-data-crawler` so arXiv papers use `PyMuPDF4LLM` as a required PDF extraction backend, produce cleaned full-text outputs from paper PDFs, and expose the arXiv dataset fields defined in [`Dataset_Product_Catalog_v2.md`](/D:/kaifa/clawtroop/Dataset_Product_Catalog_v2.md) through a mix of deterministic extraction and LLM-backed completion.

## Scope

This design covers:

- dependency changes needed to require `PyMuPDF4LLM`
- arXiv fetch and extract pipeline changes
- PDF cleaning and normalization behavior
- arXiv structured field expansion
- enrichment schema changes for catalog-wide field coverage
- test and artifact expectations

This design does not cover:

- image-based figure understanding beyond placeholder/schema wiring
- external paid APIs
- embedding generation
- non-arXiv platform changes except shared PDF extraction utilities that arXiv depends on

## Current State

The current arXiv path is metadata-only:

- the adapter fetches Atom XML from the arXiv API
- extraction reads title, summary, authors, categories, and `pdf_url`
- `plain_text` is the abstract summary, not full paper text
- the generic PDF extractor is `pypdf`-based and not wired into the new pipeline
- `normalize_record(..., supplemental={})` means arXiv never receives PDF-derived supplemental data

As a result, the current crawler cannot satisfy the arXiv catalog requirements for full text, sections, references, code/data links, or LLM-derived research analysis fields.

## Requirements

### Functional

1. `PyMuPDF4LLM` must be installed as part of the initial runtime dependency set.
2. arXiv extraction must use PDF full text as the primary content source.
3. Atom metadata must still be preserved and merged into structured outputs.
4. The crawler must persist cleaned PDF-derived artifacts for debugging and downstream reuse.
5. arXiv dataset fields from the catalog must all be represented in the pipeline:
   - deterministic fields populated directly when extractable
   - remaining fields surfaced via schema/LLM enrichment, including `pending_agent` if generation is required
6. Existing arXiv field groups must continue to work, with expanded inputs.
7. The implementation must remain local-only, without paid API dependencies.

### Non-Functional

- keep arXiv behavior deterministic where possible
- fail fast on missing required PDF dependency
- preserve backward-compatible record layout (`plain_text`, `markdown`, `structured`, `chunks`, `artifacts`)
- make debugging easy through artifacts and focused tests

## Architecture

### 1. Dependency Strategy

`PyMuPDF4LLM` becomes a required dependency in the core install path. The runtime should not silently degrade to the old metadata-only flow because the requested behavior depends on PDF parsing being available.

Implementation consequences:

- add `pymupdf4llm` and the corresponding `PyMuPDF` dependency into the core requirements set
- add a small import guard/helper module under `crawler.extract` so import failures produce a clear startup/runtime error
- remove the conceptual role of `pypdf` as the preferred PDF path for arXiv

### 2. arXiv Content Source Model

arXiv extraction will become a dual-source merge:

- `Atom XML` remains the authoritative source for canonical metadata
- `PDF` becomes the authoritative source for full text and document structure

The final arXiv document should use:

- `title`, `authors`, `categories`, `published`, `updated`, `pdf_url`, `entry_id` from Atom/XML
- `plain_text`, `markdown`, `sections`, `chunks`, references/linkable URL evidence from cleaned PDF output

The final `plain_text` and `markdown` should be PDF-first, not abstract-first. The abstract should still be preserved in structured metadata and should be included in the rendered markdown preamble for usability, but it should not replace the full paper body.

### 3. PDF Extraction and Cleaning Pipeline

Add a dedicated PDF extraction utility for scientific papers, built around `PyMuPDF4LLM`.

Responsibilities:

- fetch the arXiv PDF from `pdf_url`
- store the raw PDF in artifacts
- run `PyMuPDF4LLM` to produce markdown/text
- normalize noisy output into crawler-friendly content
- identify sections and generate chunkable content

Cleaning rules should be deterministic and conservative:

- normalize line endings and excess blank lines
- strip obviously repeated page furniture where possible
- preserve headings, lists, and code-like blocks when available from markdown
- preserve equations as text/markdown output when emitted by the parser
- keep citation markers and reference section text intact
- avoid aggressive rewriting that would damage technical content

The output of this stage should include:

- cleaned markdown
- cleaned plain text
- per-page or section metadata when available
- extraction diagnostics such as page count and parser name

### 4. Structured arXiv Field Coverage

The catalog fields split into three tiers.

#### Tier A: deterministic from Atom/XML or direct text rules

- `arxiv_id`, `DOI`, `URL`, `title`, `abstract`
- `title_normalized`
- `abstract_plain_text`
- `authors_structured[]` base fields:
  - `full_name`
  - `first_name`
  - `last_name`
  - `affiliation_standardized` when detectable
  - `affiliation_type` when inferable from affiliation text
  - `affiliation_country` when inferable from affiliation text
- `categories`, `primary_category`
- `keywords_extracted[]`
- `research_area_plain_english` baseline mapping from primary category
- `submission_date`, `update_date`, `versions[]` when available
- `raw_text`, `PDF_url`
- `sections_structured[]` base fields:
  - `heading`
  - `section_type`
  - `content_summary` via extractive shortening if possible
- `references_structured[]` base fields:
  - `title`
  - `authors`
  - `year`
  - `venue`
- `total_citation_count`
- `code_available`, `code_url`
- `dataset_released`, `dataset_url`
- `open_access_status`
- `linkable_identifiers.github_repos_mentioned[]`
- `linkable_identifiers.project_urls_mentioned[]`
- `linkable_identifiers.dataset_source_urls[]`
- `linkable_identifiers.related_arxiv_ids_mentioned[]`

#### Tier B: deterministic schema presence, LLM-backed completion

- `topic_hierarchy[]`
- `interdisciplinary_score`
- `acceptance_status_inferred`
- `venue_published`
- `venue_tier`
- `main_contributions[]`
- `novelty_type`
- `problem_statement`
- `proposed_solution_summary`
- `methods_used[]`
- `baselines_compared[]`
- `evaluation_metrics[]`
- `datasets_used[]`
- `experimental_setup_summary`
- `key_results[]`
- `state_of_art_claimed`
- `statistical_significance_reported`
- `reproducibility_indicators`
- `limitations_stated[]`
- `future_work_directions[]`
- `threats_to_validity[]`
- `references_structured[].citation_context`
- `references_structured[].citation_sentiment`
- `influential_citation_count`
- `code_framework`
- `relations.*`
- multi-level summary fields
- research depth analysis fields
- `linkable_identifiers.author_linkedin_hints[]`
- `linkable_identifiers.wikipedia_concept_hints[]`

#### Tier C: schema-only placeholders for later multimodal or advanced extraction

- `figures_analyzed[]`
- `key_equations[]`
- embeddings

For Tier C, the implementation must wire these fields into the output schema and enrichment contracts, but the initial implementation may legitimately produce empty arrays or `pending_agent` pathways rather than full automatic population.

### 5. Enrichment Model Changes

The current arXiv enrichment groups are too small for the catalog target. Extend the academic schema registry so the arXiv record can request field groups that cover:

- metadata normalization
- author enrichment
- methodology and results
- references and relations
- code/data/linkable identifiers
- multi-level summaries
- research depth analysis
- multimodal placeholders

The rule is:

- if a field can be deterministically extracted, populate it before enrichment
- if a field needs model reasoning, pass the relevant cleaned PDF text/markdown into enrichment and populate via extractive or generative path
- if generation must happen outside the pipeline, emit `pending_agent` for that field group instead of dropping the field

### 6. Artifact Model

arXiv runs should persist enough evidence to audit extraction quality.

Required artifacts:

- raw Atom/XML response
- raw PDF
- cleaned markdown from PDF
- cleaned plain text from PDF
- sections JSON
- chunks JSON
- structured JSON

Optional diagnostics:

- parser metadata JSON
- extracted references JSON if built separately

### 7. Error Handling

Error handling should distinguish these cases:

- `ARXIV_PDF_FETCH_FAILED`
- `ARXIV_PDF_EXTRACT_FAILED`
- `ARXIV_XML_PARSE_FAILED`
- `ARXIV_FIELD_COVERAGE_PARTIAL`

Behavior:

- XML metadata failure should fail the record unless an equivalent fallback source exists
- PDF fetch or parse failure should fail the full arXiv extraction, because PDF full text is now required for the target dataset behavior
- field-level deterministic misses should not fail the record; they should leave structured gaps for enrichment

## File-Level Design

Expected areas of change:

- `requirements-core.txt`
  - add `pymupdf4llm` and required PDF runtime deps
- `crawler/extract/`
  - add a dedicated `pymupdf4llm` helper module
  - add scientific PDF cleaning helpers
- `crawler/extract/pipeline.py`
  - extend arXiv XML branch to invoke PDF fetch + extraction + merge
- `crawler/core/pipeline.py`
  - stop passing empty supplemental data for arXiv-only PDF-derived normalization needs
  - persist raw PDF and derived extraction artifacts
- `crawler/platforms/arxiv.py`
  - expand enrichment field groups to cover the arXiv catalog field families
- `crawler/platforms/base.py`
  - extend arXiv normalization mapping
- `crawler/enrich/schemas/academic_field_groups.py`
  - add field groups for uncovered arXiv catalog fields
- tests
  - add unit tests for PDF cleaning, structured extraction, normalization, and enrichment requests

## Data Flow

Final arXiv path:

1. discover canonical arXiv URL
2. fetch Atom XML from arXiv API
3. parse metadata and `pdf_url`
4. fetch PDF
5. run `PyMuPDF4LLM` extraction
6. clean markdown/plain text
7. derive sections and chunks
8. derive deterministic arXiv structured fields
9. merge XML metadata + PDF-derived structure
10. run expanded arXiv enrichment groups
11. write normalized record and artifacts

## Testing Strategy

Follow TDD per component. Minimum required coverage:

- dependency import/guard behavior
- PDF extraction adapter with mocked `PyMuPDF4LLM`
- markdown/text cleaning helpers
- arXiv XML + PDF merge behavior
- field coverage population for deterministic fields
- enrichment request expansion for arXiv
- artifact persistence for raw PDF and cleaned outputs
- failure modes for missing `pdf_url`, fetch failure, parse failure

Tests should avoid real network and real PDF parsing where possible by mocking fetch results and parser outputs.

## Tradeoffs and Chosen Approach

### Considered

1. Keep metadata-only arXiv and add PDF as supplemental
2. Use PDF as the primary content source with XML metadata merge
3. Use external parsing APIs

### Chosen

Option 2.

Reasoning:

- the catalog explicitly requires full-text-derived fields
- `PyMuPDF4LLM` is light enough to be a required dependency
- XML metadata remains high-quality and cheap, so merging both sources is better than replacing XML
- this keeps the pipeline local, deterministic where possible, and compatible with the current enrichment architecture

## Open Constraints Acknowledged

- `authors_structured[]` advanced fields such as `h_index_estimated` and external author IDs are not realistically deterministic from arXiv input alone; they will be schema-covered and LLM/pending-agent backed
- figure and equation understanding will initially be schema-complete but extraction-light
- embeddings are out of scope for this iteration and should remain empty or omitted unless an existing embedding subsystem is introduced later

## Acceptance Criteria

The design is satisfied when:

- installing core dependencies installs `PyMuPDF4LLM`
- arXiv records no longer use abstract-only `plain_text`
- arXiv records contain PDF-derived `plain_text`, `markdown`, `chunks`, and section structure
- deterministic arXiv catalog fields are populated where extractable
- remaining catalog fields are represented through enrichment schema or `pending_agent`, not silently absent from the model
- tests cover the new extraction, merge, and error paths
