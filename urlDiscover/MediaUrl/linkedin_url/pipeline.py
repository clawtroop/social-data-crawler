"""
Phase 2：种子入队 → 带会话抓取 → discover 新链接 → 归一化 → 写边与前沿扩展。

与 extract 解耦：此处只写入 linkedin_page_snapshot 的轻量元数据；
细粒度字段见 extract.extract_page_metadata。
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from linkedin_url.auth.paths import default_storage_state_path
from linkedin_url.discover import discover_from_html
from linkedin_url.extract import extract_page_metadata
from linkedin_url.models import LinkedInEntityType, NormalizeResult
from linkedin_url.normalize import normalize_linkedin_url
from linkedin_url.parser import normalize_result_to_entity_upsert, normalize_result_to_observation_row

logger = logging.getLogger(__name__)


@dataclass
class CrawlConfig:
    max_depth: int = 2
    max_steps: int = 10
    seed_label: str = "pipeline"
    state_path: Path | None = None
    proxy: str | None = None


def _upsert_entity(cur, result: NormalizeResult) -> None:
    row = normalize_result_to_entity_upsert(result)
    if row is None:
        return
    table, d = row
    if table == "linkedin_profile":
        cur.execute(
            """
            INSERT INTO linkedin_profile (profile_vanity, canonical_url, last_seen_at)
            VALUES (%(profile_vanity)s, %(canonical_url)s, now())
            ON CONFLICT (profile_vanity) DO UPDATE SET
              canonical_url = EXCLUDED.canonical_url,
              last_seen_at = now()
            """,
            d,
        )
    elif table == "linkedin_company":
        cur.execute(
            """
            INSERT INTO linkedin_company (company_vanity, canonical_url, last_seen_at)
            VALUES (%(company_vanity)s, %(canonical_url)s, now())
            ON CONFLICT (company_vanity) DO UPDATE SET
              canonical_url = EXCLUDED.canonical_url,
              last_seen_at = now()
            """,
            d,
        )
    elif table == "linkedin_job":
        cur.execute(
            """
            INSERT INTO linkedin_job (job_id, canonical_url, last_seen_at)
            VALUES (%(job_id)s, %(canonical_url)s, now())
            ON CONFLICT (job_id) DO UPDATE SET
              canonical_url = EXCLUDED.canonical_url,
              last_seen_at = now()
            """,
            d,
        )
    elif table == "linkedin_post":
        cur.execute(
            """
            INSERT INTO linkedin_post (activity_id, canonical_url, last_seen_at)
            VALUES (%(activity_id)s, %(canonical_url)s, now())
            ON CONFLICT (activity_id) DO UPDATE SET
              canonical_url = EXCLUDED.canonical_url,
              last_seen_at = now()
            """,
            d,
        )


def _insert_observation(cur, result: NormalizeResult, source_label: str | None) -> None:
    obs = normalize_result_to_observation_row(result, source_label=source_label)
    cur.execute(
        """
        INSERT INTO linkedin_url_observation
          (raw_url, normalized_url, entity_type, profile_vanity, company_vanity, job_id, activity_id, source_label)
        VALUES
          (%(raw_url)s, %(normalized_url)s, %(entity_type)s, %(profile_vanity)s, %(company_vanity)s,
           %(job_id)s, %(activity_id)s, %(source_label)s)
        """,
        obs,
    )


def enqueue_seed(
    cur,
    url: str,
    *,
    seed_label: str = "seed",
    depth: int = 0,
    discovered_from_url: str | None = None,
    priority: int = 0,
) -> dict[str, Any]:
    """
    归一化 URL，写入实体表 + frontier(pending)。UNKNOWN 仅记 observation，不入队。
    返回摘要 dict。
    """
    raw = url.strip()
    result = normalize_linkedin_url(raw)
    _insert_observation(cur, result, source_label=seed_label)

    if result.entity_type == LinkedInEntityType.UNKNOWN:
        return {"ok": False, "reason": "unknown_url", "original": raw}

    _upsert_entity(cur, result)
    cur.execute(
        """
        INSERT INTO linkedin_frontier
          (canonical_url, entity_type, status, priority, depth, discovered_from_url, seed_label)
        VALUES
          (%s, %s, 'pending', %s, %s, %s, %s)
        ON CONFLICT (canonical_url) DO UPDATE SET
          seed_label = COALESCE(EXCLUDED.seed_label, linkedin_frontier.seed_label),
          priority = GREATEST(linkedin_frontier.priority, EXCLUDED.priority),
          updated_at = now()
        RETURNING id
        """,
        (
            result.canonical_url,
            result.entity_type.value,
            priority,
            depth,
            discovered_from_url,
            seed_label,
        ),
    )
    row = cur.fetchone()
    return {
        "ok": True,
        "canonical_url": result.canonical_url,
        "entity_type": result.entity_type.value,
        "frontier_id": row[0] if row else None,
    }


def _fetch_html_factory(
    cfg: CrawlConfig,
) -> Callable[[str], str]:
    from linkedin_url.auth.fetch import fetch_html_sync

    state = cfg.state_path or default_storage_state_path()

    def _fetch(u: str) -> str:
        return fetch_html_sync(u, state_path=state, proxy=cfg.proxy)

    return _fetch


def process_one_frontier(
    cur,
    row: tuple[Any, ...],
    *,
    fetch_html: Callable[[str], str],
    cfg: CrawlConfig,
) -> None:
    """
    row: (id, canonical_url, entity_type, depth, discovered_from_url)
    """
    fid, canonical_url, _etype, depth, _from = row
    cur.execute(
        "UPDATE linkedin_frontier SET status = 'processing', attempts = attempts + 1, updated_at = now() WHERE id = %s",
        (fid,),
    )
    try:
        html = fetch_html(canonical_url)
    except Exception as e:
        logger.exception("fetch failed: %s", canonical_url)
        cur.execute(
            """
            UPDATE linkedin_frontier
            SET status = 'failed', error_message = %s, updated_at = now()
            WHERE id = %s
            """,
            (str(e)[:2000], fid),
        )
        return

    meta = extract_page_metadata(html)
    h = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
    cur.execute(
        """
        INSERT INTO linkedin_page_snapshot (canonical_url, entity_type, title, content_sha256, html_bytes, fetched_at)
        VALUES (%s, %s, %s, %s, %s, now())
        ON CONFLICT (canonical_url) DO UPDATE SET
          title = EXCLUDED.title,
          content_sha256 = EXCLUDED.content_sha256,
          html_bytes = EXCLUDED.html_bytes,
          fetched_at = now()
        """,
        (canonical_url, _etype, meta.get("title"), h, len(html.encode("utf-8", errors="replace"))),
    )

    raw_links = discover_from_html(html, base_url=canonical_url)
    for raw in raw_links:
        child = normalize_linkedin_url(raw)
        _insert_observation(cur, child, source_label=f"discover:{canonical_url[:80]}")

        if child.entity_type == LinkedInEntityType.UNKNOWN:
            continue

        _upsert_entity(cur, child)
        cur.execute(
            """
            INSERT INTO linkedin_edge (parent_canonical_url, child_canonical_url, child_entity_type, relation_hint)
            VALUES (%s, %s, %s, 'discovered')
            ON CONFLICT (parent_canonical_url, child_canonical_url) DO NOTHING
            """,
            (canonical_url, child.canonical_url, child.entity_type.value),
        )

        if depth + 1 > cfg.max_depth:
            continue

        cur.execute(
            """
            INSERT INTO linkedin_frontier
              (canonical_url, entity_type, status, priority, depth, discovered_from_url, seed_label)
            VALUES
              (%s, %s, 'pending', 0, %s, %s, %s)
            ON CONFLICT (canonical_url) DO NOTHING
            """,
            (
                child.canonical_url,
                child.entity_type.value,
                depth + 1,
                canonical_url,
                cfg.seed_label,
            ),
        )

    cur.execute(
        """
        UPDATE linkedin_frontier
        SET status = 'done', last_fetch_at = now(), updated_at = now(), error_message = NULL
        WHERE id = %s
        """,
        (fid,),
    )


def fetch_next_pending(cur) -> tuple[Any, ...] | None:
    cur.execute(
        """
        SELECT id, canonical_url, entity_type, depth, discovered_from_url
        FROM linkedin_frontier
        WHERE status = 'pending'
        ORDER BY priority DESC, id ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
        """
    )
    r = cur.fetchone()
    return r


def run_crawl(
    conn,
    cfg: CrawlConfig,
    *,
    fetch_html: Callable[[str], str] | None = None,
) -> int:
    """
    处理 frontier 直至 max_steps。返回本轮实际处理条数。
    """
    fetcher = fetch_html or _fetch_html_factory(cfg)
    done = 0
    for _ in range(cfg.max_steps):
        with conn.transaction():
            with conn.cursor() as cur:
                row = fetch_next_pending(cur)
                if not row:
                    return done
                process_one_frontier(cur, row, fetch_html=fetcher, cfg=cfg)
        done += 1
    return done
