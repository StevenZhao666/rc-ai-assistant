-- 书院数据库 · 结构 v1（SQLite 版，用于本地验证）
-- 设计说明见 docs/数据库结构设计-v1.md
-- 迁到 PostgreSQL 时：TEXT 时间字段改 timestamptz，enum 改 CHECK 或独立类型，
-- 检索列 search_text 改 tsvector + 触发器，其余结构不变。

PRAGMA foreign_keys = ON;

-- ── 1. 统一基表 ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resource (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    type          TEXT NOT NULL CHECK (type IN ('doc','qa','work','link')),
    title         TEXT NOT NULL,
    summary       TEXT,
    status        TEXT NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','review','published','deprecated','archived')),
    visibility    TEXT NOT NULL DEFAULT 'public'
                  CHECK (visibility IN ('public','student','college','admin')),
    lang          TEXT DEFAULT 'zh-Hant',
    owner         TEXT,
    reviewer      TEXT,
    source_kind   TEXT DEFAULT 'official'
                  CHECK (source_kind IN ('official','student','external','unverified')),
    source_channel TEXT DEFAULT 'manual'
                  CHECK (source_channel IN ('manual','api','crawl','import','forum')),
    contact_public INTEGER NOT NULL DEFAULT 0,   -- 仅 work 用：作者是否公开联系方式
    published_at  TEXT,
    updated_at    TEXT,
    review_due    TEXT,        -- 下次必须复核的日期
    valid_from    TEXT,
    valid_until   TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_resource_type_status ON resource(type, status);
CREATE INDEX IF NOT EXISTS idx_resource_visibility ON resource(visibility, status);

-- ── 2. 公文 ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doc (
    resource_id   INTEGER PRIMARY KEY REFERENCES resource(id) ON DELETE CASCADE,
    doc_no        TEXT,                          -- CKLC/R0001/2020
    issuer        TEXT,                          -- 发布机构
    doc_type      TEXT CHECK (doc_type IN ('regulation','notice','guideline','form','minutes')),
    current_version_id INTEGER,                  -- 指向 doc_version
    file_url      TEXT,
    file_hash     TEXT
);

CREATE TABLE IF NOT EXISTS doc_version (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id        INTEGER NOT NULL REFERENCES doc(resource_id) ON DELETE CASCADE,
    version       TEXT NOT NULL,                 -- AY2026-2027 / v3
    issued_at     TEXT,
    effective_from TEXT,
    effective_until TEXT,
    storage_path  TEXT,                          -- 相对 /opt/rc-ai/files
    file_url      TEXT,
    file_hash     TEXT,
    supersedes    INTEGER REFERENCES doc_version(id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (doc_id, version)
);

CREATE TABLE IF NOT EXISTS clause (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_version_id INTEGER NOT NULL REFERENCES doc_version(id) ON DELETE CASCADE,
    anchor         TEXT NOT NULL,                -- 3.2
    section        TEXT,                         -- 3. Visitors
    variant        TEXT DEFAULT 'zh' CHECK (variant IN ('zh','en')),
    text           TEXT NOT NULL,
    sort_key       TEXT,                         -- 3.02 之类，避免 3.10 < 3.2
    UNIQUE (doc_version_id, anchor, variant)
);
CREATE INDEX IF NOT EXISTS idx_clause_anchor ON clause(anchor);

-- ── 3. 条目 ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS qa (
    resource_id    INTEGER PRIMARY KEY REFERENCES resource(id) ON DELETE CASCADE,
    question       TEXT NOT NULL,
    answer         TEXT NOT NULL,
    original_answer TEXT,                        -- 导入原文，之后不改
    ttl_type       TEXT NOT NULL DEFAULT 'A' CHECK (ttl_type IN ('A','B','C')),
    audience       TEXT DEFAULT 'all' CHECK (audience IN ('all','freshman','resident')),
    category       TEXT
);

CREATE TABLE IF NOT EXISTS qa_clause (
    qa_id      INTEGER NOT NULL REFERENCES qa(resource_id) ON DELETE CASCADE,
    clause_id  INTEGER NOT NULL REFERENCES clause(id) ON DELETE CASCADE,
    strength   TEXT NOT NULL DEFAULT 'direct'
               CHECK (strength IN ('direct','explain','ref')),
    note       TEXT,
    PRIMARY KEY (qa_id, clause_id)
);

-- ── 4. 院生作品 ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS work (
    resource_id   INTEGER PRIMARY KEY REFERENCES resource(id) ON DELETE CASCADE,
    author_id     TEXT,                          -- 学号（不对外）
    author_name   TEXT,                          -- 对外显示的名字
    work_type     TEXT CHECK (work_type IN ('skill','tool','app','art','paper','dataset')),
    summary       TEXT,
    usage         TEXT,
    repo_url      TEXT,
    demo_url      TEXT,
    license       TEXT,
    tech          TEXT,                          -- 逗号分隔的标签
    cover_url     TEXT,
    consent       TEXT NOT NULL DEFAULT 'no' CHECK (consent IN ('yes','anon','no')),
    contact       TEXT,
    contact_public INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS work_file (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id      INTEGER NOT NULL REFERENCES work(resource_id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    file_url     TEXT,
    mime         TEXT,
    size_bytes   INTEGER,
    file_hash    TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── 5. 其他资源 ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS link (
    resource_id  INTEGER PRIMARY KEY REFERENCES resource(id) ON DELETE CASCADE,
    url          TEXT NOT NULL,
    link_type    TEXT CHECK (link_type IN ('official','student','tool','club','doc')),
    is_official  INTEGER NOT NULL DEFAULT 0,
    lang         TEXT,
    description  TEXT,
    recommended_by TEXT,
    risk         TEXT DEFAULT 'none'
                 CHECK (risk IN ('none','login-required','ads','unofficial','dead'))
);

CREATE TABLE IF NOT EXISTS link_check (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id     INTEGER NOT NULL REFERENCES link(resource_id) ON DELETE CASCADE,
    checked_at  TEXT NOT NULL DEFAULT (datetime('now')),
    http_status INTEGER,
    final_url   TEXT,
    note        TEXT
);

-- ── 6. 公共表 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tag (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    kind  TEXT
);

CREATE TABLE IF NOT EXISTS resource_tag (
    resource_id INTEGER NOT NULL REFERENCES resource(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
    PRIMARY KEY (resource_id, tag_id)
);

CREATE TABLE IF NOT EXISTS review_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER REFERENCES resource(id) ON DELETE SET NULL,
    ts          TEXT NOT NULL DEFAULT (datetime('now')),
    action      TEXT NOT NULL,       -- create/edit/approve/reject/bind/autobind/archive/restore
    reviewer    TEXT,
    note        TEXT,
    before      TEXT,
    after       TEXT
);
CREATE INDEX IF NOT EXISTS idx_review_resource ON review_log(resource_id);

CREATE TABLE IF NOT EXISTS change_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER REFERENCES resource(id) ON DELETE SET NULL,
    ts          TEXT NOT NULL DEFAULT (datetime('now')),
    field       TEXT,
    old_value   TEXT,
    new_value   TEXT,
    actor       TEXT
);

CREATE TABLE IF NOT EXISTS client (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    kind          TEXT CHECK (kind IN ('internal','student','partner','trial')),
    key_hash      TEXT NOT NULL,                 -- 只存哈希，不存明文
    scope         TEXT NOT NULL DEFAULT 'read' CHECK (scope IN ('read','submit')),
    quota_per_hour INTEGER DEFAULT 60,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_used_at  TEXT,
    revoked_at    TEXT
);

CREATE TABLE IF NOT EXISTS api_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL DEFAULT (datetime('now')),
    client_id   INTEGER REFERENCES client(id) ON DELETE SET NULL,
    endpoint    TEXT,
    query       TEXT,
    result_ids  TEXT,
    status      INTEGER,
    latency_ms  INTEGER,
    ip          TEXT
);

CREATE TABLE IF NOT EXISTS glossary (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    term    TEXT NOT NULL UNIQUE,
    aliases TEXT,
    meaning TEXT NOT NULL
);

-- 迁移期用：老 id ↔ 新 id
CREATE TABLE IF NOT EXISTS legacy_map (
    old_table TEXT NOT NULL,
    old_id    INTEGER NOT NULL,
    new_id    INTEGER NOT NULL,
    new_type  TEXT,
    PRIMARY KEY (old_table, old_id)
);

-- ── 7. 兼容视图：崑崑现有查询先不用改 ─────────────────────
CREATE VIEW IF NOT EXISTS v_qa AS
SELECT r.id, q.question, q.answer, r.status,
       q.original_answer, q.ttl_type, q.audience, q.category,
       r.source_kind, r.updated_at, r.valid_until
FROM resource r JOIN qa q ON q.resource_id = r.id;
