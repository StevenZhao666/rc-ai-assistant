"""SQLite 数据层：建表 + 读取已发布条目。

设计要点（这是整个项目的骨架）：
- 一条知识 = 一条「断言」，不是一份文档
- status 状态机：draft → review → published → expired → archived
- 检索只吃 status='published' 且未过期的条目 —— 审核变成硬约束
"""
import json
import sqlite3
from datetime import date, datetime, timedelta
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
    original_answer TEXT,          -- 导入时的原文，供审核对照；之后不再改
    source_anchor TEXT,            -- 绑定的规章条款号，如 3.2
    created_at  TEXT NOT NULL
);

-- L2 预留：官网页面切片（第一期先不填）
CREATE TABLE IF NOT EXISTS chunk (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    url        TEXT,
    title      TEXT,
    text       TEXT,
    status     TEXT DEFAULT 'draft',
    updated_at TEXT,
    anchor     TEXT,              -- 条款号，如 4.2
    version    TEXT,              -- 规章版本，如 AY2026-2027
    source     TEXT,              -- 来源说明（文件名 + 哈希）
    section    TEXT,              -- 所属章节，用来区分同号条款
    variant    TEXT,              -- zh / en：同一条款的中英文各存一条
    hash       TEXT               -- 内容指纹，重复导入据此判重，避免同号条款互相覆盖
);

-- 问答日志：用来找「答不了的问题」
CREATE TABLE IF NOT EXISTS qa_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT,
    student_id TEXT,
    question   TEXT,
    answer     TEXT,
    top_score  REAL,
    feedback   INTEGER,
    mode       TEXT,              -- llm:xxx / basic / fallback_live / chat ...
    latency_ms INTEGER,           -- 端到端耗时
    session_id TEXT,              -- 同一设备的一串提问
    n_cites    INTEGER            -- 引用了几个来源
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

-- 审批留痕：谁、什么时候、把哪条、从什么改成什么
CREATE TABLE IF NOT EXISTS review_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    item_id  INTEGER,
    action   TEXT NOT NULL,      -- approve/reject/edit/create/expire
    reviewer TEXT,
    note     TEXT,
    before   TEXT,               -- JSON：改前快照
    after    TEXT                -- JSON：改后快照
);

-- 新资料候选：从官网抓回来的原始材料，还没变成问答条目
CREATE TABLE IF NOT EXISTS candidate (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    url        TEXT NOT NULL,
    title      TEXT,
    text       TEXT,
    source     TEXT,
    status     TEXT NOT NULL DEFAULT 'new',   -- new/accepted/rejected
    created_at TEXT,
    reviewer   TEXT,
    note       TEXT,
    item_id    INTEGER           -- 采纳后生成的 kb_item.id
);
"""

APPROVED_FIELDS = {
    "question", "answer", "category", "source", "source_url", "source_type",
    "note", "status", "ttl_type", "audience", "owner", "reviewer",
    "verified_at", "valid_until", "warnings", "locked_until", "version",
    "needs_recheck", "source_anchor", "source_chunk_id",
}

LOCK_MINUTES = 30


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
        _migrate(conn)
        conn.commit()


def _migrate(conn) -> None:
    """给老库补列（CREATE TABLE IF NOT EXISTS 不会改已存在的表）。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(kb_item)").fetchall()}
    for name, decl in (("owner", "TEXT"), ("locked_until", "TEXT"),
                       ("version", "INTEGER NOT NULL DEFAULT 1"),
                       ("needs_recheck", "INTEGER NOT NULL DEFAULT 0")):
        if name not in cols:
            conn.execute(f"ALTER TABLE kb_item ADD COLUMN {name} {decl}")

    kcols = {r[1] for r in conn.execute("PRAGMA table_info(kb_item)").fetchall()}
    if "source_anchor" not in kcols:
        conn.execute("ALTER TABLE kb_item ADD COLUMN source_anchor TEXT")
    if "source_chunk_id" not in kcols:
        conn.execute("ALTER TABLE kb_item ADD COLUMN source_chunk_id INTEGER")
    if "original_answer" not in kcols:
        conn.execute("ALTER TABLE kb_item ADD COLUMN original_answer TEXT")
        # 老条目：把当前答案当作原文留档，之后审核时能看出改了什么
        conn.execute("UPDATE kb_item SET original_answer = answer WHERE original_answer IS NULL")

    ccols = {r[1] for r in conn.execute("PRAGMA table_info(chunk)").fetchall()}
    for name, decl in (("anchor", "TEXT"), ("version", "TEXT"), ("source", "TEXT"), ("section", "TEXT"), ("variant", "TEXT"), ("hash", "TEXT")):
        if name not in ccols:
            conn.execute(f"ALTER TABLE chunk ADD COLUMN {name} {decl}")

    qcols = {r[1] for r in conn.execute("PRAGMA table_info(qa_log)").fetchall()}
    for name, decl in (("mode", "TEXT"), ("latency_ms", "INTEGER"),
                       ("session_id", "TEXT"), ("n_cites", "INTEGER")):
        if name not in qcols:
            conn.execute(f"ALTER TABLE qa_log ADD COLUMN {name} {decl}")


def list_clauses(limit: int = 500) -> list[dict]:
    """所有已入库的规章条款，供审核端下拉选择绑定。"""
    with connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, anchor, version, text, source, section FROM chunk WHERE status='published'"
            " ORDER BY id LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["preview"] = (d["text"] or "")[:80]
        d.pop("text", None)
        out.append(d)
    return out


def get_clause(anchor: str, version: str = "") -> dict | None:
    """按条款号取原文；同一号有中英两条时全部返回。"""
    if not anchor:
        return None
    with connect() as conn:
        conn.row_factory = sqlite3.Row
        sql = "SELECT anchor, version, text, source FROM chunk WHERE anchor = ? AND status='published'"
        args = [anchor]
        if version:
            sql += " AND version = ?"
            args.append(version)
        rows = [dict(r) for r in conn.execute(sql, tuple(args)).fetchall()]
    return rows[0] if rows else None


def get_clause_by_id(chunk_id: int) -> dict | None:
    """精确绑定：直接指向一条原文，不受同号条款干扰。"""
    if not chunk_id:
        return None
    with connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, anchor, version, text, source, section FROM chunk WHERE id = ?",
            (chunk_id,)).fetchone()
    return dict(row) if row else None


def get_clauses(anchor: str, version: str = "") -> list[dict]:
    if not anchor:
        return []
    with connect() as conn:
        conn.row_factory = sqlite3.Row
        sql = "SELECT anchor, version, text, source FROM chunk WHERE anchor = ? AND status='published'"
        args = [anchor]
        if version:
            sql += " AND version = ?"
            args.append(version)
        return [dict(r) for r in conn.execute(sql, tuple(args)).fetchall()]


def find_chunk(url: str) -> dict | None:
    """按来源 URL 找抓到的页面原文，供审核对照。没有就返回 None。"""
    if not url:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT id, url, title, text, updated_at FROM chunk WHERE url = ? ORDER BY id DESC LIMIT 1",
            (url,)).fetchone()
    return dict(row) if row else None




# 规章是双语的（有的条款只有英文），中文提问要能对上英文条款。
# 这不是翻译，只是一张常用词对照表；不够用时往里加。
_ZH_EN = {
    "宠物": ["pet", "animal"], "養寵物": ["pet"], "养宠物": ["pet"],
    "訪客": ["visitor", "guest"], "访客": ["visitor", "guest"], "過夜": ["overnight", "stay"],
    "过夜": ["overnight"], "換房": ["change of room", "room change"], "换房": ["room"],
    "吸煙": ["smoking", "smoke"], "吸烟": ["smoking"], "清潔": ["cleaning", "clean"],
    "清洁": ["cleaning"], "電器": ["appliance", "electrical"], "电器": ["appliance"],
    "門禁": ["curfew", "access"], "门禁": ["curfew"], "押金": ["deposit"],
    "退宿": ["check-out", "checkout", "vacate", "leave"], "訪客登記": ["registration"], "噪音": ["noise"],
    "安静": ["noise", "quiet"], "廚房": ["kitchen"], "厨房": ["kitchen"],
    "洗衣": ["laundry"], "維修": ["repair", "maintenance"], "维修": ["repair"],
    "違規": ["violation", "breach"], "违规": ["violation"], "處分": ["disciplinary", "penalty"],
    "处分": ["disciplinary"], "膳食": ["meal"], "饭堂": ["canteen", "dining"],
    "火警": ["fire"], "演習": ["drill"], "演习": ["drill"], "行李": ["luggage"],
    "室友": ["roommate"], "暑期": ["summer"], "續住": ["renew", "extension"],
    "续住": ["renew"], "學生證": ["student card"], "学生证": ["student card"],
}

# 这些词组在任何条款里都有，拿它们算相关等于没算
_STOP = {"書院", "书院", "大學", "大学", "學生", "学生", "可以", "什麼", "什么", "怎麼", "怎么",
         "請問", "请问", "如何", "我們", "我们", "是否", "需要", "規定", "规定", "問題", "问题",
         "澳門", "澳门", "香港", "內地", "内地", "論壇", "论坛", "網站", "网站"}

_BIGRAM = lambda t: {t[i:i + 2] for i in range(len(t) - 1)}


def _tokens(text: str) -> set[str]:
    """中文取二元组，英文取小写词；够用且不用分词库。"""
    import re as _re
    text = (text or "").lower()
    zh = "".join(ch for ch in text if "一" <= ch <= "鿿")
    en = set(_re.findall(r"[a-z]{3,}", text))
    return (_BIGRAM(zh) if len(zh) > 1 else set()) | en


def related_chunks(question: str, answer: str = "", limit: int = 3, min_score: float = 0.0) -> list[dict]:
    """按词面重合找最相关的规章原文段落，给审核对照用。"""
    q = (_tokens(question) | _tokens(answer)) - _STOP
    # 中文问句补上英文关键词，才能对上英文条款
    strong: set[str] = set()
    for zh, ens in _ZH_EN.items():
        if zh in (question or "") or zh in (answer or ""):
            strong.update(e.lower() for e in ens)
    q |= strong
    if not q:
        return []
    with connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(
            "SELECT id, anchor, version, text, source, url FROM chunk WHERE status='published'").fetchall()]
    # 去掉「到处都是」的词：某词若在超过 12% 的条款里出现，它对区分没有帮助
    corpus = [_tokens(r["text"]) for r in rows]
    df: dict[str, int] = {}
    for toks in corpus:
        for w in toks:
            df[w] = df.get(w, 0) + 1
    limit_df = max(3, int(len(rows) * 0.12))
    q = {w for w in q if df.get(w, 0) <= limit_df}
    if not q:
        return []
    strong &= q

    scored = []
    for toks, r in zip(corpus, rows):
        t = toks
        if not t:
            continue
        hit = len(q & t)
        # 命中常用词对照表里的词，一条也算相关（规章有的条款只有英文）
        if hit >= 2 or (strong & t):
            scored.append((hit, hit / (len(q) ** 0.5), r))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    out = []
    for hit, ratio, r in scored[:limit]:
        r["score"] = round(ratio, 2)
        r["text"] = (r["text"] or "")[:400]
        out.append(r)
    return out


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


def log_qa(student_id: str, question: str, answer: str, top_score: float,
           mode: str = "", latency_ms: int = 0, session_id: str = "", n_cites: int = 0) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    with connect(write=True) as conn:
        conn.execute(
            "INSERT INTO qa_log (ts, student_id, question, answer, top_score, mode, latency_ms, session_id, n_cites)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (ts, student_id, question, answer, top_score, mode, latency_ms, session_id, n_cites),
        )
        conn.commit()
    # 同时写一份 append-only 的流水：库被删/重建也不影响这份记录
    try:
        with (config.DATA_DIR / "qa_log.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": ts, "who": student_id, "q": question,
                                "score": round(top_score, 2), "len": len(answer or "")},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass


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


# ── 审批相关 ────────────────────────────────────────────────────────

def list_items(status: str | None = None, q: str = "", limit: int = 300) -> list[dict]:
    sql = "SELECT * FROM kb_item WHERE 1=1"
    args: list = []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if q:
        sql += " AND (question LIKE ? OR answer LIKE ? OR category LIKE ?)"
        args += [f"%{q}%"] * 3
    sql += " ORDER BY CASE status WHEN 'review' THEN 0 WHEN 'draft' THEN 1 WHEN 'published' THEN 2 ELSE 3 END, id"
    sql += " LIMIT ?"
    args.append(limit)
    with connect() as conn:
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    for d in rows:
        try:
            d["warnings"] = json.loads(d.get("warnings") or "[]")
        except Exception:
            d["warnings"] = []
    return rows


def get_item(item_id: int) -> dict | None:
    with connect() as conn:
        r = conn.execute("SELECT * FROM kb_item WHERE id = ?", (item_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["warnings"] = json.loads(d.get("warnings") or "[]")
    except Exception:
        d["warnings"] = []
    return d


def update_item(item_id: int, patch: dict) -> dict | None:
    """只允许改白名单字段；回来后返回新快照。"""
    fields = {k: v for k, v in patch.items() if k in APPROVED_FIELDS}
    if not fields:
        return get_item(item_id)
    if isinstance(fields.get("warnings"), (list, dict)):
        fields["warnings"] = json.dumps(fields["warnings"], ensure_ascii=False)
    sets = ", ".join(f"{k} = ?" for k in fields)
    with connect(write=True) as conn:
        conn.execute(f"UPDATE kb_item SET {sets} WHERE id = ?", (*fields.values(), item_id))
        conn.commit()
    return get_item(item_id)


def create_item(fields: dict) -> int:
    data = {k: v for k, v in fields.items() if k in APPROVED_FIELDS}
    data.setdefault("status", "review")
    data.setdefault("ttl_type", "A")
    data.setdefault("audience", "all")
    data.setdefault("source_type", "official")
    data.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    data.setdefault("original_answer", data.get("answer") or "")
    cols = ", ".join(data)
    marks = ", ".join("?" * len(data))
    with connect(write=True) as conn:
        cur = conn.execute(f"INSERT INTO kb_item ({cols}) VALUES ({marks})", tuple(data.values()))
        conn.commit()
        return int(cur.lastrowid)


def log_review(item_id: int | None, action: str, reviewer: str, note: str = "",
               before: dict | None = None, after: dict | None = None) -> None:
    with connect(write=True) as conn:
        conn.execute(
            "INSERT INTO review_log (ts, item_id, action, reviewer, note, before, after)"
            " VALUES (?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), item_id, action, reviewer, note,
             json.dumps(before, ensure_ascii=False) if before else None,
             json.dumps(after, ensure_ascii=False) if after else None),
        )
        conn.commit()


def item_history(item_id: int, limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM review_log WHERE item_id = ? ORDER BY id DESC LIMIT ?",
            (item_id, limit),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("before", "after"):
            try:
                d[k] = json.loads(d[k]) if d[k] else None
            except Exception:
                d[k] = None
        out.append(d)
    return out


def recent_log(limit: int = 20) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, ts, item_id, action, reviewer, note FROM review_log ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()]


def add_candidate(url: str, title: str, text: str, source: str = "") -> int:
    with connect(write=True) as conn:
        cur = conn.execute(
            "INSERT INTO candidate (url, title, text, source, status, created_at)"
            " VALUES (?,?,?,?, 'new', ?)",
            (url, title, text, source, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_candidates(status: str | None = None, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM candidate"
    args: list = []
    if status:
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def get_candidate(cid: int) -> dict | None:
    with connect() as conn:
        r = conn.execute("SELECT * FROM candidate WHERE id = ?", (cid,)).fetchone()
    return dict(r) if r else None


def decide_candidate(cid: int, status: str, reviewer: str,
                     note: str = "", item_id: int | None = None) -> None:
    with connect(write=True) as conn:
        conn.execute(
            "UPDATE candidate SET status = ?, reviewer = ?, note = ?, item_id = ? WHERE id = ?",
            (status, reviewer, note, item_id, cid),
        )
        conn.commit()


def review_stats() -> dict:
    with connect() as conn:
        by_status = dict(conn.execute(
            "SELECT status, COUNT(*) FROM kb_item GROUP BY status").fetchall())
        cand = dict(conn.execute(
            "SELECT status, COUNT(*) FROM candidate GROUP BY status").fetchall())
        logs = conn.execute("SELECT COUNT(*) FROM review_log").fetchone()[0]
        recheck = conn.execute(
            "SELECT COUNT(*) FROM kb_item WHERE status='published' AND needs_recheck=1").fetchone()[0]
    return {"by_status": by_status, "candidates": cand, "review_logs": logs, "recheck": recheck}


def mark_recheck_all() -> int:
    """把现有已发布条目全部标成「待复核」——不影响检索，只是排队等人看一遍。"""
    with connect(write=True) as conn:
        cur = conn.execute(
            "UPDATE kb_item SET needs_recheck = 1 WHERE status = 'published'")
        conn.commit()
        return cur.rowcount


def list_recheck(limit: int = 500) -> list[dict]:
    """待复核队列，按风险排序：有告警 > 非官方来源 > 年度型 > 其他旧条目。"""
    sql = """
        SELECT * FROM kb_item
        WHERE status = 'published' AND needs_recheck = 1
        ORDER BY
          CASE WHEN warnings IS NOT NULL AND warnings NOT IN ('', '[]') THEN 0 ELSE 1 END,
          CASE WHEN source_type IS NULL OR source_type != 'official' THEN 0 ELSE 1 END,
          CASE WHEN ttl_type = 'B' THEN 0 ELSE 1 END,
          id
        LIMIT ?
    """
    with connect() as conn:
        rows = [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]
    for d in rows:
        try:
            d["warnings"] = json.loads(d.get("warnings") or "[]")
        except Exception:
            d["warnings"] = []
    return rows


def claim_item(item_id: int, reviewer: str) -> tuple[bool, dict | None]:
    """认领：锁 30 分钟。别人正在改的条目抢不到，避免两个人同时动同一条。"""
    now = datetime.now().isoformat(timespec="seconds")
    until = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds")
    with connect(write=True) as conn:
        cur = conn.execute(
            "UPDATE kb_item SET owner = ?, locked_until = ? WHERE id = ?"
            " AND (locked_until IS NULL OR locked_until < ? OR owner = ? OR owner IS NULL)",
            (reviewer, until, item_id, now, reviewer),
        )
        conn.commit()
        ok = cur.rowcount > 0
    return ok, get_item(item_id)


def release_item(item_id: int, reviewer: str) -> None:
    with connect(write=True) as conn:
        conn.execute(
            "UPDATE kb_item SET owner = NULL, locked_until = NULL WHERE id = ? AND owner = ?",
            (item_id, reviewer),
        )
        conn.commit()


def decide_item(item_id: int, action: str, reviewer: str, note: str = "",
                patch: dict | None = None, version: int | None = None
                ) -> tuple[bool, str, dict | None]:
    """审批动作。version 对不上就拒绝，防止覆盖别人刚做的修改。"""
    item = get_item(item_id)
    if not item:
        return False, "not_found", None
    cur_ver = int(item.get("version") or 1)
    if version is not None and int(version) != cur_ver:
        return False, "conflict", item

    fields = dict(patch or {})
    if action == "approve":
        fields.update(status="published", verified_at=date.today().isoformat(),
                      reviewer=reviewer, needs_recheck=0)
    elif action == "verify":
        # 复核通过：条目本来就在线上，只清标记、记核实日期
        fields.update(verified_at=date.today().isoformat(), reviewer=reviewer, needs_recheck=0)
    elif action == "reject":
        fields.update(status="draft")
    elif action == "archive":
        fields.update(status="archived")
    elif action == "edit":
        pass
    else:
        return False, "bad_action", item

    fields["version"] = cur_ver + 1
    fields["locked_until"] = None
    after = update_item(item_id, fields)
    log_review(item_id, action, reviewer, note, before=item, after=after)
    return True, "ok", after
