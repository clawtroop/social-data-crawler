# URL Discovery Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new `Map/Crawl + PlatformAdapter/GenericAdapter` discovery framework that replaces the current ad hoc URL discovery path and supports both arbitrary webpages and platform-aware traversal.

**Architecture:** Introduce a dedicated `crawler.discovery` runtime with first-class contracts, queue/state stores, and adapter interfaces. Keep fetch/extract runtime reusable, move semantic discovery into adapters, and add explicit `discover-map` and `discover-crawl` entrypoints before cutting over the main pipeline.

**Tech Stack:** Python 3.12+, dataclasses, asyncio, pytest, existing crawler fetch/extract modules

---

## File Structure

### New files

- `crawler/discovery/contracts.py`
  - shared dataclasses and enums for discovery candidates, records, map/crawl results, and options
- `crawler/discovery/adapters/base.py`
  - base discovery adapter contract
- `crawler/discovery/adapters/generic.py`
  - generic sitemap/link discovery and generic crawl expansion
- `crawler/discovery/state/job.py`
  - `JobSpec`
- `crawler/discovery/state/frontier.py`
  - `FrontierEntry`
- `crawler/discovery/state/visited.py`
  - `VisitRecord`
- `crawler/discovery/state/checkpoint.py`
  - `Checkpoint`
- `crawler/discovery/state/occupancy.py`
  - `OccupancyLease`
- `crawler/discovery/state/edges.py`
  - `DiscoveryEdge`
- `crawler/discovery/store/frontier_store.py`
  - frontier persistence and queue operations
- `crawler/discovery/store/visited_store.py`
  - dedupe and visit-state persistence
- `crawler/discovery/store/checkpoint_store.py`
  - checkpoint persistence
- `crawler/discovery/store/occupancy_store.py`
  - lease lifecycle
- `crawler/discovery/map_engine.py`
  - generic map orchestration
- `crawler/discovery/crawl_engine.py`
  - generic crawl orchestration
- `crawler/discovery/runner.py`
  - top-level discovery run entrypoints
- `crawler/tests/test_discovery_contracts.py`
- `crawler/tests/test_discovery_state.py`
- `crawler/tests/test_generic_discovery.py`
- `crawler/tests/test_discovery_runner.py`

### Modified files

- `crawler/discovery/url_builder.py`
  - refactor from bare builder to seed-record helper
- `crawler/cli.py`
  - add `discover-map` and `discover-crawl`
- `crawler/contracts.py`
  - add discovery config fields and command enum values
- `crawler/core/pipeline.py`
  - wire discovery entrypoints and future cutover hooks
- `crawler/platforms/wikipedia.py`
  - migrate discovery-specific logic out into new discovery adapter
- `crawler/platforms/amazon.py`
  - migrate search/discovery logic out into new discovery adapter
- `crawler/platforms/linkedin.py`
  - migrate search-result discovery into new discovery adapter

### Existing files to inspect while implementing

- `crawler/fetch/unified.py`
- `crawler/fetch/engine.py`
- `crawler/fetch/session_store.py`
- `references/url_templates.json`
- `references/field_mappings.json`
- `references/backend_routing.json`
- `docs/superpowers/specs/2026-03-30-url-discovery-redesign-design.md`

## Task 1: Add Discovery Contracts

**Files:**
- Create: `crawler/discovery/contracts.py`
- Modify: `crawler/contracts.py`
- Test: `crawler/tests/test_discovery_contracts.py`

- [ ] **Step 1: Write the failing tests**

```python
from crawler.discovery.contracts import (
    CrawlOptions,
    DiscoveryCandidate,
    DiscoveryMode,
    DiscoveryRecord,
    MapOptions,
)


def test_discovery_candidate_defaults():
    candidate = DiscoveryCandidate(
        platform="generic",
        resource_type="page",
        canonical_url="https://example.com/docs",
        seed_url="https://example.com",
        fields={},
        discovery_mode=DiscoveryMode.PAGE_LINKS,
        score=0.4,
        score_breakdown={"domain_trust": 0.4},
        hop_depth=1,
        parent_url="https://example.com",
        metadata={},
    )
    assert candidate.platform == "generic"
    assert candidate.discovery_mode is DiscoveryMode.PAGE_LINKS


def test_map_options_defaults_are_conservative():
    options = MapOptions()
    assert options.sitemap_mode == "include"
    assert options.include_subdomains is False
    assert options.allow_external_links is False
    assert options.ignore_query_parameters is True


def test_crawler_config_accepts_discovery_commands():
    from crawler.contracts import CrawlCommand, CrawlerConfig

    config = CrawlerConfig.from_mapping(
        {
            "command": "discover-map",
            "input_path": "input.jsonl",
            "output_dir": "out",
        }
    )
    assert config.command == CrawlCommand.DISCOVER_MAP
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_discovery_contracts.py -v`

Expected: FAIL with import errors for `crawler.discovery.contracts` and missing command enum values.

- [ ] **Step 3: Write minimal implementation**

```python
# crawler/discovery/contracts.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class DiscoveryMode(str, Enum):
    DIRECT_INPUT = "direct_input"
    CANONICALIZED_INPUT = "canonicalized_input"
    TEMPLATE_CONSTRUCTION = "template_construction"
    API_LOOKUP = "api_lookup"
    SEARCH_RESULTS = "search_results"
    GRAPH_TRAVERSAL = "graph_traversal"
    PAGE_LINKS = "page_links"
    ARTIFACT_LINK = "artifact_link"
    PAGINATION = "pagination"
    SITEMAP = "sitemap"


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    platform: str
    resource_type: str
    canonical_url: str | None
    seed_url: str | None
    fields: dict[str, str]
    discovery_mode: DiscoveryMode
    score: float
    score_breakdown: dict[str, float]
    hop_depth: int
    parent_url: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DiscoveryRecord:
    platform: str
    resource_type: str
    discovery_mode: DiscoveryMode
    canonical_url: str
    identity: dict[str, str]
    source_seed: dict[str, Any] | None = None
    discovered_from: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MapOptions:
    limit: int = 200
    sitemap_mode: Literal["include", "only", "skip"] = "include"
    include_subdomains: bool = False
    allow_external_links: bool = False
    ignore_query_parameters: bool = True
    include_paths: tuple[str, ...] = ()
    exclude_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CrawlOptions(MapOptions):
    max_depth: int = 2
    max_pages: int = 100
    crawl_entire_domain: bool = False
    max_concurrency: int = 4
    delay_seconds: float = 0.0
```

```python
# crawler/contracts.py
class CrawlCommand(str, Enum):
    DISCOVER_MAP = "discover-map"
    DISCOVER_CRAWL = "discover-crawl"
    CRAWL = "crawl"
    RUN = "run"
    ENRICH = "enrich"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_discovery_contracts.py -v`

Expected: PASS for all new contract tests.

- [ ] **Step 5: Commit checkpoint**

Checkpoint label: `plan-step: discovery-contracts`

## Task 2: Add Discovery State Models

**Files:**
- Create: `crawler/discovery/state/job.py`
- Create: `crawler/discovery/state/frontier.py`
- Create: `crawler/discovery/state/visited.py`
- Create: `crawler/discovery/state/checkpoint.py`
- Create: `crawler/discovery/state/occupancy.py`
- Create: `crawler/discovery/state/edges.py`
- Test: `crawler/tests/test_discovery_state.py`

- [ ] **Step 1: Write the failing tests**

```python
from crawler.discovery.state.frontier import FrontierEntry, FrontierStatus
from crawler.discovery.state.job import JobSpec
from crawler.discovery.state.visited import VisitRecord


def test_job_spec_keeps_mode_and_session_ref():
    job = JobSpec(
        job_id="job-1",
        mode="map",
        adapter="generic",
        seed_set=["https://example.com"],
        limits={"max_pages": 10},
        session_ref=None,
        created_at="2026-03-30T00:00:00Z",
    )
    assert job.mode == "map"
    assert job.session_ref is None


def test_frontier_entry_starts_queued():
    entry = FrontierEntry(
        frontier_id="f1",
        job_id="job-1",
        url_key="generic:https://example.com",
        canonical_url="https://example.com",
        adapter="generic",
        entity_type="page",
        depth=0,
        priority=1.0,
        discovered_from=None,
        discovery_reason="direct_input",
    )
    assert entry.status is FrontierStatus.QUEUED
    assert entry.attempt == 0


def test_visit_record_separates_map_and_crawl_state():
    record = VisitRecord(
        url_key="generic:https://example.com",
        canonical_url="https://example.com",
        scope_key="example.com",
        first_seen_at="2026-03-30T00:00:00Z",
        last_seen_at="2026-03-30T00:00:00Z",
        best_depth=0,
    )
    assert record.map_state is None
    assert record.crawl_state is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_discovery_state.py -v`

Expected: FAIL with missing modules under `crawler.discovery.state`.

- [ ] **Step 3: Write minimal implementation**

```python
# crawler/discovery/state/frontier.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FrontierStatus(str, Enum):
    QUEUED = "queued"
    LEASED = "leased"
    RETRY_WAIT = "retry_wait"
    DONE = "done"
    DEAD = "dead"


@dataclass(slots=True)
class FrontierEntry:
    frontier_id: str
    job_id: str
    url_key: str
    canonical_url: str | None
    adapter: str
    entity_type: str | None
    depth: int
    priority: float
    discovered_from: dict[str, Any] | None
    discovery_reason: str
    status: FrontierStatus = FrontierStatus.QUEUED
    attempt: int = 0
    not_before: str | None = None
    last_error: dict[str, Any] | None = None
```

```python
# crawler/discovery/state/job.py
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class JobSpec:
    job_id: str
    mode: Literal["map", "crawl"]
    adapter: str
    seed_set: list[str]
    limits: dict[str, Any]
    session_ref: str | None
    created_at: str
```

```python
# crawler/discovery/state/visited.py
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class VisitRecord:
    url_key: str
    canonical_url: str
    scope_key: str
    first_seen_at: str
    last_seen_at: str
    best_depth: int
    map_state: str | None = None
    crawl_state: str | None = None
    fetch_fingerprint: str | None = None
    final_url: str | None = None
    http_status: int | None = None
    adapter_state: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_discovery_state.py -v`

Expected: PASS for job/frontier/visited state tests.

- [ ] **Step 5: Commit checkpoint**

Checkpoint label: `plan-step: discovery-state-models`

## Task 3: Build Adapter Base and Seed Construction

**Files:**
- Create: `crawler/discovery/adapters/base.py`
- Modify: `crawler/discovery/url_builder.py`
- Test: `crawler/tests/test_discovery_contracts.py`

- [ ] **Step 1: Write the failing tests**

```python
from crawler.discovery.contracts import DiscoveryMode
from crawler.discovery.url_builder import build_seed_records


def test_build_seed_records_returns_discovery_record():
    records = build_seed_records(
        {"platform": "wikipedia", "resource_type": "article", "title": "Artificial intelligence"}
    )
    assert len(records) == 1
    assert records[0].discovery_mode is DiscoveryMode.TEMPLATE_CONSTRUCTION
    assert records[0].canonical_url == "https://en.wikipedia.org/wiki/Artificial_intelligence"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_discovery_contracts.py::test_build_seed_records_returns_discovery_record -v`

Expected: FAIL because `build_seed_records` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# crawler/discovery/adapters/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from crawler.discovery.contracts import DiscoveryCandidate, DiscoveryRecord


class BaseDiscoveryAdapter(ABC):
    platform: str
    supported_resource_types: tuple[str, ...]

    @abstractmethod
    def can_handle_url(self, url: str) -> bool:
        ...

    @abstractmethod
    def build_seed_records(self, input_record: dict[str, Any]) -> list[DiscoveryRecord]:
        ...

    @abstractmethod
    async def map(self, seed: DiscoveryRecord, context: dict[str, Any]) -> Any:
        ...

    @abstractmethod
    async def crawl(self, candidate: DiscoveryCandidate, context: dict[str, Any]) -> Any:
        ...
```

```python
# crawler/discovery/url_builder.py
from crawler.discovery.contracts import DiscoveryMode, DiscoveryRecord


def build_seed_records(record: dict) -> list[DiscoveryRecord]:
    discovered = build_url(record)
    identity = dict(discovered["fields"])
    return [
        DiscoveryRecord(
            platform=discovered["platform"],
            resource_type=discovered["resource_type"],
            discovery_mode=DiscoveryMode.TEMPLATE_CONSTRUCTION,
            canonical_url=discovered["canonical_url"],
            identity=identity,
            source_seed=record,
            discovered_from=None,
            metadata={"artifacts": discovered["artifacts"]},
        )
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_discovery_contracts.py -v`

Expected: PASS including the new seed-record test.

- [ ] **Step 5: Commit checkpoint**

Checkpoint label: `plan-step: adapter-base-and-seeds`

## Task 4: Implement In-Memory Stores and Scheduler Basics

**Files:**
- Create: `crawler/discovery/store/frontier_store.py`
- Create: `crawler/discovery/store/visited_store.py`
- Create: `crawler/discovery/store/checkpoint_store.py`
- Create: `crawler/discovery/store/occupancy_store.py`
- Create: `crawler/discovery/scheduler.py`
- Test: `crawler/tests/test_discovery_state.py`

- [ ] **Step 1: Write the failing tests**

```python
from crawler.discovery.scheduler import DiscoveryScheduler
from crawler.discovery.state.frontier import FrontierEntry


def test_scheduler_leases_highest_priority_entry():
    scheduler = DiscoveryScheduler()
    scheduler.enqueue(FrontierEntry(
        frontier_id="low",
        job_id="job-1",
        url_key="k-low",
        canonical_url="https://example.com/low",
        adapter="generic",
        entity_type="page",
        depth=0,
        priority=0.1,
        discovered_from=None,
        discovery_reason="page_links",
    ))
    scheduler.enqueue(FrontierEntry(
        frontier_id="high",
        job_id="job-1",
        url_key="k-high",
        canonical_url="https://example.com/high",
        adapter="generic",
        entity_type="page",
        depth=0,
        priority=0.9,
        discovered_from=None,
        discovery_reason="sitemap",
    ))
    leased = scheduler.lease_next(worker_id="worker-1")
    assert leased.frontier_id == "high"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_discovery_state.py::test_scheduler_leases_highest_priority_entry -v`

Expected: FAIL with missing scheduler/store modules.

- [ ] **Step 3: Write minimal implementation**

```python
# crawler/discovery/scheduler.py
from __future__ import annotations

from crawler.discovery.state.frontier import FrontierEntry, FrontierStatus


class DiscoveryScheduler:
    def __init__(self) -> None:
        self._entries: list[FrontierEntry] = []

    def enqueue(self, entry: FrontierEntry) -> None:
        self._entries.append(entry)

    def lease_next(self, worker_id: str) -> FrontierEntry:
        queued = [entry for entry in self._entries if entry.status is FrontierStatus.QUEUED]
        queued.sort(key=lambda entry: entry.priority, reverse=True)
        entry = queued[0]
        entry.status = FrontierStatus.LEASED
        return entry
```

```python
# crawler/discovery/store/frontier_store.py
class InMemoryFrontierStore:
    def __init__(self) -> None:
        self.entries = {}
```

```python
# crawler/discovery/store/visited_store.py
class InMemoryVisitedStore:
    def __init__(self) -> None:
        self.records = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_discovery_state.py -v`

Expected: PASS for scheduler priority ordering and existing state tests.

- [ ] **Step 5: Commit checkpoint**

Checkpoint label: `plan-step: scheduler-and-stores`

## Task 5: Implement Generic Adapter `map()`

**Files:**
- Create: `crawler/discovery/adapters/generic.py`
- Create: `crawler/discovery/map_engine.py`
- Test: `crawler/tests/test_generic_discovery.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from crawler.discovery.adapters.generic import GenericDiscoveryAdapter
from crawler.discovery.contracts import DiscoveryMode, DiscoveryRecord, MapOptions


@pytest.mark.asyncio
async def test_generic_map_extracts_same_domain_links_only():
    adapter = GenericDiscoveryAdapter()
    seed = DiscoveryRecord(
        platform="generic",
        resource_type="page",
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        canonical_url="https://example.com/docs",
        identity={"url": "https://example.com/docs"},
        source_seed=None,
        discovered_from=None,
        metadata={},
    )
    context = {
        "html": '''
            <html><body>
              <a href="/guide">Guide</a>
              <a href="https://example.com/api">API</a>
              <a href="https://other.com/offsite">Offsite</a>
            </body></html>
        ''',
        "options": MapOptions(),
    }
    result = await adapter.map(seed, context)
    urls = [candidate.canonical_url for candidate in result.accepted]
    assert "https://example.com/guide" in urls
    assert "https://example.com/api" in urls
    assert "https://other.com/offsite" not in urls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_generic_discovery.py -v`

Expected: FAIL because `GenericDiscoveryAdapter` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# crawler/discovery/adapters/generic.py
from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from crawler.discovery.adapters.base import BaseDiscoveryAdapter
from crawler.discovery.contracts import DiscoveryCandidate, DiscoveryMode, MapResult


class GenericDiscoveryAdapter(BaseDiscoveryAdapter):
    platform = "generic"
    supported_resource_types = ("page", "article", "listing", "document")

    def can_handle_url(self, url: str) -> bool:
        return url.startswith("http://") or url.startswith("https://")

    def build_seed_records(self, input_record: dict):
        from crawler.discovery.contracts import DiscoveryRecord

        url = input_record["url"]
        return [DiscoveryRecord(
            platform="generic",
            resource_type="page",
            discovery_mode=DiscoveryMode.DIRECT_INPUT,
            canonical_url=url,
            identity={"url": url},
            source_seed=input_record,
            discovered_from=None,
            metadata={},
        )]

    async def map(self, seed, context):
        html = context["html"]
        options = context["options"]
        soup = BeautifulSoup(html, "html.parser")
        seed_host = urlparse(seed.canonical_url).netloc
        accepted = []
        for anchor in soup.find_all("a", href=True):
            candidate_url = urljoin(seed.canonical_url, anchor["href"])
            if urlparse(candidate_url).netloc != seed_host and not options.allow_external_links:
                continue
            accepted.append(DiscoveryCandidate(
                platform="generic",
                resource_type="page",
                canonical_url=candidate_url,
                seed_url=seed.canonical_url,
                fields={},
                discovery_mode=DiscoveryMode.PAGE_LINKS,
                score=0.3,
                score_breakdown={"domain_trust": 0.3},
                hop_depth=1,
                parent_url=seed.canonical_url,
                metadata={"anchor_text": anchor.get_text(" ", strip=True)},
            ))
        return MapResult(accepted=accepted, rejected=[], exhausted=True, next_seeds=[])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_generic_discovery.py -v`

Expected: PASS for same-domain generic map behavior.

- [ ] **Step 5: Commit checkpoint**

Checkpoint label: `plan-step: generic-map`

## Task 6: Implement Generic Crawl Engine

**Files:**
- Create: `crawler/discovery/crawl_engine.py`
- Create: `crawler/discovery/runner.py`
- Test: `crawler/tests/test_discovery_runner.py`

- [x] **Step 1: Write the failing tests**

```python
import pytest

from crawler.discovery.contracts import CrawlOptions, DiscoveryCandidate, DiscoveryMode
from crawler.discovery.runner import run_discover_crawl


@pytest.mark.asyncio
async def test_run_discover_crawl_fetches_seed_and_returns_record():
    candidate = DiscoveryCandidate(
        platform="generic",
        resource_type="page",
        canonical_url="https://example.com/docs",
        seed_url="https://example.com/docs",
        fields={},
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        score=1.0,
        score_breakdown={"direct_input": 1.0},
        hop_depth=0,
        parent_url=None,
        metadata={},
    )

    async def fake_fetch(url: str) -> dict:
        return {"url": url, "html": "<html><body><h1>Docs</h1></body></html>", "content_type": "text/html"}

    records = await run_discover_crawl(
        seeds=[candidate],
        fetch_fn=fake_fetch,
        options=CrawlOptions(max_depth=0, max_pages=1),
    )
    assert records[0]["canonical_url"] == "https://example.com/docs"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_discovery_runner.py -v`

Expected: FAIL because `run_discover_crawl` does not exist.

- [x] **Step 3: Write minimal implementation**

```python
# crawler/discovery/runner.py
from __future__ import annotations

from typing import Any, Awaitable, Callable


async def run_discover_crawl(
    seeds: list,
    fetch_fn: Callable[[str], Awaitable[dict[str, Any]]],
    options,
) -> list[dict[str, Any]]:
    records = []
    for candidate in seeds[: options.max_pages]:
        fetched = await fetch_fn(candidate.canonical_url)
        records.append(
            {
                "platform": candidate.platform,
                "resource_type": candidate.resource_type,
                "canonical_url": candidate.canonical_url,
                "discovery_mode": candidate.discovery_mode.value,
                "fetched": fetched,
            }
        )
    return records
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_discovery_runner.py -v`

Expected: PASS for the crawl runner smoke test. ✅ Verified 2026-03-30

- [ ] **Step 5: Commit checkpoint**

Checkpoint label: `plan-step: generic-crawl-runner`

## Task 7: Add CLI and Config Entry Points

**Files:**
- Modify: `crawler/cli.py`
- Modify: `crawler/contracts.py`
- Modify: `crawler/core/pipeline.py`
- Test: `crawler/tests/test_cli.py`

- [x] **Step 1: Write the failing tests**

```python
from crawler.cli import parse_args
from crawler.contracts import CrawlCommand


def test_parse_discover_map_command():
    config = parse_args(["discover-map", "--input", "in.jsonl", "--output", "out"])
    assert config.command is CrawlCommand.DISCOVER_MAP


def test_parse_discover_crawl_command():
    config = parse_args(["discover-crawl", "--input", "in.jsonl", "--output", "out", "--max-depth", "3"])
    assert config.command is CrawlCommand.DISCOVER_CRAWL
    assert config.max_depth == 3
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_cli.py -v`

Expected: FAIL because the parser does not support the new commands or options.

- [x] **Step 3: Write minimal implementation**

```python
# crawler/cli.py
for command in CrawlCommand:
    subparser = subparsers.add_parser(command.value)
    subparser.set_defaults(command=command)
    subparser.add_argument("--input", dest="input_path", type=Path, required=True)
    subparser.add_argument("--output", dest="output_dir", type=Path, required=True)
    subparser.add_argument("--max-depth", dest="max_depth", type=int, default=2)
    subparser.add_argument("--max-pages", dest="max_pages", type=int, default=100)
    subparser.add_argument("--sitemap-mode", dest="sitemap_mode", choices=["include", "only", "skip"], default="include")
```

```python
# crawler/core/pipeline.py
if config.command is CrawlCommand.DISCOVER_MAP:
    return asyncio.run(run_discover_map_from_config(config)), []
if config.command is CrawlCommand.DISCOVER_CRAWL:
    return asyncio.run(run_discover_crawl_from_config(config)), []
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_cli.py -v`

Expected: PASS for the new parser behavior. ✅ Verified 2026-03-30

- [x] **Step 5: Run focused discovery test suite**

Run: `pytest crawler/tests/test_discovery_contracts.py crawler/tests/test_discovery_state.py crawler/tests/test_generic_discovery.py crawler/tests/test_discovery_runner.py crawler/tests/test_cli.py -v`

Expected: PASS across the new discovery-focused suite. ✅ Verified 2026-03-30

## Task 8: Migrate Wikipedia Discovery Adapter

**Files:**
- Create: `crawler/discovery/adapters/wikipedia.py`
- Modify: `crawler/platforms/wikipedia.py`
- Test: `crawler/tests/test_generic_discovery.py`

- [x] **Step 1: Write the failing test**

```python
import pytest

from crawler.discovery.adapters.wikipedia import WikipediaDiscoveryAdapter
from crawler.discovery.contracts import DiscoveryMode, DiscoveryRecord


@pytest.mark.asyncio
async def test_wikipedia_map_emits_article_candidates_from_api_links():
    adapter = WikipediaDiscoveryAdapter()
    seed = DiscoveryRecord(
        platform="wikipedia",
        resource_type="article",
        discovery_mode=DiscoveryMode.TEMPLATE_CONSTRUCTION,
        canonical_url="https://en.wikipedia.org/wiki/Artificial_intelligence",
        identity={"title": "Artificial_intelligence"},
        source_seed=None,
        discovered_from=None,
        metadata={},
    )
    context = {
        "page_links": ["Machine learning", "Deep learning"],
    }
    result = await adapter.map(seed, context)
    assert result.accepted[0].platform == "wikipedia"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_generic_discovery.py::test_wikipedia_map_emits_article_candidates_from_api_links -v`

Expected: FAIL because the discovery adapter does not exist.

- [x] **Step 3: Write minimal implementation**

```python
# crawler/discovery/adapters/wikipedia.py
from crawler.discovery.adapters.base import BaseDiscoveryAdapter
from crawler.discovery.contracts import DiscoveryCandidate, DiscoveryMode, MapResult


class WikipediaDiscoveryAdapter(BaseDiscoveryAdapter):
    platform = "wikipedia"
    supported_resource_types = ("article",)

    def can_handle_url(self, url: str) -> bool:
        return "wikipedia.org/wiki/" in url

    def build_seed_records(self, input_record):
        from crawler.discovery.url_builder import build_seed_records
        return build_seed_records(input_record)

    async def map(self, seed, context):
        accepted = []
        for title in context.get("page_links", []):
            slug = title.replace(" ", "_")
            accepted.append(DiscoveryCandidate(
                platform="wikipedia",
                resource_type="article",
                canonical_url=f"https://en.wikipedia.org/wiki/{slug}",
                seed_url=seed.canonical_url,
                fields={"title": slug},
                discovery_mode=DiscoveryMode.API_LOOKUP,
                score=0.8,
                score_breakdown={"api_lookup": 0.8},
                hop_depth=1,
                parent_url=seed.canonical_url,
                metadata={},
            ))
        return MapResult(accepted=accepted, rejected=[], exhausted=True, next_seeds=[])
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_generic_discovery.py::test_wikipedia_map_emits_article_candidates_from_api_links -v`

Expected: PASS for the Wikipedia adapter map behavior. ✅ Verified 2026-03-30

- [ ] **Step 5: Commit checkpoint**

Checkpoint label: `plan-step: wikipedia-discovery-adapter`

## Task 9: Migrate Amazon and LinkedIn Discovery Adapters

**Files:**
- Create: `crawler/discovery/adapters/amazon.py`
- Create: `crawler/discovery/adapters/linkedin.py`
- Modify: `crawler/platforms/amazon.py`
- Modify: `crawler/platforms/linkedin.py`
- Test: `crawler/tests/test_generic_discovery.py`

- [x] **Step 1: Write the failing tests**

```python
import pytest

from crawler.discovery.adapters.amazon import AmazonDiscoveryAdapter
from crawler.discovery.adapters.linkedin import LinkedInDiscoveryAdapter


@pytest.mark.asyncio
async def test_amazon_map_promotes_search_results_to_product_candidates():
    adapter = AmazonDiscoveryAdapter()
    result = await adapter.map_search_results(
        query="mechanical keyboard",
        urls=["https://www.amazon.com/dp/B000000001", "https://www.amazon.com/dp/B000000002"],
    )
    assert result.accepted[0].resource_type == "product"


@pytest.mark.asyncio
async def test_linkedin_map_promotes_search_results_to_entity_candidates():
    adapter = LinkedInDiscoveryAdapter()
    result = await adapter.map_search_candidates(
        query="openai",
        search_type="company",
        candidates=[{"canonical_url": "https://www.linkedin.com/company/openai/", "resource_type": "company"}],
    )
    assert result.accepted[0].resource_type == "company"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_generic_discovery.py -v`

Expected: FAIL because the new Amazon and LinkedIn discovery adapters do not exist.

- [x] **Step 3: Write minimal implementation**

```python
# crawler/discovery/adapters/amazon.py
class AmazonDiscoveryAdapter(BaseDiscoveryAdapter):
    platform = "amazon"
    supported_resource_types = ("product", "seller", "search")

    async def map_search_results(self, query: str, urls: list[str]):
        accepted = [
            DiscoveryCandidate(
                platform="amazon",
                resource_type="product",
                canonical_url=url,
                seed_url=None,
                fields={"asin": url.rstrip("/").split("/")[-1]},
                discovery_mode=DiscoveryMode.SEARCH_RESULTS,
                score=0.7,
                score_breakdown={"search_results": 0.7},
                hop_depth=1,
                parent_url=None,
                metadata={"query": query},
            )
            for url in urls
        ]
        return MapResult(accepted=accepted, rejected=[], exhausted=True, next_seeds=[])
```

```python
# crawler/discovery/adapters/linkedin.py
class LinkedInDiscoveryAdapter(BaseDiscoveryAdapter):
    platform = "linkedin"
    supported_resource_types = ("search", "profile", "company", "post", "job")

    async def map_search_candidates(self, query: str, search_type: str, candidates: list[dict]):
        accepted = [
            DiscoveryCandidate(
                platform="linkedin",
                resource_type=item["resource_type"],
                canonical_url=item["canonical_url"],
                seed_url=None,
                fields={},
                discovery_mode=DiscoveryMode.SEARCH_RESULTS,
                score=0.85,
                score_breakdown={"search_results": 0.85},
                hop_depth=1,
                parent_url=None,
                metadata={"query": query, "search_type": search_type},
            )
            for item in candidates
        ]
        return MapResult(accepted=accepted, rejected=[], exhausted=True, next_seeds=[])
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_generic_discovery.py -v`

Expected: PASS for Amazon and LinkedIn discovery adapter tests. ✅ Verified 2026-03-30

- [x] **Step 5: Run focused platform discovery suite**

Run: `pytest crawler/tests/test_discovery_contracts.py crawler/tests/test_generic_discovery.py crawler/tests/test_discovery_runner.py -v`

Expected: PASS with all discovery adapter tests green. ✅ Verified 2026-03-30

## Task 10: Cut Over the Main Pipeline

**Files:**
- Modify: `crawler/core/pipeline.py`
- Modify: `crawler/cli.py`
- Modify: `crawler/contracts.py`
- Test: `crawler/tests/test_pipeline.py`

- [x] **Step 1: Write the failing test**

```python
from crawler.contracts import CrawlerConfig
from crawler.core.pipeline import run_command


def test_run_command_dispatches_discover_map():
    config = CrawlerConfig.from_mapping(
        {
            "command": "discover-map",
            "input_path": "tests/fixtures/generic-input.jsonl",
            "output_dir": "tests/tmp/out",
        }
    )
    records, errors = run_command(config)
    assert isinstance(records, list)
    assert errors == []
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_pipeline.py::test_run_command_dispatches_discover_map -v`

Expected: FAIL because pipeline dispatch is incomplete. (Note: Pipeline was implemented in Task 7)

- [x] **Step 3: Write minimal implementation**

```python
# crawler/core/pipeline.py
def run_command(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    if config.command is CrawlCommand.DISCOVER_MAP:
        return _run_discovery_map_pipeline(config)
    if config.command is CrawlCommand.DISCOVER_CRAWL:
        return _run_discovery_crawl_pipeline(config)
    if config.use_legacy_pipeline:
        return _run_legacy_pipeline(config)
    return _run_new_pipeline(config)
```

```python
def _run_discovery_map_pipeline(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    return asyncio.run(run_discover_map_from_config(config)), []


def _run_discovery_crawl_pipeline(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    return asyncio.run(run_discover_crawl_from_config(config)), []
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_pipeline.py::test_run_command_dispatches_discover_map -v`

Expected: PASS for discovery dispatch. ✅ Verified 2026-03-30

- [x] **Step 5: Run the regression suite**

Run: `pytest crawler/tests/test_cli.py crawler/tests/test_pipeline.py crawler/tests/test_discovery_contracts.py crawler/tests/test_discovery_state.py crawler/tests/test_generic_discovery.py crawler/tests/test_discovery_runner.py -v`

Expected: PASS for both discovery routing and existing pipeline behavior not touched by the cutover. ✅ Verified 2026-03-30

## Self-Review Checklist

- Spec coverage:
  - `Map/Crawl` split: Tasks 1, 5, 6, 7, 10
  - `GenericAdapter`: Task 5
  - platform adapters: Tasks 8 and 9
  - queue/state/checkpoint model: Tasks 2 and 4
  - CLI/pipeline integration: Tasks 7 and 10
  - session separation: Tasks 2, 4, and 10
- Placeholder scan:
  - no `TODO`, `TBD`, or “implement later” placeholders remain
- Type consistency:
  - `DiscoveryCandidate`, `DiscoveryRecord`, `MapOptions`, `CrawlOptions`, `JobSpec`, and `FrontierEntry` names are consistent across tasks

## Execution Notes

- Implement tasks in order
- Keep first persistence layer in-memory if needed, then move to filesystem-backed stores without changing public contracts
- Do not merge discovery state into `.sessions`
- Keep `generic` conservative by default: same-domain, no external links, shallow depth
- Delay full removal of old adapter logic until Tasks 8 through 10 are green
