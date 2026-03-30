# Social Data Crawler - Comprehensive Architecture Analysis

**Date**: 2026-03-29
**Status**: Complete
**Scope**: Read-only architectural deep-dive

---

## Executive Summary

`social-data-crawler` is a **production-grade, agent-first web crawler and enrichment framework** designed for deterministic, structured data extraction from 5 major platforms: Wikipedia, arXiv, Amazon, Base (blockchain), and LinkedIn.

### Key Characteristics
- **Architecture**: 3-layer pipeline (Fetch → Extract → Enrich)
- **Code Volume**: ~8,500 LOC core + ~2,000 LOC tests
- **Philosophy**: Local execution, API-first, session-persistent, agent-oriented
- **Design Pattern**: Declarative platform adapters, configuration-driven routing
- **Output**: Deterministic JSONL with LLM-ready semantic chunks

---

## Project Structure

### Directory Hierarchy

```
social-data-crawler/
├── crawler/                              # Main Python package
│   ├── __pycache__/
│   ├── cli.py                           # Entry point: argparse CLI
│   ├── contracts.py                     # Core data classes (CrawlCommand, CrawlerConfig, NormalizedError)
│   │
│   ├── core/                            # Pipeline orchestration
│   │   ├── pipeline.py                  # Unified pipeline routing (new 3-layer vs legacy dispatcher)
│   │   └── dispatcher.py                # LEGACY dispatcher (deprecated, fallback only)
│   │
│   ├── discovery/                       # URL canonicalization
│   │   └── url_builder.py              # Transform discovery fields → canonical URL
│   │
│   ├── fetch/                           # Data acquisition layer (1,272 LOC)
│   │   ├── engine.py (271 LOC)         # FetchEngine: main orchestrator
│   │   ├── browser_pool.py (162 LOC)   # Browser context pooling, reuse
│   │   ├── session_manager.py (96 LOC) # Auth state lifecycle, Playwright storage_state
│   │   ├── backend_router.py (69 LOC)  # Config-driven backend selection
│   │   ├── wait_strategy.py (115 LOC)  # Intelligent wait behaviors
│   │   ├── http_backend.py (32 LOC)    # httpx HTTP client
│   │   ├── api_backend.py (65 LOC)     # API calls (non-HTML)
│   │   ├── playwright_backend.py (39 LOC) # Playwright browser
│   │   ├── camoufox_backend.py (37 LOC)  # Anti-detection browser
│   │   ├── browser_common.py (47 LOC)   # Shared browser utilities
│   │   ├── session_store.py (88 LOC)    # Persistent session storage
│   │   ├── unified.py (142 LOC)         # Unified fetch entry point
│   │   ├── models.py (79 LOC)           # FetchTiming, RawFetchResult
│   │   └── __init__.py
│   │
│   ├── extract/                         # Content extraction layer (1,450 LOC)
│   │   ├── pipeline.py (234 LOC)       # ExtractPipeline orchestrator
│   │   ├── content_cleaner.py (107 LOC) # HTML noise removal
│   │   ├── main_content.py (230 LOC)    # Semantic main content detection
│   │   ├── html_extract.py (36 LOC)    # HTML parsing helpers
│   │   ├── trafilatura_extract.py (34 LOC) # Article extraction wrapper
│   │   ├── unstructured_extract.py (51 LOC) # PDF/doc parsing
│   │   ├── models.py (141 LOC)          # ContentChunk, ExtractedDocument
│   │   ├── chunking/
│   │   │   ├── hybrid_chunker.py (278 LOC) # Heading-first + paragraph chunking
│   │   │   └── __init__.py
│   │   ├── structured/
│   │   │   ├── json_extractor.py (332 LOC) # JSON-to-structured transformation
│   │   │   └── __init__.py
│   │   └── __init__.py
│   │
│   ├── enrich/                          # Data enrichment layer (1,508 LOC)
│   │   ├── pipeline.py (408 LOC)       # EnrichPipeline: orchestrator
│   │   ├── models.py (149 LOC)          # EnrichedField, EnrichedRecord
│   │   ├── orchestrator.py (138 LOC)    # Legacy enrichment routing
│   │   ├── field_groups.py (7 LOC)     # Field group utilities
│   │   ├── extractive/                 # Fast extraction enrichment
│   │   │   ├── regex_enricher.py (101 LOC) # Pattern-based extraction
│   │   │   ├── lookup_enricher.py (112 LOC) # Lookup table enrichment
│   │   │   └── __init__.py
│   │   ├── generative/                 # LLM-powered enrichment
│   │   │   ├── llm_client.py (125 LOC) # OpenAI-compatible API client
│   │   │   ├── prompt_renderer.py (69 LOC) # Prompt template rendering
│   │   │   └── __init__.py
│   │   ├── batch/                      # Async batch execution
│   │   │   ├── async_executor.py (73 LOC) # Parallel enrichment
│   │   │   └── __init__.py
│   │   ├── schemas/
│   │   │   ├── field_group_registry.py (177 LOC) # Field group definitions
│   │   │   └── __init__.py
│   │   ├── templates/
│   │   │   ├── __init__.py (131 LOC)   # Legacy templates
│   │   │   └── prompt_templates/      # Template files
│   │   └── __init__.py
│   │
│   ├── platforms/                       # Platform adapters (1,094 LOC total)
│   │   ├── base.py (226 LOC)           # PlatformAdapter base class + defaults
│   │   ├── wikipedia.py (78 LOC)       # Wikipedia adapter
│   │   ├── arxiv.py (75 LOC)           # arXiv adapter
│   │   ├── amazon.py (47 LOC)          # Amazon adapter
│   │   ├── base_chain.py (103 LOC)     # Base Chain adapter
│   │   ├── linkedin.py (539 LOC)       # LinkedIn adapter
│   │   ├── registry.py (25 LOC)        # Platform registry lookup
│   │   └── __init__.py
│   │
│   ├── normalize/                       # Output normalization
│   │   ├── canonical.py                # Build canonical record format
│   │   └── __init__.py
│   │
│   ├── output/                          # Result writing
│   │   ├── jsonl_writer.py             # JSONL output
│   │   ├── summary_writer.py           # Summary JSON + manifest
│   │   ├── artifact_writer.py          # Debug artifact persistence
│   │   └── __init__.py
│   │
│   ├── io/                              # File I/O
│   │   └── __init__.py (read_json_file, read_jsonl_file, etc.)
│   │
│   ├── mcp/                             # MCP server integration
│   │   └── ...
│   │
│   ├── tests/                           # Unit tests
│   │   ├── test_*.py
│   │   └── __pycache__/
│   │
│   └── __init__.py
│
├── auto-browser/                        # VRD browser integration
│   ├── scripts/
│   │   └── vrd.py                      # Browser session management
│   ├── tests/
│   │   └── test_vrd.py
│   ├── SKILL.md                        # auto-browser documentation
│   └── __pycache__/
│
├── references/                          # Configuration files
│   ├── backend_routing.json            # Backend selection rules
│   ├── url_templates.json              # URL canonicalization patterns
│   ├── field_mappings.json             # Input field normalization
│   ├── wait_strategies.json            # Per-platform wait configs
│   ├── noise_selectors.json            # HTML noise removal selectors
│   ├── main_content_selectors.json     # Content detection CSS selectors
│   ├── skill_patterns.json             # Regex extraction patterns
│   ├── rate_limits.json                # Rate limiting config
│   ├── enrichment_catalog/             # Enrichment rule definitions
│   └── lookup_tables/                  # Static lookup data
│
├── docs/                                # Documentation
│   └── superpowers/                    # Advanced usage guides
│
├── data/                                # Test fixtures
├── output/                              # Sample output
├── README.md                            # Quick start
├── SKILL.md                             # Comprehensive skill documentation
├── CLAUDE.md                            # (inherited from parent)
├── pyproject.toml                       # Package metadata
├── requirements.txt                     # Dependencies
├── .env.example                         # Environment template
└── .gitignore
```

---

## Architecture Overview: 3-Layer Pipeline

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INPUT                              │
│                    (JSONL records)                              │
│  {"platform":"wikipedia","resource_type":"article",            │
│   "title":"Artificial Intelligence"}                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────────────┐
    │  DISCOVERY: url_builder.py                            │
    │  Transform: {"title":"AI"} →                          │
    │  "https://en.wikipedia.org/wiki/Artificial..."        │
    └────────────┬─────────────────────────────────────────┘
                 │
                 ▼
    ╔══════════════════════════════════════════════════════╗
    ║  LAYER 1: FETCH ENGINE                              ║
    ║  ─────────────────────────────────────────────────   ║
    ║  1. resolve_backend() → backend_routing.json         ║
    ║  2. FetchEngine._fetch_with_backend()                ║
    ║  3. retry + escalation loop                          ║
    ║  4. BrowserPool context reuse                        ║
    ║  5. wait_strategy application                        ║
    ║  6. SessionManager state persistence                 ║
    ║                                                      ║
    ║  Output: RawFetchResult                              ║
    ║    {url, final_url, backend, status_code,            ║
    ║     html/json_data, headers, cookies_updated, ...}   ║
    ╚════════════┬═════════════════════════════════════════╝
                 │
                 ▼
    ╔══════════════════════════════════════════════════════╗
    ║  LAYER 2: EXTRACT PIPELINE                          ║
    ║  ─────────────────────────────────────────────────   ║
    ║  1. ContentCleaner.clean_html()                      ║
    ║     → remove nav, ads, hidden (CSS selectors)        ║
    ║  2. MainContentExtractor.extract()                   ║
    ║     → find article body via selectors + density      ║
    ║  3. HybridChunker.chunk()                            ║
    ║     → split by headings, then paragraphs             ║
    ║     → respect max_chunk_tokens (512)                 ║
    ║  4. JsonExtractor.extract() [for API]                ║
    ║     → Wikipedia: title, categories, pageprops        ║
    ║     → arXiv: authors, abstract, PDF URL              ║
    ║                                                      ║
    ║  Output: ExtractedDocument                           ║
    ║    {chunks: [{chunk_id, text, markdown,              ║
    ║              section_path, heading_level,             ║
    ║              char_offset, token_count}, ...],         ║
    ║     structured: {...},                               ║
    ║     extraction_quality: {...}}                       ║
    ╚════════════┬═════════════════════════════════════════╝
                 │
                 ▼
    ╔══════════════════════════════════════════════════════╗
    ║  LAYER 3: ENRICH PIPELINE                           ║
    ║  ─────────────────────────────────────────────────   ║
    ║  For each field_group:                               ║
    ║  1. Check extractive strategy possible?              ║
    ║     → RegexEnricher (free, instant)                 ║
    ║     → LookupEnricher (table-based)                  ║
    ║  2. If extractive fails → LLMClient                  ║
    ║     → OpenAI-compatible API call                     ║
    ║     → Async batch execution                          ║
    ║  3. Merge results, track confidence & evidence       ║
    ║                                                      ║
    ║  Output: EnrichedRecord                              ║
    ║    {doc_id, source_url, platform,                    ║
    ║     structured: {...},                               ║
    ║     enriched: {field_group → [fields...]}}           ║
    ╚════════════┬═════════════════════════════════════════╝
                 │
                 ▼
    ┌────────────────────────────────────────────────────────┐
    │  OUTPUT WRITING                                        │
    │  - records.jsonl (canonical format)                   │
    │  - errors.jsonl (failures + recovery)                 │
    │  - summary.json (stats)                               │
    │  - run_manifest.json (metadata)                       │
    │  - artifacts/ (debug HTML, PDFs, screenshots)         │
    └────────────────────────────────────────────────────────┘
```

---

## Layer 1: Fetch Engine

### FetchEngine Class (engine.py)

**Responsibility**: Unified URL fetching with backend selection, retry/escalation, and session management.

**Constructor**:
```python
FetchEngine(
  session_root: Path,
  max_retries: int = 2,
  http_timeout: float = 20.0
)
```

**Key Methods**:
- `async fetch(url, platform, resource_type, requires_auth, override_backend, api_fetcher)`
  - Main entry point
  - Returns `RawFetchResult`

**Internal Workflow**:
1. **Backend Resolution** (`backend_router.resolve_backend()`)
   - Check `references/backend_routing.json` for rules
   - Match platform + resource_type + auth requirement
   - Return (initial_backend, fallback_chain)

2. **Retry Loop with Escalation**
   ```
   backends_to_try = [initial_backend] + fallback_chain
   for attempt, backend in enumerate(backends_to_try):
     try:
       result = _fetch_with_backend(backend, ...)
       return result
     except HTTPStatusError as e:
       if e.status_code == 403:
         continue  # Try next backend
       elif e.status_code == 429:
         sleep(backoff)  # Rate limit, retry same backend
       else:
         raise
   ```

3. **Backend Implementation** (`_fetch_with_backend()`)
   - Dispatch to appropriate backend handler
   - Options: `http`, `api`, `playwright`, `camoufox`

### BrowserPool (browser_pool.py)

**Purpose**: Reuse browser contexts to avoid cold starts (~3-5s per context).

**Key Features**:
- Maintains a pool of Playwright/Camoufox contexts
- Reuses contexts across multiple fetch operations
- Graceful cleanup on exit
- Per-platform configuration

**Lifecycle**:
```
BrowserPool.__init__() → .start() → acquire context
→ .fetch() on context → context returned to pool
→ .close() on exit
```

### Session Manager (session_manager.py)

**Purpose**: Persist browser authentication state across runs.

**Key Operations**:
- Load/save Playwright `storage_state` (cookies, localStorage, sessionStorage)
- Detect expired sessions (403 → AUTH_EXPIRED)
- Auto-refresh after successful fetch

**Storage Structure**:
```
output/.sessions/
├── wikipedia.json (if used)
├── arxiv.json
├── amazon.json
├── linkedin.json (primary auth storage)
└── base_chain.json
```

### Backend Router (backend_router.py)

**Configuration File**: `references/backend_routing.json`
```json
{
  "rules": [
    {
      "match": {"platform": "wikipedia"},
      "initial_backend": "api",
      "fallback_chain": ["http", "playwright"]
    },
    {
      "match": {"platform": "amazon", "resource_type": "product"},
      "initial_backend": "http",
      "fallback_chain": ["playwright", "camoufox"]
    },
    {
      "match": {"platform": "linkedin", "requires_auth": true},
      "initial_backend": "api",
      "fallback_chain": ["playwright"]
    }
  ],
  "default": {
    "initial_backend": "http",
    "fallback_chain": ["playwright", "camoufox"]
  }
}
```

### Wait Strategies (wait_strategy.py)

**Purpose**: Intelligent page readiness detection before content extraction.

**Strategies** (from `references/wait_strategies.json`):
1. **Selector-based**: Wait for CSS selector to appear
   - Example: `wait_for(".article-content")`

2. **Network quiet**: Wait for pending network requests → 0
   - Example: `networkidle` / `domcontentloaded`

3. **Scroll-based**: Scroll to load lazy-loaded content
   - Example: Scroll to bottom, then wait for new content

4. **Timeout-based**: Simple sleep fallback
   - Example: `sleep(2000)`

**Config Structure**:
```json
{
  "wikipedia": [{"type": "selector", "value": "body"}],
  "amazon": [
    {"type": "selector", "value": ".a-price"},
    {"type": "networkidle", "timeout": 5000}
  ],
  "linkedin": [
    {"type": "scroll", "value": "bottom"},
    {"type": "networkidle", "timeout": 3000}
  ]
}
```

### Backend Implementations

#### HTTP Backend (http_backend.py)
- Uses `httpx` async client
- Standard HTTP headers
- Follows redirects
- Timeout: 20s default

#### API Backend (api_backend.py)
- JSON-specific requests (Wikipedia, arXiv, etc.)
- Adds `Accept: application/json` header
- Parses response as JSON

#### Playwright Backend (playwright_backend.py)
- Standard Chromium browser
- Full page wait + screenshot capture
- Interception possible
- Session state support

#### Camoufox Backend (camoufox_backend.py)
- Mozilla Firefox + anti-detection patches
- Used for high-risk sites (Amazon, LinkedIn)
- Same interface as Playwright

### RawFetchResult Model

```python
@dataclass
class RawFetchResult:
    url: str                          # Original URL
    final_url: str                    # After redirects
    backend: Literal["http", "playwright", "camoufox", "api"]
    fetch_time: datetime              # When fetched
    content_type: str                 # MIME type
    status_code: int                  # HTTP status
    html: str | None                  # HTML content
    json_data: dict | None            # Parsed JSON
    content_bytes: bytes | None       # Raw bytes (for PDFs, images)
    screenshot: bytes | None          # Screenshot bytes
    headers: dict[str, str]           # Response headers
    cookies_updated: bool             # Session state changed
    wait_strategy_used: str           # Which wait was applied
    resources_blocked: list[str]      # Blocked resource types
    timing: FetchTiming               # Performance metrics
```

---

## Layer 2: Extract Pipeline

### ExtractPipeline Class (pipeline.py)

**Constructor**:
```python
ExtractPipeline(
  max_chunk_tokens: int = 512,
  min_chunk_tokens: int = 100,
  overlap_tokens: int = 50
)
```

**Main Method**:
```python
def extract(
  fetch_result: dict,
  platform: str,
  resource_type: str
) -> ExtractedDocument
```

### Two-Branch Processing

#### Branch 1: API JSON Response

**Flow**: API JSON → JsonExtractor → structured extraction → chunking

**JsonExtractor** (structured/json_extractor.py):
- Platform-specific JSON parsing
- Example (Wikipedia):
  ```python
  data = fetch_result["json_data"]
  pages = data["query"]["pages"]
  page = next(iter(pages.values()))
  categories = [item["title"].removeprefix("Category:")
                for item in page["categories"]]
  extract = page["extract"]  # Plain text from MediaWiki
  ```

#### Branch 2: HTML Response

**Flow**: HTML → ContentCleaner → MainContentExtractor → HybridChunker

### ContentCleaner (content_cleaner.py)

**Purpose**: Remove navigation, ads, footer, and hidden elements.

**CSS Selectors** (from `references/noise_selectors.json`):
```json
{
  "generic": [
    "nav", "footer", ".navbar", ".sidebar",
    "[class*='ad'], [class*='advertisement']",
    "[style*='display:none']"
  ],
  "wikipedia": [
    ".navbox", ".reflist", ".mw-editsection"
  ],
  "amazon": [
    ".aok-inline-block.a-ads",
    ".aplus-2-module-container"
  ]
}
```

**Cleaning Logic**:
1. Parse HTML with BeautifulSoup
2. Remove matched elements via CSS selectors
3. Remove script, style tags
4. Remove HTML comments
5. Return cleaned HTML

### MainContentExtractor (main_content.py)

**Strategy** (priority order):
1. **Platform-specific CSS selector** (from `main_content_selectors.json`)
   - Wikipedia: `#mw-content-text`
   - Amazon product: `#dp-container`
   - LinkedIn profile: `[data-testid="profile-content"]`

2. **Semantic HTML tags**
   - `<article>`, `<main>`, `<section role="main">`

3. **Content density heuristics**
   - Calculate char/tag ratio
   - Find div with highest density (likely content)
   - Fallback: body tag

**Output**: BeautifulSoup element representing main content.

### HybridChunker (chunking/hybrid_chunker.py)

**Purpose**: Split long-form content into LLM-friendly chunks.

**Strategy**:
```
1. Extract all headings (h1-h6)
2. For each heading block (content between h2...h2):
   a. If block ≤ max_chunk_tokens → one chunk
   b. If block > max_chunk_tokens:
      - Split by paragraphs
      - Accumulate until next chunk would exceed limit
      - Respect min_chunk_tokens
      - Add overlap_tokens to next chunk
3. Generate chunk_id, section_path, heading_text, etc.
4. Estimate tokens (word count / 1.3)
```

**Output Chunk Structure**:
```python
@dataclass
class ContentChunk:
    chunk_id: str                  # e.g., "abc123#chunk_0"
    chunk_index: int               # 0-based
    text: str                      # Plain text
    markdown: str                  # Markdown format
    section_path: list[str]        # Hierarchical path: ["Section", "Subsection"]
    heading_text: str              # Current heading
    heading_level: int             # 1-6
    char_offset_start: int         # In original document
    char_offset_end: int
    token_count_estimate: int      # Estimated token count
```

### ExtractedDocument Model

```python
@dataclass
class ExtractedDocument:
    doc_id: str                    # Deterministic hash of URL + platform
    url: str
    platform: str
    resource_type: str
    status: str                    # "success", "partial", "error"
    chunks: list[ContentChunk]
    structured: StructuredFields   # API-specific extraction (categories, etc.)
    extraction_quality: ExtractionQuality
    metadata: dict                 # title, source_url, etc.
    plain_text: str
    markdown: str
    timestamp: datetime
```

---

## Layer 3: Enrich Pipeline

### EnrichPipeline Class (pipeline.py)

**Constructor**:
```python
EnrichPipeline(
  model_config: dict | None = None,
  llm_client: LLMClient | None = None
)
```

**Main Method**:
```python
async def enrich(
  document: dict,
  field_groups: list[str]
) -> EnrichedRecord
```

### Two-Tier Enrichment Strategy

#### Tier 1: Extractive Enrichment (Fast, Free)

**RegexEnricher** (extractive/regex_enricher.py):
- Pattern files from `references/skill_patterns.json`
- Examples:
  - Email: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
  - Phone: `\+?1?\d{9,15}`
  - URL: `https?://[^\s]+`
  - Code snippet: `` ```[a-z]*\n(.*?)\n``` ``

**LookupEnricher** (extractive/lookup_enricher.py):
- Static lookup tables from `references/lookup_tables/`
- Examples:
  - Country codes (ISO-3166)
  - Programming languages
  - Company tickers
  - Domain TLDs

**Result**: `ExtractiveResult(fields={field_name: value, ...}, confidence, evidence_source)`

#### Tier 2: Generative Enrichment (LLM-Backed, On-Demand)

**LLMClient** (generative/llm_client.py):
- Supports OpenAI-compatible API (base_url, api_key, model)
- Async request batching
- Error handling (rate limits, timeouts)

**PromptRenderer** (generative/prompt_renderer.py):
- Template-based prompt generation
- Injects field group spec + document content
- Example:
  ```
  "Extract the main topic categories from the following document:\n\n"
  + document["markdown"] +
  "\n\nReturn valid JSON: {\"topics\": [...]}"
  ```

**Flow**:
```python
if extractive_result.confidence >= threshold:
  return extractive_result
else:
  llm_result = await llm_client.complete(prompt)
  return llm_result
```

### Field Group Definitions (FieldGroupRegistry)

**Location**: `crawler/enrich/schemas/field_group_registry.py`

**Example Field Group**:
```python
FieldGroupSpec(
  name="summaries",
  description="Abstract, key points",
  fields=[
    FieldDefinition(
      name="abstract",
      type="string",
      source_fields=["plain_text", "markdown"],
      extractive_config=RegexConfig(pattern="..."),
      generative_config=GenerativeConfig(
        model="gpt-4",
        prompt_template="Summarize in 2-3 sentences"
      )
    ),
    ...
  ]
)
```

**Typical Field Groups**:
- `summaries` - abstracts, key points, executive summaries
- `classifications` - topics, categories, tags, skill tags
- `linkables` - mentioned people, companies, products, URLs
- `multimodal` - image captions, code snippets, figures
- `behavior` - user actions, engagement, sentiment
- `risk` - trust scores, red flags, quality metrics
- `code` - programming languages, complexity, patterns
- `figures` - numbers, statistics, metrics

### EnrichedRecord Model

```python
@dataclass
class EnrichedRecord:
    doc_id: str
    source_url: str
    platform: str
    resource_type: str
    structured: StructuredFields           # API extraction
    enriched: dict[str, FieldGroupResult]  # {field_group → {fields → values}}
    metadata: dict
    timestamp: datetime
    processing_stats: dict                 # timing, confidence scores
```

---

## Platform Adapters

### PlatformAdapter Base Class (platforms/base.py)

**Architecture**: Declarative adapter pattern with pluggable functions.

```python
@dataclass(frozen=True)
class PlatformAdapter:
    platform: str                          # e.g., "wikipedia"
    discovery: PlatformDiscoveryPlan       # Resource types, canonicalizer
    fetch: PlatformFetchPlan               # Backend defaults, auth requirement
    extract: PlatformExtractPlan           # Extraction strategy
    normalize: PlatformNormalizePlan       # Normalization hook
    enrich: PlatformEnrichmentPlan         # Enrichment route, field groups
    error: PlatformErrorPlan               # Error classification

    # Pluggable functions
    resolve_backend_fn: Callable[...]      # Backend selection
    fetch_fn: Callable[...]                # Platform-specific fetch
    extract_fn: Callable[...]              # Platform-specific extraction
    normalize_fn: Callable[...]            # Output normalization
    enrichment_fn: Callable[...]           # Enrichment routing
```

### Platform Implementations

#### Wikipedia (wikipedia.py - 78 LOC)

**Discovery**:
- Input: `{"platform":"wikipedia", "resource_type":"article", "title":"Artificial Intelligence"}`
- URL: `https://en.wikipedia.org/wiki/Artificial_Intelligence`

**Fetch Plan**:
- Default: `api` (MediaWiki)
- Fallback: `http`, `playwright`
- Auth: Not required (public)

**Fetch Implementation**:
```python
def _fetch_wikipedia_api(record, discovered, storage_state_path):
  title = discovered["fields"]["title"]
  endpoint = (
    "https://en.wikipedia.org/w/api.php"
    f"?action=query&titles={quote(title)}"
    "&prop=extracts|categories|pageprops&explaintext=1&cllimit=20&format=json&redirects=1"
  )
  return fetch_api_get(endpoint, headers={"Accept": "application/json"})
```

**Extraction**:
- Parses `query.pages[*].extract` → plain_text
- Extracts `categories[*].title` → structured.categories
- Builds markdown: `# {title}\n\n{extract}`

**Enrichment**:
- Route: `knowledge_base`
- Field groups: `summaries`, `references`

#### arXiv (arxiv.py - 75 LOC)

**Discovery**:
- Input: `{"platform":"arxiv", "resource_type":"paper", "arxiv_id":"2401.12345"}`
- URL: `https://arxiv.org/api/query?search_query=arxiv_id:2401.12345`

**Fetch Plan**:
- Default: `api` (Atom XML)
- Fallback: `http` (PDF)
- Auth: Not required

**Extraction**:
- Parses Atom XML → title, authors, abstract, published date
- Extracts PDF URL from `link[@type="application/pdf"]@href`
- Identifies primary category

#### Amazon (amazon.py - 47 LOC)

**Discovery**:
- Input: `{"platform":"amazon", "resource_type":"product", "asin":"B09V3KXJPB"}`
- URL: `https://www.amazon.com/dp/{asin}`

**Fetch Plan**:
- Default: `http`
- Fallback: `playwright`, `camoufox`
- Auth: Not required (but anti-bot detection)

**Extraction**:
- Parses dynamic product page (requires browser or JavaScript rendering)
- Extracts: title, price, rating, reviews, availability

#### Base Chain (base_chain.py - 103 LOC)

**Discovery**:
- Input: `{"platform":"base", "resource_type":"transaction", "tx_hash":"0xabc..."}`
- URL: `https://basescan.io/tx/{tx_hash}`

**Fetch Plan**:
- Default: `api` (Basescan/Etherscan V2)
- Fallback: `http`, `playwright`
- Auth: Optional (Etherscan API key)

**Extraction**:
- Queries Base RPC / Etherscan API
- Extracts: sender, receiver, value, gas, status, timestamp
- Structured: JSON from blockchain

#### LinkedIn (linkedin.py - 539 LOC)

**Discovery**:
- Input: `{"platform":"linkedin", "resource_type":"profile", "public_identifier":"john-doe-ai"}`
- URL: `https://www.linkedin.com/in/{public_identifier}`

**Fetch Plan**:
- Default: `api` (Voyager, LinkedIn's internal API)
- Fallback: `playwright` (browser scraping)
- Auth: **Required** (cookies or storage_state)

**Fetch Implementation**:
- Voyager API call with Authorization header
- Falls back to browser if Voyager fails
- Handles `401/403` → AUTH_EXPIRED

**Extraction**:
- Parses Voyager JSON or HTML
- Extracts: headline, experience, education, skills

---

## Configuration Files

### backend_routing.json

Drives backend selection logic. Example:
```json
{
  "rules": [
    {
      "match": {"platform": "wikipedia"},
      "initial_backend": "api",
      "fallback_chain": ["http", "playwright"]
    },
    {
      "match": {"platform": "amazon"},
      "initial_backend": "http",
      "fallback_chain": ["playwright", "camoufox"]
    }
  ],
  "default": {"initial_backend": "http", "fallback_chain": []}
}
```

### url_templates.json

URL canonicalization patterns. Example:
```json
{
  "wikipedia": "https://en.wikipedia.org/wiki/{title}",
  "arxiv": "https://arxiv.org/api/query?search_query={arxiv_id}",
  "amazon": "https://www.amazon.com/dp/{asin}",
  "linkedin": "https://www.linkedin.com/in/{public_identifier}"
}
```

### wait_strategies.json

Per-platform intelligent wait logic. Example:
```json
{
  "wikipedia": [{"type": "selector", "value": "#mw-content-text"}],
  "amazon": [
    {"type": "selector", "value": ".a-price"},
    {"type": "networkidle", "timeout": 5000}
  ]
}
```

### noise_selectors.json

CSS selectors for noise removal. Example:
```json
{
  "generic": ["nav", "footer", ".ads"],
  "wikipedia": [".navbox", ".reflist"],
  "amazon": [".aok-inline-block.a-ads"]
}
```

### skill_patterns.json

Regex patterns for extraction. Example:
```json
{
  "email": "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}",
  "phone": "\\+?1?\\d{9,15}",
  "url": "https?://[^\\s]+"
}
```

---

## Command-Line Interface

### Commands

#### 1. Crawl (Fetch + Extract)

```bash
python -m crawler crawl \
  --input ./records.jsonl \
  --output ./out \
  --backend http \
  --resume \
  --artifacts-dir ./out/artifacts \
  --strict
```

Options:
- `--input` (required): JSONL input file
- `--output` (required): Output directory
- `--backend` (optional): Force specific backend (http, api, playwright, camoufox)
- `--cookies` (optional): Browser cookies/storage_state file
- `--resume`: Append to existing output
- `--artifacts-dir`: Custom artifact directory
- `--strict`: Return non-zero exit code on any failure

#### 2. Enrich (Enrichment Only)

```bash
python -m crawler enrich \
  --input ./out/records.jsonl \
  --output ./out-enriched \
  --field-group summaries \
  --field-group classifications \
  --model-config ./model.json
```

Options:
- `--field-group` (repeatable): Enrichment field groups to apply
- `--model-config` (optional): LLM API configuration

#### 3. Run (Crawl + Enrich)

```bash
python -m crawler run \
  --input ./records.jsonl \
  --output ./out \
  --max-chunk-tokens 512 \
  --chunk-overlap 50
```

Options:
- All crawl + enrich options combined
- `--max-chunk-tokens`: Maximum tokens per chunk (default: 512)
- `--chunk-overlap`: Overlap tokens between chunks (default: 50)

#### 4. Fill-Enrichment (Agent-Executed Enrichment)

```bash
python -m crawler fill-enrichment \
  --records ./records.jsonl \
  --responses ./llm_responses.json
```

Purpose: Allow agents to execute LLM enrichment externally, then fill results back.

---

## Output Contract

### Directory Structure

```
output/
├── records.jsonl                 # Canonical records (1 per line)
├── errors.jsonl                  # Error records
├── summary.json                  # Aggregated statistics
├── run_manifest.json             # Execution metadata
├── .sessions/                    # Browser session state
│   ├── wikipedia.json
│   ├── linkedin.json
│   └── ...
└── artifacts/                    # Debug data
    └── <resource_id>/
        ├── raw_response.html
        ├── extracted.json
        ├── screenshot.png
        └── enriched.json
```

### records.jsonl Format

```json
{
  "platform": "wikipedia",
  "resource_type": "article",
  "canonical_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
  "status": "success",
  "stage": "enriched",
  "plain_text": "Artificial intelligence is intelligence demonstrated by machines...",
  "markdown": "# Artificial Intelligence\n\nArtificial intelligence is...",
  "chunks": [
    {
      "chunk_id": "abc123#chunk_0",
      "chunk_index": 0,
      "text": "Artificial intelligence is intelligence demonstrated by machines...",
      "markdown": "# Introduction\n\nArtificial intelligence...",
      "section_path": ["Introduction"],
      "heading_text": "Introduction",
      "heading_level": 1,
      "char_offset_start": 0,
      "char_offset_end": 512,
      "token_count_estimate": 128
    }
  ],
  "structured": {
    "categories": ["Machine Learning", "Computer Science", "Philosophy"]
  },
  "extraction_quality": {
    "content_ratio": 0.42,
    "noise_removed": 15,
    "chunking_strategy": "hybrid:platform_selector",
    "total_chunks": 8
  },
  "enriched": {
    "summaries": {
      "abstract": "Artificial intelligence is the broad field of computer science...",
      "key_points": ["Machine learning", "Natural language processing", "Robotics"]
    },
    "classifications": {
      "topics": ["AI", "Computer Science", "Technology"]
    }
  },
  "metadata": {
    "title": "Artificial intelligence",
    "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "fetch_backend": "api",
    "fetch_time_ms": 450,
    "extraction_time_ms": 200,
    "enrichment_time_ms": 100
  }
}
```

### errors.jsonl Format

```json
{
  "platform": "amazon",
  "resource_type": "product",
  "canonical_url": "https://www.amazon.com/dp/B09V3KXJPB",
  "status": "failed",
  "stage": "fetch",
  "error_code": "BLOCKED_BY_ANTI_BOT",
  "retryable": true,
  "next_action": "retry with camoufox backend or supply valid cookies",
  "message": "HTTP 403 Forbidden",
  "metadata": {
    "failed_backend": "http",
    "retry_count": 1
  }
}
```

### summary.json Format

```json
{
  "command": "run",
  "timestamp": "2026-03-29T10:30:00Z",
  "total_records": 10,
  "succeeded": 9,
  "failed": 1,
  "skipped": 0,
  "stages": {
    "fetch": {"succeeded": 10, "failed": 0},
    "extract": {"succeeded": 10, "failed": 0},
    "enrich": {"succeeded": 9, "failed": 1}
  },
  "timing": {
    "total_ms": 15000,
    "fetch_ms": 5000,
    "extract_ms": 7000,
    "enrich_ms": 3000
  },
  "backends_used": ["api", "http", "playwright"],
  "enrichment_fields_applied": ["summaries", "classifications"]
}
```

---

## Concurrency & Performance

### Async Execution

- **FetchEngine**: Async HTTP client, browser pool management
- **ExtractPipeline**: Synchronous (single-threaded per record)
- **EnrichPipeline**: Async batch execution for LLM calls
- **Overall**: `asyncio` for orchestration

### Performance Characteristics

- **Cold browser startup**: ~3-5s per context (cached after)
- **HTTP fetch**: <1s typical
- **API fetch**: <1s typical
- **HTML cleaning + extraction**: <500ms typical
- **Chunking**: <100ms typical
- **Enrichment (extractive)**: <10ms per field
- **Enrichment (generative)**: ~1-5s per LLM call

### Bottlenecks

1. **Browser startup** - mitigated by BrowserPool reuse
2. **LLM API latency** - mitigated by async batch execution
3. **Network latency** - inherent to web crawling
4. **Site complexity** - depends on HTML structure

---

## Current Limitations & Future Improvements

### Known Limitations

1. **LinkedIn Authentication**
   - Requires manual login or cookie export
   - Voyager API limited without full browser context
   - Post scraping still browser-dependent

2. **Error Recovery**
   - Some errors are fatal without manual rerun
   - Limited automatic retry logic
   - Session expiry detection works but requires manual refresh

3. **Enrichment Cost**
   - LLM enrichment can be expensive at scale
   - No cross-run caching for LLM results
   - Field groups are platform-agnostic (not customized)

4. **Extraction Robustness**
   - Depends on site-specific CSS selectors
   - Requires maintenance as sites update
   - Semantic chunking works best for articles

5. **Scalability**
   - Single-machine only (no distributed execution)
   - BrowserPool not optimized for high concurrency
   - No load balancing or failover

6. **Observability**
   - Limited logging in async pipeline
   - No distributed tracing
   - Error codes could be more transparent

### Suggested Improvements

1. **Session Caching** - Store LLM enrichment results for deduplication
2. **Distributed Execution** - Task queue (Celery/Redis) for multi-machine
3. **Enhanced Logging** - Structured logging, OpenTelemetry integration
4. **Field Group Customization** - Platform-specific enrichment specs
5. **Advanced Auth** - OAuth2 support, headless browser automation for login
6. **Fallback Strategies** - More granular error handling and recovery
7. **Content Quality Scoring** - Confidence metrics per extraction
8. **Metrics Export** - Prometheus-compatible metrics endpoint

---

## Comparison to Reference Systems

### vs. Firecrawl

| Dimension | social-crawler | Firecrawl |
|-----------|---|---|
| **Execution** | Local Python | Managed API service |
| **Platforms** | 5 pre-integrated | Generic web crawler |
| **Cost** | $0 (local) | Pay-per-call |
| **Session State** | Persistent (.sessions/) | Stateless |
| **Enrichment** | Extractive-first + LLM | LLM-first |
| **Output Format** | JSONL + LLM-ready chunks | LLM-formatted HTML/MD |
| **Customization** | Platform adapters | API configuration |
| **Latency** | ~5-10s per URL | ~2-5s per URL |

**When to use social-crawler**:
- Local/on-premise execution required
- Platform-specific extraction needed
- Cost-sensitive at scale
- Session state management important

**When to use Firecrawl**:
- Generic web crawler needed
- Managed service preferred
- Speed/reliability is priority
- Per-call API acceptable

### vs. Scrapy

| Dimension | social-crawler | Scrapy |
|-----------|---|---|
| **Level** | High-level, opinionated | Low-level, flexible |
| **Learning Curve** | Low | Steep |
| **Pre-integration** | 5 platforms | 0 (DIY) |
| **Browser Support** | Native (Playwright/Camoufox) | Via middleware |
| **Async** | asyncio-native | Twisted |
| **Deployment** | Single script | Full application |
| **Debugging** | Built-in artifacts | Manual |

**When to use social-crawler**:
- Quick start needed
- Supported platforms sufficient
- Agent-native output important

**When to use Scrapy**:
- Deep customization needed
- Large-scale distributed crawling
- Complex project structure justified

### vs. Crawl4AI

| Dimension | social-crawler | Crawl4AI |
|-----------|---|---|
| **Focus** | Multi-platform + enrichment | LLM-ready content |
| **Platforms** | 5 specific | Generic web |
| **Enrichment** | Extractive + generative | None (output only) |
| **Chunking** | Semantic + token-aware | AI-powered segmentation |
| **API-first** | Yes (Wikipedia, arXiv) | Browser-only |
| **Session State** | Persistent | Per-run only |

---

## Developer Guide

### Key Entry Points

1. **CLI Entry** (`cli.py`)
   - Argument parsing
   - Config validation
   - Orchestration of command execution

2. **Pipeline Router** (`core/pipeline.py`)
   - Decides new vs legacy pipeline
   - Orchestrates layers in sequence

3. **Fetch Engine** (`fetch/engine.py`)
   - URL data acquisition
   - Backend selection + escalation

4. **Extract Pipeline** (`extract/pipeline.py`)
   - Content cleaning + chunking
   - Structured extraction

5. **Enrich Pipeline** (`enrich/pipeline.py`)
   - Extractive + generative enrichment
   - Field group orchestration

### Adding a New Platform

1. Create `crawler/platforms/newplatform.py`:
   ```python
   from .base import PlatformAdapter, PlatformDiscoveryPlan, ...

   def _fetch_newplatform(record, discovered, storage_state_path):
       # Implement fetch logic
       return fetch_result

   def _extract_newplatform(record, fetched):
       # Implement extraction logic
       return extracted_data

   ADAPTER = PlatformAdapter(
       platform="newplatform",
       discovery=PlatformDiscoveryPlan(...),
       fetch=PlatformFetchPlan(...),
       extract=PlatformExtractPlan(...),
       # ... other plans
       fetch_fn=_fetch_newplatform,
       extract_fn=_extract_newplatform,
       # ... other functions
   )
   ```

2. Register in `crawler/platforms/registry.py`:
   ```python
   from .newplatform import ADAPTER

   REGISTRY["newplatform"] = ADAPTER
   ```

3. Add to `references/backend_routing.json`:
   ```json
   {
     "match": {"platform": "newplatform"},
     "initial_backend": "http",
     "fallback_chain": ["playwright"]
   }
   ```

4. Create input fixtures and test.

### Adding a New Enrichment Field Group

1. Define in `crawler/enrich/schemas/field_group_registry.py`:
   ```python
   FIELD_GROUP_REGISTRY["mynewgroup"] = FieldGroupSpec(
       name="mynewgroup",
       description="...",
       fields=[
           FieldDefinition(name="field1", ...),
           # ...
       ]
   )
   ```

2. Define regex patterns in `references/skill_patterns.json` (if using extractive).

3. Define lookup tables in `references/lookup_tables/` (if using lookup enrichment).

4. Test via:
   ```bash
   python -m crawler enrich --input records.jsonl --output out --field-group mynewgroup
   ```

---

## Summary

**social-data-crawler** is a well-architected, production-ready crawler framework with:

✓ Clean 3-layer pipeline (Fetch → Extract → Enrich)
✓ Intelligent backend routing and fallback chains
✓ LLM-friendly semantic chunking
✓ Extractive-first enrichment strategy
✓ Persistent session management
✓ Deterministic JSONL output
✓ Comprehensive configuration system
✓ 5 pre-integrated platforms
✓ Agent-native output contract

Its main strengths are **local execution**, **platform-specific optimizations**, and **agent-friendly output formats**. The main opportunities for improvement are **distributed execution**, **enhanced error recovery**, and **observability instrumentation**.
