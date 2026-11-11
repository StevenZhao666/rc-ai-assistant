"""SQLite 数据层：建表 + 读取已发布条目。

设计要点（这是整个项目的骨架）：
- 一条知识 = 一条「断言」，不是一份文档
- status 状态机：draft → review → published → expired → archived
- 检索只吃 status='published' 且未过期的条目 —— 审核变成硬约束
"""
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS kb_item (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    category    TEXT,
    source      TEXT,              -- 来源说明，如《住宿规章》第 4.2 条
    source_url  TEXT,              -- 来源页面链接
    source_type TEXT DEFAULT 'unverified',  -- official / external / unverified
    note        TEXT,              -- 修改原因（来自 overrides.py）
    status      TEXT NOT NULL DEFAULT 'published',  -- draft/review/published/expired/archived
    ttl_type    TEXT NOT NULL DEFAULT 'A',          -- A 稳定 / B 年度 / C 实时
    audience    TEXT NOT NULL DEFAULT 'all',        -- freshmen/resident/all
    owner       TEXT,              -- 内容责任人
    reviewer    TEXT,              -- 审核人
    verified_at TEXT,              -- 最后核实日期
    valid_until TEXT,              -- 失效日期（可空）
    warnings    TEXT,              -- JSON 数组：自动检查发现的问题
    created_at  TEXT NOT NULL
);

-- L2 预留：官网页面切片（第一期先不填）
CREATE TABLE IF NOT EXISTS chunk (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    url        TEXT,
    title      TEXT,
    text       TEXT,
    status     TEXT DEFAULT 'draft',
    updated_at TEXT
);

-- 问答日志：用来找「答不了的问题」
CREATE TABLE IF NOT EXISTS qa_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT,
    student_id TEXT,
    question   TEXT,
    answer     TEXT,
    top_score  REAL,
    feedback   INTEGER
);

-- 用户反馈：👍/👎 + 可选说明。用来筛出要补/要改的条目
CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT,
    student_id TEXT,
    question   TEXT,
    answer     TEXT,
    vote       INTEGER,          -- 1 有用 / -1 没用
    note       TEXT,
    mode       TEXT
);
"""


def connect(write: bool = False) -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    if write:
        conn.executescript(SCHEMA)
    return conn


def init_db() -> None:
    with connect(write=True) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def published_items() -> list[dict]:
    """取出可被检索的条目：已发布 + 未过期。"""
    today = date.today().isoformat()
    sql = """
        SELECT * FROM kb_item
        WHERE status = 'published'
          AND (valid_until IS NULL OR valid_until = '' OR valid_until >= ?)
    """
    with connect() as conn:
        rows = conn.execute(sql, (today,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["warnings"] = json.loads(d.get("warnings") or "[]")
        except Exception:
            d["warnings"] = []
        out.append(d)
    return out


def log_qa(student_id: str, question: str, answer: str, top_score: float) -> None:
    with connect(write=True) as conn:
        conn.execute(
            "INSERT INTO qa_log (ts, student_id, question, answer, top_score) VALUES (?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), student_id, question, answer, top_score),
        )
        conn.commit()


def stats() -> dict:
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM kb_item").fetchone()[0]
        by_status = dict(conn.execute("SELECT status, COUNT(*) FROM kb_item GROUP BY status").fetchall())
        qa = conn.execute("SELECT COUNT(*) FROM qa_log").fetchone()[0]
        fb = dict(conn.execute("SELECT vote, COUNT(*) FROM feedback GROUP BY vote").fetchall())
    return {"items": total, "by_status": by_status, "qa_logs": qa, "feedback": fb}


def add_feedback(student_id: str, question: str, answer: str, vote: int,
                 note: str = "", mode: str = "") -> None:
    with connect(write=True) as conn:
        conn.execute(
            "INSERT INTO feedback (ts, student_id, question, answer, vote, note, mode) VALUES (?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), student_id, question, answer, vote, note, mode),
        )
        conn.commit()


def unanswered(limit: int = 30) -> list[dict]:
    """没答上来的问题：兜底最多、且没有正反馈的。这是「下一批要补的内容」清单。"""
    sql = """
        SELECT question, COUNT(*) AS times, MAX(ts) AS last_seen
        FROM qa_log
        WHERE answer LIKE '%没有找到确切答案%' OR answer LIKE '%资料里没有%'
        GROUP BY question
        ORDER BY times DESC, last_seen DESC
        LIMIT ?
    """
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]


def bad_feedback(limit: int = 30) -> list[dict]:
    """被点「没用」的问题，优先看这些。"""
    sql = """
        SELECT question, answer, note, ts FROM feedback
        WHERE vote = -1 ORDER BY ts DESC LIMIT ?
    """
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]
