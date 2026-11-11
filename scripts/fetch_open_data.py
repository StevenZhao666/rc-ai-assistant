"""从 data.um.edu.mo 拉开放数据，落进 chunk 表当「草稿」。

为什么单独一个脚本：
- 数据平台的接口要订阅密钥，且路径由门户决定 → 单独配置、单独跑，不污染问答服务
- 拉下来的东西一律 status='draft'，绝不直接可答（对应「爬虫不得直写 published」这条边界）
- 可以在没有网络/没有密钥的情况下用 --ingest 导入本地 JSON 验证解析

用法：
    python scripts/fetch_open_data.py --list
    python scripts/fetch_open_data.py --check
    python scripts/fetch_open_data.py --fetch courses
    python scripts/fetch_open_data.py --ingest sample.json --dataset courses --dry-run

密钥：.env 里的 OPEN_DATA_KEY（Azure APIM 订阅密钥）
路径：拿到门户的「APIs」页后，把 Path 填到下面 DATASETS 里即可
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config, db  # noqa: E402

# ── 配置：拿到门户里的接口路径后，改这里 ──────────────────────────
# path 为相对路径，拼接在 BASE 后；params 是默认查询参数（分页等）
BASE = os.environ.get("OPEN_DATA_BASE", "https://data.um.edu.mo")
KEY_ENV = "OPEN_DATA_KEY"
KEY_HEADER = "Ocp-Apim-Subscription-Key"

DATASETS = {
    "courses": {
        "label": "课程与课堂安排（Courses）",
        "path": "/api/courses",          # ← 待填：门户 APIs 页里的实际路径
        "params": {"page": 1, "pageSize": 200},
        "title_field": "courseCode",
        "trust": "official",
    },
    "catalog": {
        "label": "课程目录（Course Catalog）",
        "path": "/api/coursecatalog",     # ← 待填
        "params": {},
        "title_field": "courseCode",
        "trust": "official",
    },
    "facilities": {
        "label": "体育设施（Sports Facilities）",
        "path": "/api/facilities",        # ← 待填
        "params": {},
        "title_field": "name",
        "trust": "official",
    },
    "events": {
        "label": "校内活动（Events）",
        "path": "/api/events",            # ← 待填
        "params": {},
        "title_field": "title",
        "trust": "official",
    },
    "holidays": {
        "label": "大学假期（Public Holidays）",
        "path": "/api/holidays",          # ← 待填
        "params": {},
        "title_field": "name",
        "trust": "official",
    },
}


def key() -> str:
    k = os.environ.get(KEY_ENV, "")
    if not k:
        print(f"缺少 {KEY_ENV}：请先在 data.um.edu.mo 申请并把密钥写进 .env")
    return k


def http_get(path: str, params: dict) -> tuple[int, str]:
    url = BASE.rstrip("/") + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url, headers={
        KEY_HEADER: key(),
        "Accept": "application/json",
        "User-Agent": "rc-ai-assistant/0.1",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")[:400]
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def as_records(payload: str) -> list[dict]:
    """兼容几种常见返回形状：裸数组 / {value:[...]} / {data:[...]} / {items:[...]}"""
    try:
        obj = json.loads(payload)
    except Exception:
        return []
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for k in ("value", "data", "items", "results", "records"):
            v = obj.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def to_draft(records: list[dict], ds: str) -> list[dict]:
    """把一条记录压成 chunk 的四个字段：url / title / text / status。

    结构化数据不切分：整条 JSON 存 text，title 取主键字段。
    这样人看起来是「一条记录」，模型看到的是完整字段，不会切碎。
    """
    cfg = DATASETS[ds]
    out = []
    for r in records:
        title = str(r.get(cfg["title_field"]) or r.get("title") or r.get("name") or "").strip()
        if not title:
            continue
        out.append({
            "url": f"{BASE}/dataset?{ds}",          # 数据集页（人可核）
            "title": f"[{ds}] {title}"[:200],
            "text": json.dumps(r, ensure_ascii=False),
            "status": "draft",
        })
    return out


def write_drafts(rows: list[dict], dry: bool) -> int:
    if dry:
        for r in rows[:5]:
            print(f"  (dry-run) {r['title'][:60]}")
        if len(rows) > 5:
            print(f"  ... 共 {len(rows)} 条")
        return len(rows)
    with db.connect(write=True) as conn:
        # 同 title 的草稿先删，避免重复拉取堆垃圾
        for r in rows:
            conn.execute("DELETE FROM chunk WHERE title = ? AND status = 'draft'", (r["title"],))
            conn.execute(
                "INSERT INTO chunk (url, title, text, status, updated_at) VALUES (?,?,?,?,?)",
                (r["url"], r["title"], r["text"], r["status"], date.today().isoformat()),
            )
        conn.commit()
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="列出已配置的数据集")
    ap.add_argument("--check", action="store_true", help="逐个探接口是否可用（需要密钥）")
    ap.add_argument("--fetch", metavar="DATASET", help="拉取某个数据集并写入草稿")
    ap.add_argument("--ingest", metavar="FILE", help="从本地 JSON 导入（验证解析用）")
    ap.add_argument("--dataset", help="配合 --ingest 指定数据集名")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    a = ap.parse_args()

    if a.list or not any([a.check, a.fetch, a.ingest]):
        print(f"base = {BASE}")
        print(f"密钥 = {'已配置' if os.environ.get(KEY_ENV) else '未配置'}")
        for name, cfg in DATASETS.items():
            print(f"  {name:12s} {cfg['path']:24s} {cfg['label']}")
        return 0

    if a.check:
        for name, cfg in DATASETS.items():
            code, body = http_get(cfg["path"], cfg["params"])
            n = len(as_records(body))
            print(f"  {name:12s} HTTP {code:>3}  记录 {n:>4}  {body[:70] if code != 200 else ''}")
        return 0

    if a.fetch:
        ds = a.fetch
        if ds not in DATASETS:
            print(f"未知数据集：{ds}")
            return 1
        code, body = http_get(DATASETS[ds]["path"], DATASETS[ds]["params"])
        if code != 200:
            print(f"拉取失败 HTTP {code}：{body[:200]}")
            return 1
        rows = to_draft(as_records(body), ds)
        n = write_drafts(rows, a.dry_run)
        print(f"{ds}: 解析 {n} 条 → {'未写入（dry-run）' if a.dry_run else '已写入 chunk(status=draft)'}")
        return 0

    if a.ingest:
        ds = a.dataset or "courses"
        rows = to_draft(as_records(Path(a.ingest).read_text(encoding="utf-8")), ds)
        n = write_drafts(rows, a.dry_run)
        print(f"{ds}: 从 {a.ingest} 解析 {n} 条 → {'未写入' if a.dry_run else '已写入草稿'}")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
