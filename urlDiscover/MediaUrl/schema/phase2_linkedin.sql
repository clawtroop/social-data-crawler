-- Phase 2：前沿队列、关系边、页面元数据（轻量快照）
-- 依赖 phase1_linkedin.sql 已执行

-- ---------------------------------------------------------------------------
-- 采集前沿：待抓取 / 已完成 / 失败
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS linkedin_frontier (
    id                 BIGSERIAL PRIMARY KEY,
    canonical_url      TEXT NOT NULL UNIQUE,
    entity_type        TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'done', 'failed', 'skipped')),
    priority           INT  NOT NULL DEFAULT 0,
    depth              INT  NOT NULL DEFAULT 0,
    discovered_from_url TEXT NULL,
    seed_label         TEXT NULL,
    error_message      TEXT NULL,
    attempts           INT  NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_fetch_at      TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_frontier_status_prio
    ON linkedin_frontier (status, priority DESC, id);

COMMENT ON TABLE linkedin_frontier IS 'BFS/DFS 采集队列；canonical_url 去重';

-- ---------------------------------------------------------------------------
-- 关系边：从父页面 URL 发现子实体（来源追溯）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS linkedin_edge (
    id                   BIGSERIAL PRIMARY KEY,
    parent_canonical_url TEXT NOT NULL,
    child_canonical_url  TEXT NOT NULL,
    child_entity_type    TEXT NOT NULL,
    relation_hint        TEXT NOT NULL DEFAULT 'discovered',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_edge_parent_child UNIQUE (parent_canonical_url, child_canonical_url)
);

CREATE INDEX IF NOT EXISTS idx_edge_child ON linkedin_edge (child_canonical_url);
CREATE INDEX IF NOT EXISTS idx_edge_parent ON linkedin_edge (parent_canonical_url);

COMMENT ON TABLE linkedin_edge IS 'discover(url) 产边；与 extract 解耦';

-- ---------------------------------------------------------------------------
-- 轻量页面快照（标题 + 哈希，便于增量与排错）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS linkedin_page_snapshot (
    canonical_url   TEXT NOT NULL PRIMARY KEY,
    entity_type     TEXT NOT NULL,
    title           TEXT NULL,
    content_sha256  TEXT NOT NULL,
    html_bytes      INT  NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE linkedin_page_snapshot IS '每次抓取后更新；content_sha256 用于变更检测';
