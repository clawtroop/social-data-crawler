# URL Discovery Redesign Design

> Date: 2026-03-30
> Status: Approved

## Overview

Replace the current ad hoc discovery implementation with a single discovery framework built around two explicit capabilities:

1. `Map` for fast URL discovery
2. `Crawl` for recursive fetch + expansion

The framework must support both:

- platform-aware discovery for `linkedin`, `amazon`, `wikipedia`, and future platforms
- generic discovery for arbitrary public webpages

This design follows the repository research conclusion of "one skill + platform adapters" and mirrors Firecrawl's separation between fast URL mapping and recursive crawling.

## Goals

- Support multiple discovery modes in one framework:
  - template construction
  - API-driven discovery
  - graph traversal
  - search-based discovery
  - content-based discovery
- Support arbitrary URLs through a `generic` adapter
- Keep queue, dedupe, checkpoint, and retry logic platform-agnostic
- Keep session/cookie storage separate from discovery state
- Make discovery output first-class structured records, not raw URL lists
- Allow later replacement of the current temporary crawler pipeline without compatibility hacks

## Non-Goals

- Preserve the current `crawler/platforms/*` implementation shape
- Keep `use_legacy_pipeline` as a long-term architecture anchor
- Solve every platform-specific anti-bot problem in the first pass
- Design a distributed multi-node scheduler in this phase

## Architecture

### 1. Core Split

The new runtime is split into four layers:

1. `discovery core`
   - queue scheduling
   - dedupe
   - checkpointing
   - retry/backoff
   - traversal policy
2. `discovery adapters`
   - platform or generic URL understanding
   - candidate generation
   - canonicalization
   - resource classification
3. `fetch/extract runtime`
   - backend routing
   - auth/session use
   - page/API fetch
   - extraction
4. `output/state`
   - records/errors/summary
   - frontier/visited/checkpoint persistence

### 2. Mode Split

#### `Map`

Purpose:
- discover candidate URLs quickly
- avoid heavy content persistence by default
- work well for arbitrary sites and search/result pages

Typical inputs:
- seed URL
- dataset record with identifiers
- search query seed

Typical outputs:
- normalized candidates
- candidate scores
- discovery provenance

#### `Crawl`

Purpose:
- fetch a candidate
- extract content or structured payload
- optionally expand to child candidates
- persist final crawl records

Typical outputs:
- fetched payload
- extracted content
- normalized record
- spawned candidates

### 3. Adapter Split

Two adapter families exist:

#### `GenericAdapter`

Use for arbitrary public webpages when no platform-specific adapter applies.

Responsibilities:
- accept any public URL
- canonicalize conservatively
- discover links from sitemap and HTML
- classify only at a coarse level
- assign lower-confidence scores
- obey strict traversal boundaries

#### Platform Adapters

Use for `linkedin`, `amazon`, `wikipedia`, and future supported platforms.

Responsibilities:
- deterministic identity extraction
- platform-native canonical URLs
- resource-type classification
- API-backed discovery where useful
- auth/session requirements
- platform-specific scoring and expansion rules

## Proposed File Layout

```text
crawler/
├── discovery/
│   ├── __init__.py
│   ├── contracts.py
│   ├── map_engine.py
│   ├── crawl_engine.py
│   ├── scheduler.py
│   ├── runner.py
│   ├── url_builder.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── generic.py
│   │   ├── wikipedia.py
│   │   ├── amazon.py
│   │   └── linkedin.py
│   ├── state/
│   │   ├── job.py
│   │   ├── frontier.py
│   │   ├── visited.py
│   │   ├── checkpoint.py
│   │   ├── occupancy.py
│   │   └── edges.py
│   └── store/
│       ├── frontier_store.py
│       ├── visited_store.py
│       ├── checkpoint_store.py
│       └── occupancy_store.py
├── fetch/
├── extract/
├── enrich/
└── core/
    └── pipeline.py
```

## Core Contracts

### Discovery Candidate

```python
@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    platform: str
    resource_type: str
    canonical_url: str | None
    seed_url: str | None
    fields: dict[str, str]
    discovery_mode: str
    score: float
    score_breakdown: dict[str, float]
    hop_depth: int
    parent_url: str | None
    metadata: dict[str, Any]
```

Rules:
- `canonical_url` may be absent during early generic discovery, but must be filled before fetch
- `score` is queue-facing
- `score_breakdown` is required for debugability
- `parent_url` and `discovery_mode` preserve provenance

### Discovery Record

`DiscoveryCandidate` is queue-facing. Final discovery output written to downstream stages should be normalized into a stable record:

```python
@dataclass(frozen=True, slots=True)
class DiscoveryRecord:
    platform: str
    resource_type: str
    discovery_mode: str
    canonical_url: str
    identity: dict[str, str]
    source_seed: dict[str, Any] | None
    discovered_from: dict[str, Any] | None
    metadata: dict[str, Any]
```

### Map Result

```python
@dataclass(frozen=True, slots=True)
class MapResult:
    accepted: list[DiscoveryCandidate]
    rejected: list[DiscoveryCandidate]
    exhausted: bool
    next_seeds: list[str]
```

### Crawl Result

```python
@dataclass(frozen=True, slots=True)
class CrawlResult:
    candidate: DiscoveryCandidate
    fetched: dict[str, Any]
    extracted: dict[str, Any]
    normalized: dict[str, Any]
    spawned_candidates: list[DiscoveryCandidate]
```

## Adapter Contract

```python
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
    async def map(self, seed: DiscoveryRecord, context: dict[str, Any]) -> MapResult:
        ...

    @abstractmethod
    async def crawl(self, candidate: DiscoveryCandidate, context: dict[str, Any]) -> CrawlResult:
        ...

    @abstractmethod
    def normalize_candidate(self, candidate: DiscoveryCandidate) -> DiscoveryCandidate:
        ...

    @abstractmethod
    def score_candidate(self, candidate: DiscoveryCandidate) -> float:
        ...
```

Interpretation:
- `build_seed_records()` handles template construction and dataset field mapping
- `map()` handles discovery and candidate generation
- `crawl()` handles fetch + extract + normalize + child expansion
- `normalize_candidate()` and `score_candidate()` let the scheduler remain generic

## Discovery Modes

Every candidate must carry a `discovery_mode`. Initial set:

- `direct_input`
- `canonicalized_input`
- `template_construction`
- `api_lookup`
- `search_results`
- `graph_traversal`
- `page_links`
- `artifact_link`
- `pagination`
- `sitemap`

These modes are descriptive, not execution states. They explain how the candidate was discovered.

## Generic Discovery

The `generic` adapter is the fallback for arbitrary webpages.

### Generic Map Behavior

Default behavior:
- same-domain only
- subdomains disabled by default
- external links disabled by default
- sitemap enabled by default
- shallow discovery
- query-parameter normalization enabled by default

Sources:
- sitemap URLs
- HTML anchor links
- canonical URL tags
- pagination links
- obvious content links inside article/docs/blog containers

### Generic Crawl Behavior

Default behavior:
- BFS traversal
- low concurrency
- conservative retry
- path-based filtering
- low-confidence child candidate emission

The generic adapter must not pretend to know semantic entity types beyond coarse classes such as:
- `page`
- `article`
- `listing`
- `document`

## Platform-Specific Behavior

### Wikipedia

- `build_seed_records()` uses title normalization and template construction
- `map()` may use MediaWiki API page links, category links, random-title discovery, and existence checks
- `crawl()` remains API-first for article payloads, with optional page-link expansion
- default traversal should stay high-confidence and narrow

### Amazon

- `build_seed_records()` handles `asin`, `seller_id`, and `query`
- `map()` treats search/category/list pages as discovery surfaces
- `crawl()` treats product/seller pages as durable entity records
- ASIN extraction from URLs and page attributes belongs to the adapter

### LinkedIn

- `build_seed_records()` handles deterministic profile/company/post/job/search inputs
- `map()` promotes search result extraction and result-page expansion into first-class candidates
- `crawl()` handles backend-aware authenticated fetch and resource normalization
- auth/session handling remains outside discovery state and inside fetch/session runtime

## State Model

### JobSpec

Immutable job configuration:

```python
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

### FrontierEntry

Queue row:

```python
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
    status: Literal["queued", "leased", "retry_wait", "done", "dead"]
    attempt: int
    not_before: str | None
    last_error: dict[str, Any] | None
```

### VisitRecord

Dedupe row:

```python
@dataclass(slots=True)
class VisitRecord:
    url_key: str
    canonical_url: str
    scope_key: str
    first_seen_at: str
    last_seen_at: str
    best_depth: int
    map_state: str | None
    crawl_state: str | None
    fetch_fingerprint: str | None
    final_url: str | None
    http_status: int | None
    adapter_state: dict[str, Any]
```

Important rule:
- `map_state` and `crawl_state` must remain separate
- a URL mapped successfully is not automatically considered crawled

### Checkpoint

Checkpoint is resumable progress only, not the source of truth.

### OccupancyLease

Lease state is separate from visited state and from sessions. It exists only to prevent duplicate active work and to allow recovery after worker failure.

### DiscoveryEdge

Optional provenance edge:
- parent URL
- child URL
- reason
- observed timestamp

This is useful for graph debugging and later provenance-aware ranking.

## Job Lifecycle

State transitions:

1. `created`
2. seed records normalized into `queued` frontier rows
3. `queued -> leased`
4. `leased -> discovering`
5. `discovering -> done` for `map`
6. `discovering -> fetched -> done` for `crawl`
7. retryable failures move to `retry_wait`
8. terminal failures move to `dead`
9. expired leases return work to `queued`

Checkpointing happens after batches. It never replaces frontier/visited truth.

## Separation From Session State

These must stay out of `.sessions`:

- frontier queue rows
- visited/dedupe rows
- checkpoint snapshots
- leases
- retry counters
- provenance edges
- fetch fingerprints

Only a `session_ref` may appear in discovery job config. Actual cookie/storage-state files remain in the fetch session store.

## CLI and Pipeline Shape

### New Commands

Add discovery-focused commands:

- `discover-map`
- `discover-crawl`

Retain higher-level:

- `crawl`
- `run`
- `enrich`

Interpretation:
- `discover-map`: emit discovery candidates or records without heavy extraction
- `discover-crawl`: full recursive discovery plus fetch/extract
- `crawl`: fetch explicit inputs with minimal discovery
- `run`: end-to-end crawl + enrich

### Suggested Config Additions

Add to `CrawlerConfig`:

```python
discovery_mode: Literal["direct", "map", "crawl"] = "direct"
seed_url: str | None = None
max_depth: int = 2
max_pages: int = 100
max_candidates: int = 500
sitemap_mode: Literal["include", "only", "skip"] = "include"
include_paths: tuple[str, ...] = ()
exclude_paths: tuple[str, ...] = ()
include_subdomains: bool = False
allow_external_links: bool = False
ignore_query_parameters: bool = True
max_concurrency: int = 4
delay_seconds: float = 0.0
```

### Pipeline

Target shape:

```text
input records
-> build seeds
-> map (optional)
-> crawl (optional)
-> fetch
-> extract
-> enrich
-> write
```

## Scoring

Scoring is required for queue ordering and debugging. Each candidate stores:

- final `score`
- `score_breakdown`

Typical score components:
- URL pattern confidence
- resource-type confidence
- domain trust
- anchor text relevance
- discovery source quality
- depth penalty
- duplicate penalty

## Migration Strategy

### Phase 1

- Introduce new discovery contracts and state model
- Add `generic` adapter with conservative map/crawl behavior
- Keep current fetch/extract runtime reusable

### Phase 2

- Move `wikipedia`, `amazon`, `linkedin` discovery logic into new discovery adapters
- Promote current LinkedIn search result extraction into `map()`
- Move template URL logic into `build_seed_records()`

### Phase 3

- Add new CLI commands and new pipeline entrypoints
- Persist frontier/visited/checkpoint state under discovery-specific stores
- Stop treating current `crawler/platforms/*` modules as the primary abstraction

### Phase 4

- Remove temporary compatibility paths once generic + platform adapters cover required use cases

## Testing Strategy

1. Unit tests for URL canonicalization and `url_key` generation
2. Unit tests for generic sitemap/link discovery
3. Unit tests for adapter candidate scoring
4. Unit tests for frontier/lease recovery
5. Integration tests for:
   - generic `discover-map`
   - generic `discover-crawl`
   - wikipedia adapter
   - amazon adapter
   - linkedin adapter with mocked authenticated fetch
6. Resume/restart tests using persisted checkpoints

## Risks

1. URL identity drift across adapters will break dedupe if `url_key` normalization is weak
2. Lease recovery bugs can create duplicate fetches or stuck frontier entries
3. Mixing `map` and `crawl` into one visited flag will cause false dedupe and missed work

## Open Decisions Fixed By This Design

- Use one discovery framework, not one skill per platform
- Support arbitrary webpages through a `generic` adapter
- Separate `Map` from `Crawl`
- Keep sessions outside discovery state
- Treat search/list pages as discovery surfaces, not always final records
- Prefer adapter-owned semantic logic and core-owned scheduling/state logic
