---
name: crawl4ai
description: Web crawling with Crawl4AI - converts any URL to LLM-ready markdown
version: 1.0.0
requires:
  bins:
    - python3
  pip:
    - crawl4ai
---

# Crawl4AI Skill

Convert any URL to clean, LLM-ready markdown.

## Quick Usage

```bash
# Single URL fetch
python -c "
import asyncio
from crawl4ai import AsyncWebCrawler

async def fetch(url):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
        print(result.markdown)

asyncio.run(fetch('$URL'))
"
```

## When to Use

- Fetch any webpage and convert to markdown
- Extract content from JS-rendered pages
- Prepare web content for LLM processing

## Features

- Automatic JS rendering (Playwright)
- Clean markdown output
- Metadata extraction
- Link extraction
- No API key required (runs locally)

## Examples

### Basic fetch
```bash
python -c "import asyncio; from crawl4ai import AsyncWebCrawler; asyncio.run((lambda: AsyncWebCrawler().__aenter__().then(lambda c: c.arun('https://example.com')))())"
```

### With extraction strategy (CSS selectors, no AI)
```python
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

strategy = JsonCssExtractionStrategy(schema={
    "title": "h1",
    "content": "article"
})

async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url=url, extraction_strategy=strategy)
```
