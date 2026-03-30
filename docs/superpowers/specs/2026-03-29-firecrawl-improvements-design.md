# Firecrawl-Inspired Improvements Design

> Date: 2026-03-29
> Status: Approved

## Overview

Implement two core capabilities borrowed from Firecrawl:
1. **Sitemap Discovery** — Automatic URL discovery from sitemaps
2. **AI Schema Extraction** — LLM-driven structured data extraction with schema/prompt support

Replace old fixed-rule extraction with AI-driven approach.

## 1. Sitemap Discovery

### 1.1 New Component

**File:** `crawler/discovery/sitemap_discoverer.py`

**Class:** `SitemapDiscoverer`

```python
class DiscoveredURL(BaseModel):
    url: str
    lastmod: str | None = None
    changefreq: str | None = None
    priority: float | None = None
    source: Literal["sitemap", "sitemap_index", "robots_txt"]

class SitemapDiscoverer:
    """Discover URLs from sitemaps, following Firecrawl's three-mode approach."""

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self._client = http_client

    async def discover(
        self,
        base_url: str,
        mode: Literal["include", "only", "skip"] = "include",
        max_urls: int = 10000,
    ) -> list[DiscoveredURL]:
        """
        Discover URLs from a domain.

        Args:
            base_url: Domain root URL (e.g., "https://example.com")
            mode: Discovery mode
                - "include": Combine sitemap URLs with crawled links (default)
                - "only": Only use sitemap URLs, don't crawl links
                - "skip": Skip sitemap, only crawl links
            max_urls: Maximum URLs to return

        Returns:
            List of discovered URLs with metadata
        """
```

### 1.2 Discovery Logic

1. **Check robots.txt** for `Sitemap:` directives
2. **Try standard locations:**
   - `/sitemap.xml`
   - `/sitemap_index.xml`
   - `/sitemap-index.xml`
3. **Parse sitemap index** → recursively fetch child sitemaps
4. **Parse standard sitemaps** → extract `<url>` entries
5. **Deduplicate and sort** by priority/lastmod

### 1.3 Integration Point

In `crawler/core/pipeline.py`, add sitemap discovery as an optional input source:

```python
# If sitemap_mode is set, discover URLs first
if config.sitemap_mode != "skip":
    discoverer = SitemapDiscoverer()
    discovered = await discoverer.discover(config.base_url, config.sitemap_mode)
    # Merge with input records or use as primary source
```

## 2. AI Schema Extraction

### 2.1 New Component

**File:** `crawler/extract/schema_extractor.py`

**Class:** `SchemaExtractor`

```python
class ExtractionResult(BaseModel):
    """Result of AI schema extraction."""
    data: dict[str, Any]
    confidence: float
    model_used: str
    tokens_used: int | None = None
    extraction_mode: Literal["schema", "prompt", "combined"]

class SchemaExtractor:
    """AI-driven structured data extraction, inspired by Firecrawl /extract."""

    def __init__(self, llm_client: LLMClient | None = None):
        self._llm = llm_client

    async def extract(
        self,
        content: str,
        *,
        schema: dict | None = None,
        prompt: str | None = None,
        platform: str | None = None,
    ) -> ExtractionResult:
        """
        Extract structured data from content using AI.

        Three modes (following Firecrawl):
        1. Schema mode: JSON Schema defines output structure
        2. Prompt mode: Natural language describes what to extract
        3. Combined mode: Schema + prompt for guided extraction

        Args:
            content: Text content (markdown or plain text)
            schema: JSON Schema defining expected output structure
            prompt: Natural language description of what to extract
            platform: Optional platform name to use predefined schema

        Returns:
            ExtractionResult with extracted data and metadata
        """
```

### 2.2 Extraction Modes

**Mode 1: Schema**
```python
result = await extractor.extract(
    content=markdown,
    schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Article title"},
            "author": {"type": "string", "description": "Author name"},
            "published_date": {"type": "string", "format": "date"},
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-5 main points"
            }
        },
        "required": ["title"]
    }
)
```

**Mode 2: Prompt**
```python
result = await extractor.extract(
    content=markdown,
    prompt="Extract: company name, founding year, headquarters location, key products"
)
```

**Mode 3: Combined**
```python
result = await extractor.extract(
    content=markdown,
    schema={"type": "object", "properties": {...}},
    prompt="Focus on financial metrics and ignore marketing content"
)
```

### 2.3 LLM Prompt Template

```python
SCHEMA_EXTRACTION_PROMPT = """
You are a precise data extraction assistant. Extract structured data from the content below.

{schema_section}
{prompt_section}

Content:
---
{content}
---

Return ONLY valid JSON matching the schema. No explanations.
"""
```

### 2.4 Platform Predefined Schemas

**File:** `crawler/extract/platform_schemas.py`

```python
PLATFORM_SCHEMAS = {
    "wikipedia": {
        "article": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "categories": {"type": "array", "items": {"type": "string"}},
                "infobox": {"type": "object"},
                "sections": {"type": "array", "items": {"type": "string"}},
            }
        }
    },
    "arxiv": {
        "paper": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "authors": {"type": "array", "items": {"type": "string"}},
                "abstract": {"type": "string"},
                "categories": {"type": "array", "items": {"type": "string"}},
                "arxiv_id": {"type": "string"},
            }
        }
    },
    # ... more platforms
}
```

## 3. ExtractPipeline Changes

### 3.1 Current Flow (to be replaced)

```
HTML → ContentCleaner → MainContentExtractor → HybridChunker → JsonExtractor (fixed rules)
```

### 3.2 New Flow

```
HTML → ContentCleaner → MainContentExtractor → HybridChunker
                                                    ↓
                                            SchemaExtractor (AI-driven)
                                                    ↓
                                            StructuredFields output
```

### 3.3 Modified ExtractPipeline

```python
class ExtractPipeline:
    def __init__(
        self,
        max_chunk_tokens: int = 512,
        min_chunk_tokens: int = 100,
        overlap_tokens: int = 50,
        llm_client: LLMClient | None = None,
    ):
        self.cleaner = ContentCleaner()
        self.main_extractor = MainContentExtractor()
        self.chunker = HybridChunker(...)
        self.schema_extractor = SchemaExtractor(llm_client)  # NEW

    async def extract(
        self,
        fetch_result: dict[str, Any],
        platform: str,
        resource_type: str,
        *,
        schema: dict | None = None,      # NEW
        prompt: str | None = None,        # NEW
    ) -> ExtractedDocument:
        # ... existing cleaning and chunking ...

        # NEW: AI schema extraction instead of JsonExtractor
        extraction_result = await self.schema_extractor.extract(
            content=main_content.markdown,
            schema=schema,
            prompt=prompt,
            platform=platform,
        )

        structured = StructuredFields(
            title=extraction_result.data.get("title"),
            description=extraction_result.data.get("description") or extraction_result.data.get("summary"),
            platform_fields=extraction_result.data,
            extraction_mode=extraction_result.extraction_mode,
        )

        # ... rest of document building ...
```

## 4. Files to Delete

| File | Reason |
|------|--------|
| `crawler/extract/structured/json_extractor.py` | Replaced by SchemaExtractor |
| `crawler/extract/structured/__init__.py` | Empty after removal |

## 5. CLI Changes

### 5.1 New Arguments

```python
# In cli.py build_parser()
subparser.add_argument(
    "--extract-schema",
    dest="extract_schema",
    type=str,
    help="JSON Schema for AI extraction (JSON string or file path)",
)
subparser.add_argument(
    "--extract-prompt",
    dest="extract_prompt",
    type=str,
    help="Natural language prompt for AI extraction",
)
subparser.add_argument(
    "--sitemap-mode",
    dest="sitemap_mode",
    choices=["include", "only", "skip"],
    default="skip",
    help="Sitemap discovery mode (default: skip)",
)
subparser.add_argument(
    "--base-url",
    dest="base_url",
    type=str,
    help="Base URL for sitemap discovery",
)
```

### 5.2 Config Changes

Add to `CrawlerConfig`:
```python
extract_schema: dict | None = None
extract_prompt: str | None = None
sitemap_mode: Literal["include", "only", "skip"] = "skip"
base_url: str | None = None
```

## 6. Input JSONL Support

Allow per-record schema/prompt in input:

```jsonl
{"url": "https://example.com/page1", "extract_prompt": "Extract product name and price"}
{"url": "https://example.com/page2", "extract_schema": {"type": "object", ...}}
```

## 7. Error Handling

- **No LLM configured:** Fall back to basic HTML meta extraction (title, description from meta tags)
- **LLM failure:** Return partial result with error flag
- **Invalid schema:** Raise validation error before extraction
- **Empty content:** Return empty structured fields

## 8. Testing Strategy

1. **Unit tests** for SitemapDiscoverer with mock HTTP responses
2. **Unit tests** for SchemaExtractor with mock LLM responses
3. **Integration tests** for full pipeline with both components
4. **Contract tests** to ensure output format compatibility

## 9. Migration Notes

- Old `JsonExtractor` output format preserved in `platform_fields`
- Existing tests updated to use new async interface
- Default behavior (no schema/prompt) uses platform predefined schemas
