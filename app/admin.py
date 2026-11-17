"""后台数据看板接口（只读）。

设计取舍：
- 只读，不在这里改数据；审批仍在 review.py
- 学号默认脱敏（uc12***），管理员名单里的人看全号
- 老数据没有 mode / latency_ms / session_id，全部按 NULL 兼容，不假装有值
"""
from __future__ import annotations

import json
import os
import platform
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from . import config, db

router = APIRouter(prefix="/api/admin")

# 大致单价（元 / 百万 token），只用来给个量级；免费档记 0
PRICES = {
    "glm-4": (0.0, 0.0),
    "deepseek-chat": (1.0, 2.0),
    "deepseek-flash": (0.5, 2.0),
}

_MODES = ("llm", "basic", "fallback", "policy", "chat")


def _admin(request: Request) -> str:
    who = (request.headers.get("X-Admin") or request.headers.get("X-Student-Id")
           or request.headers.get("X-Reviewer") or "").strip()
    if not who:
        raise HTTPException(401, "需要管理员身份：请求头带 X-Admin（或页面顶部填学号）")
    allowed = config.ADMINS or config.REVIEWERS
    if allowed and who not in allowed:
        raise HTTPException(403, f"{who} 不在管理员名单里")
    return who


def _mask(sid: str | None, full: bool) -> str:
    sid = (sid or "").strip()
    if not sid:
        return "匿名"
    if full or len(sid) <= 4:
        return sid
    return sid[:4] + "***"


def _conn() -> sqlite3.Connection:
    return db.connect()


def _rows(sql: str, args: tuple = ()) -> list[dict]:
    with _conn() as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def _one(sql: str, args: tuple = ()) -> dict:
    r = _rows(sql, args)
    return r[0] if r else {}


def _since(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")


def _mode_bucket(mode: str | None) -> str:
    m = (mode or "").strip()
    if not m:
        return "unknown"
    if m.startswith("llm:"):
        return "llm"
    for b in _MODES:
        if m.startswith(b):
            return b
    return "other"


# ── 1. 概览 ────────────────────────────────────────────────
@router.get("/overview")
def overview(request: Request, days: int = Query(7, ge=1, le=90)) -> dict:
    who = _admin(request)

    today = date.today().isoformat()
    q_today = _one("SELECT COUNT(*) n, COUNT(DISTINCT student_id) v FROM qa_log WHERE substr(ts,1,10)=?", (today,))

    rows = _rows("SELECT ts, student_id, mode, n_cites FROM qa_log WHERE ts >= ?", (_since(days),))
    by_day: dict[str, dict] = {}
    for i in range(days):
        d = (datetime.now() - timedelta(days=days - 1 - i)).date().isoformat()
        by_day[d] = {"date": d, "questions": 0, "visitors": set(), "llm": 0, "basic": 0,
                     "fallback": 0, "chat": 0}
    mode_cnt: Counter = Counter()
    cited = 0
    judged = 0          # 只有带 n_cites 的新记录才参与命中率，老数据不拉低或抬高
    for r in rows:
        d = (r["ts"] or "")[:10]
        b = _mode_bucket(r["mode"])
        mode_cnt[b] += 1
        if r.get("n_cites") is not None:
            judged += 1
            if r["n_cites"]:
                cited += 1
        if d in by_day:
            by_day[d]["questions"] += 1
            by_day[d]["visitors"].add(r["student_id"] or "")
            if b in ("llm", "basic", "fallback", "chat"):
                by_day[d][b] += 1
    series = []
    for d, v in by_day.items():
        v = dict(v)
        v["visitors"] = len({x for x in v["visitors"] if x})
        series.append(v)

    fb = _one("SELECT SUM(vote=1) up, SUM(vote=-1) down FROM feedback")
    kb = _one("""SELECT
        SUM(status='published') published, SUM(status='review') review,
        SUM(status='draft') draft, SUM(status='expired') expired,
        SUM(status='archived') archived,
        SUM(status='published' AND valid_until IS NOT NULL AND valid_until != ''
            AND valid_until <= ?) expiring
        FROM kb_item""", ((date.today() + timedelta(days=7)).isoformat(),))
    cand = _one("SELECT COUNT(*) pending FROM candidate WHERE status='pending'")

    lat = [r["latency_ms"] for r in _rows(
        "SELECT latency_ms FROM qa_log WHERE latency_ms IS NOT NULL AND latency_ms > 0"
        " AND ts >= ? ORDER BY latency_ms", (_since(days),))]
    def pct(p: float) -> int:
        if not lat:
            return 0
        return int(lat[min(len(lat) - 1, int(len(lat) * p))])

    return {
        "today": {"questions": q_today.get("n") or 0, "visitors": q_today.get("v") or 0},
        "days": series,
        "modes": {k: mode_cnt.get(k, 0) for k in ("llm", "basic", "fallback", "policy", "chat", "unknown", "other")},
        "hit_rate": round(cited / judged, 3) if judged else 0.0,
        "judged": judged,
        "feedback": {"up": fb.get("up") or 0, "down": fb.get("down") or 0},
        "kb": {k: (kb.get(k) or 0) for k in ("published", "review", "draft", "expired", "archived", "expiring")},
        "candidates": {"pending": cand.get("pending") or 0},
        "latency": {"p50": pct(0.5), "p95": pct(0.95), "avg": int(sum(lat) / len(lat)) if lat else 0,
                    "n": len(lat)},
        "viewer": who,
    }


# ── 2. 提问流水 ────────────────────────────────────────────
@router.get("/questions")
def questions(request: Request, days: int = Query(7, ge=1, le=365), mode: str = "",
              sid: str = "", q: str = "", full: int = 0,
              limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> dict:
    who = _admin(request)
    sql = "SELECT id, ts, student_id, question, answer, top_score, mode, latency_ms, n_cites, feedback" \
          " FROM qa_log WHERE ts >= ?"
    args: list = [_since(days)]
    if mode:
        if mode == "llm":
            sql += " AND mode LIKE 'llm%'"
        elif mode == "fallback":
            sql += " AND (mode LIKE 'fallback%' OR mode IS NULL OR mode='')"
        else:
            sql += " AND mode LIKE ?"
            args.append(mode + "%")
    if sid:
        sql += " AND student_id = ?"
        args.append(sid)
    if q:
        sql += " AND question LIKE ?"
        args.append(f"%{q}%")
    total = _one("SELECT COUNT(*) n FROM (" + sql + ")", tuple(args)).get("n") or 0
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    args += [limit, offset]
    rows = _rows(sql, tuple(args))
    full_view = bool(full)
    out = []
    for r in rows:
        r["student_id"] = _mask(r.get("student_id"), full_view)
        r["mode_bucket"] = _mode_bucket(r.get("mode"))
        if not full_view:
            r.pop("answer", None)
        out.append(r)
    return {"total": total, "limit": limit, "offset": offset, "rows": out,
            "masked": not full_view}


# ── 3. 未命中清单 ──────────────────────────────────────────
@router.get("/gaps")
def gaps(request: Request, days: int = Query(30, ge=1, le=365),
         limit: int = Query(40, ge=1, le=200)) -> dict:
    _admin(request)
    rows = _rows("""SELECT question, mode, top_score, ts FROM qa_log
                    WHERE ts >= ? AND (
                          mode LIKE 'fallback%'
                          OR (n_cites = 0 AND (mode LIKE 'llm%' OR mode LIKE 'basic%'))
                          -- 老记录没有 mode：只按分数判断，且排除「你好」这类短句
                          OR ((mode IS NULL OR mode = '') AND COALESCE(top_score,0) < ?
                              AND length(trim(question)) >= 6)
                    )
                    ORDER BY id DESC LIMIT 5000""", (_since(days), config.MIN_SCORE))
    groups: dict[str, dict] = {}
    for r in rows:
        key = "".join(ch for ch in (r["question"] or "").lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
        key = key[:40]
        if not key:
            continue
        g = groups.setdefault(key, {"key": key, "sample": r["question"], "count": 0,
                                    "last_ts": r["ts"], "modes": Counter(), "score_max": 0.0})
        g["count"] += 1
        g["modes"][_mode_bucket(r["mode"])] += 1
        g["last_ts"] = max(g["last_ts"] or "", r["ts"] or "")
        g["score_max"] = max(g["score_max"], r["top_score"] or 0.0)
    items = sorted(groups.values(), key=lambda g: -g["count"])[:limit]
    for g in items:
        g["modes"] = dict(g["modes"])
        g["score_max"] = round(g["score_max"], 2)
    return {"total_groups": len(groups), "rows": items}


# ── 4. 反馈 ───────────────────────────────────────────────
@router.get("/feedback")
def feedback_list(request: Request, limit: int = Query(100, ge=1, le=500), vote: int = 0) -> dict:
    who = _admin(request)
    sql = "SELECT id, ts, student_id, question, answer, vote, note, mode FROM feedback"
    args: list = []
    if vote in (1, -1):
        sql += " WHERE vote = ?"
        args.append(vote)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    rows = _rows(sql, tuple(args))
    for r in rows:
        r["student_id"] = _mask(r.get("student_id"), bool(config.ADMINS and who in config.ADMINS))
        r["mode_bucket"] = _mode_bucket(r.get("mode"))
    return {"rows": rows, "up": _one("SELECT COUNT(*) n FROM feedback WHERE vote=1").get("n") or 0,
            "down": _one("SELECT COUNT(*) n FROM feedback WHERE vote=-1").get("n") or 0}


# ── 5. 知识库健康 ─────────────────────────────────────────
@router.get("/kb")
def kb_health(request: Request) -> dict:
    _admin(request)
    status = {r["status"]: r["n"] for r in _rows("SELECT status, COUNT(*) n FROM kb_item GROUP BY status")}
    src = {r["source_type"] or "unverified": r["n"]
           for r in _rows("SELECT source_type, COUNT(*) n FROM kb_item GROUP BY source_type")}
    ttl = {r["ttl_type"] or "A": r["n"] for r in _rows("SELECT ttl_type, COUNT(*) n FROM kb_item GROUP BY ttl_type")}
    no_src = _one("""SELECT COUNT(*) n FROM kb_item WHERE status='published'
                     AND (source_url IS NULL OR source_url='')""").get("n") or 0
    warn = _one("""SELECT COUNT(*) n FROM kb_item WHERE status='published'
                   AND warnings IS NOT NULL AND warnings != '' AND warnings != '[]'""").get("n") or 0
    stale_days = 180
    stale_cut = (date.today() - timedelta(days=stale_days)).isoformat()
    stale = _one("""SELECT COUNT(*) n FROM kb_item WHERE status='published'
                    AND (verified_at IS NULL OR verified_at < ?)""", (stale_cut,)).get("n") or 0
    recheck = _one("SELECT COUNT(*) n FROM kb_item WHERE needs_recheck=1").get("n") or 0
    expiring = _rows("""SELECT id, question, valid_until FROM kb_item
                        WHERE status='published' AND valid_until IS NOT NULL AND valid_until != ''
                        ORDER BY valid_until LIMIT 20""")
    no_src_list = _rows("""SELECT id, question FROM kb_item WHERE status='published'
                           AND (source_url IS NULL OR source_url='') LIMIT 20""")
    return {
        "status": status, "source_type": src, "ttl": ttl,
        "no_source": no_src, "no_source_items": no_src_list,
        "with_warnings": warn, "stale": {"days": stale_days, "count": stale},
        "needs_recheck": recheck, "expiring": expiring,
        "total": sum(status.values()),
    }


# ── 6. 审批审计 ───────────────────────────────────────────
@router.get("/audit")
def audit(request: Request, limit: int = Query(100, ge=1, le=500)) -> dict:
    _admin(request)
    rows = _rows("""SELECT r.id, r.ts, r.item_id, r.action, r.reviewer, r.note,
                           r.before, r.after, k.question
                    FROM review_log r LEFT JOIN kb_item k ON k.id = r.item_id
                    ORDER BY r.id DESC LIMIT ?""", (limit,))
    acts = {r["action"]: r["n"] for r in _rows("SELECT action, COUNT(*) n FROM review_log GROUP BY action")}
    who = {r["reviewer"] or "?": r["n"] for r in _rows(
        "SELECT reviewer, COUNT(*) n FROM review_log GROUP BY reviewer ORDER BY n DESC LIMIT 10")}
    locked = _rows("""SELECT id, question, owner, locked_until FROM kb_item
                      WHERE locked_until IS NOT NULL AND locked_until > ?""",
                   (datetime.now().isoformat(timespec="seconds"),))
    return {"rows": rows, "actions": acts, "reviewers": who, "locked": locked}


# ── 7. 模型与成本 ─────────────────────────────────────────
@router.get("/usage")
def usage(request: Request, days: int = Query(7, ge=1, le=90)) -> dict:
    _admin(request)
    path = config.DATA_DIR / "llm_usage.jsonl"
    cut = _since(days)
    per_model: dict[str, dict] = {}
    per_day: dict[str, dict] = defaultdict(lambda: {"calls": 0, "prompt": 0, "completion": 0})
    total = {"calls": 0, "prompt": 0, "completion": 0, "cost": 0.0}
    bad = 0
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                bad += 1
                continue
            if (r.get("ts") or "") < cut:
                continue
            model = r.get("model") or "?"
            p, c = int(r.get("prompt") or 0), int(r.get("completion") or 0)
            base = model.split(":")[0]
            price = next((v for k, v in PRICES.items() if base.startswith(k)), None)
            cost = (p * price[0] + c * price[1]) / 1_000_000 if price else 0.0
            m = per_model.setdefault(model, {"calls": 0, "prompt": 0, "completion": 0, "cost": 0.0})
            m["calls"] += 1
            m["prompt"] += p
            m["completion"] += c
            m["cost"] += cost
            d = (r.get("ts") or "")[:10]
            per_day[d]["calls"] += 1
            per_day[d]["prompt"] += p
            per_day[d]["completion"] += c
            total["calls"] += 1
            total["prompt"] += p
            total["completion"] += c
            total["cost"] += cost
    for m in per_model.values():
        m["cost"] = round(m["cost"], 6)
    total["cost"] = round(total["cost"], 6)
    return {"total": total, "per_model": [{"model": k, **v} for k, v in
                                          sorted(per_model.items(), key=lambda kv: -kv[1]["calls"])],
            "per_day": [{"date": k, **v} for k, v in sorted(per_day.items())],
            "bad_lines": bad, "priced": list(PRICES)}


# ── 8. 系统状态 ───────────────────────────────────────────
@router.get("/system")
def system(request: Request) -> dict:
    _admin(request)
    db_path = Path(config.DB_PATH)
    backups = sorted((config.ROOT / "backups").glob("kb-*.sqlite3")) if (config.ROOT / "backups").exists() else []
    qa_jsonl = config.DATA_DIR / "qa_log.jsonl"
    usage_jsonl = config.DATA_DIR / "llm_usage.jsonl"

    def lines(p: Path) -> int:
        try:
            with p.open("rb") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    commit = ""
    try:
        head = (config.ROOT / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1]
            loose = config.ROOT / ".git" / ref
            if loose.exists():
                commit = loose.read_text(encoding="utf-8").strip()[:7]
            else:
                packed = (config.ROOT / ".git" / "packed-refs").read_text(encoding="utf-8")
                for line in packed.splitlines():
                    if line.endswith(" " + ref):
                        commit = line.split()[0][:7]
                        break
        else:
            commit = head[:7]
    except Exception:
        pass

    return {
        "db": {"path": str(db_path), "size_kb": round(db_path.stat().st_size / 1024, 1) if db_path.exists() else 0,
               "items": _one("SELECT COUNT(*) n FROM kb_item").get("n") or 0,
               "questions": _one("SELECT COUNT(*) n FROM qa_log").get("n") or 0},
        "logs": {"qa_jsonl": lines(qa_jsonl), "usage_jsonl": lines(usage_jsonl)},
        "backups": {"count": len(backups), "latest": backups[-1].name if backups else "",
                    "latest_at": datetime.fromtimestamp(backups[-1].stat().st_mtime).isoformat(timespec="seconds")
                    if backups else ""},
        "git": {"commit": commit, "branch": "master"},
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "now": datetime.now().isoformat(timespec="seconds")},
        "limits": {"llm_per_hour": int(os.environ.get("ASK_LIMIT_PER_HOUR", "10")),
                   "basic_per_hour": int(os.environ.get("ASK_BASIC_LIMIT_PER_HOUR", "20"))},
    }
