-- Phase 1：LinkedIn 四类实体基础表 + URL 归一主键
-- PostgreSQL 12+

-- ---------------------------------------------------------------------------
-- Profile: 主键 profile_vanity（与 canonical URL 一一对应）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS linkedin_profile (
    profile_vanity TEXT NOT NULL PRIMARY KEY,
    canonical_url  TEXT NOT NULL UNIQUE,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE linkedin_profile IS '个人主页 https://www.linkedin.com/in/{vanity}/';

-- ---------------------------------------------------------------------------
-- Company: 主键 company_vanity
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS linkedin_company (
    company_vanity TEXT NOT NULL PRIMARY KEY,
    canonical_url  TEXT NOT NULL UNIQUE,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE linkedin_company IS '公司页 https://www.linkedin.com/company/{companyVanity}/';

-- ---------------------------------------------------------------------------
-- Job: 主键 job_id（文本存数字 ID，与 LinkedIn 一致）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS linkedin_job (
    job_id         TEXT NOT NULL PRIMARY KEY,
    canonical_url  TEXT NOT NULL UNIQUE,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE linkedin_job IS '职位页 https://www.linkedin.com/jobs/view/{jobId}/';

-- ---------------------------------------------------------------------------
-- Post: 主键 activity_id（urn:li:activity 的数字段）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS linkedin_post (
    activity_id    TEXT NOT NULL PRIMARY KEY,
    canonical_url  TEXT NOT NULL UNIQUE,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE linkedin_post IS '动态 https://www.linkedin.com/feed/update/urn:li:activity:{activityId}/';

-- ---------------------------------------------------------------------------
-- 可选：原始 URL 观测（便于审计 posts/ 与 feed 双形式、短链展开后回填）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS linkedin_url_observation (
    id             BIGSERIAL PRIMARY KEY,
    raw_url        TEXT NOT NULL,
    normalized_url TEXT,
    entity_type    TEXT,
    profile_vanity TEXT,
    company_vanity TEXT,
    job_id         TEXT,
    activity_id    TEXT,
    source_label   TEXT,
    observed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_url_obs_raw ON linkedin_url_observation (raw_url);
CREATE INDEX IF NOT EXISTS idx_url_obs_activity ON linkedin_url_observation (activity_id)
    WHERE activity_id IS NOT NULL;

COMMENT ON TABLE linkedin_url_observation IS '种子来源原始 URL 与规范化结果对照（可选）';
