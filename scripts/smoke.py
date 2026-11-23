"""端到端冒烟测试：一条命令确认「现在的服务还是好的」。

    ./.venv/Scripts/python.exe scripts/smoke.py
    BASE=http://159.75.225.125/ai ./.venv/Scripts/python.exe scripts/smoke.py   # 打公网

只读检查，不改数据；会真实调用一次模型（约 1-3 秒）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("BASE", "http://127.0.0.1:8001").rstrip("/")
ADMIN = os.environ.get("SMOKE_ADMIN", "uc99999")

PASS = FAIL = 0
DETAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}  {detail}")
        DETAILS.append(f"{name}: {detail}")


def req(path: str, method: str = "GET", body: dict | None = None, headers: dict | None = None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw.decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode("utf-8", "ignore")


def post_ask(q: str) -> dict:
    code, d = req("/api/ask", "POST", {"question": q}, {"X-Device-Id": "smoke-test"})
    check(f"提问「{q}」返回 200", code == 200, str(code))
    return d if isinstance(d, dict) else {}


def main() -> None:
    # 1. 存活与页面
    code, d = req("/health")
    check("健康检查 200 且 ok=true", code == 200 and isinstance(d, dict) and d.get("ok"), f"{code} {d}")

    for path, word in (("/", "崑崑"), ("/review", "审批"), ("/admin", "数据后台"), ("/upload", "投稿"), ("/library", "資料庫")):
        code, body = req(path)
        text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
        check(f"页面 {path} 可打开且含关键词", code == 200 and word in text, f"{code}")

    # 2. 三条典型回答路径
    d = post_ask("健身房几点开")
    check("资料题给出引用", bool(d.get("citations")), json.dumps(d.get("citations"), ensure_ascii=False)[:120])
    check("资料题带模式", str(d.get("mode", "")).startswith(("llm", "basic", "extractive")), str(d.get("mode")))

    d = post_ask("你好")
    check("寒暄走 chat 分支", d.get("mode") == "chat", str(d.get("mode")))
    check("寒暄不返回引用", not d.get("citations"), str(d.get("citations")))

    d = post_ask("押金多少")
    check("已知缺口走 fallback", str(d.get("mode", "")).startswith("fallback"), str(d.get("mode")))

    # 2.5 投稿通道
    code, info = req("/api/upload/info")
    check("投稿信息可读", code == 200 and isinstance(info, dict) and "open" in info, str(code))
    code, _ = req("/api/upload", "POST", {})
    check("投稿接口拒绝空提交", code in (400, 403, 415, 422, 503), str(code))

    code, lib = req("/api/library")
    check("资料库接口可读", code == 200 and isinstance(lib, dict) and "items" in lib, str(code))
    code, sall = req("/api/search?q=" + "abc")
    check("统一检索接口可读", code == 200 and isinstance(sall, dict) and "items" in sall, str(code))

    # 3. 鉴权
    code, _ = req("/api/admin/overview")
    check("后台接口无身份被拒", code == 401, str(code))

    code, ov = req("/api/admin/overview", headers={"X-Admin": ADMIN})
    check("后台概览可读", code == 200 and isinstance(ov, dict), str(code))
    check("概览里有知识库统计", isinstance(ov, dict) and (ov.get("kb") or {}).get("published", 0) > 0,
          str(ov.get("kb") if isinstance(ov, dict) else ov)[:120])

    code, _ = req("/api/review/item/23")
    check("审批接口无身份被拒", code == 401, str(code))

    code, it = req("/api/review/item/23", headers={"X-Reviewer": ADMIN})
    check("审批单条可读", code == 200 and isinstance(it, dict) and "item" in it, str(code))
    check("单条带原文或条款", bool(it.get("bound") or it.get("related") or it.get("item", {}).get("original_answer")),
          "bound/related/original_answer 都是空")

    # 4. 结构冒烟（独立进程，避免污染当前库）
    if not BASE.startswith("http://127.0.0.1"):
        print("[SKIP] 公网模式跳过本地 schema 测试")
    else:
        r = subprocess.run([sys.executable, str(ROOT / "tests" / "test_schema.py")],
                           capture_output=True, text=True, encoding="utf-8")
        tail = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
        check("新结构 DDL 冒烟（18 表）", r.returncode == 0, tail or (r.stderr or "")[-160:])

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    if FAIL:
        print("失败项：")
        for x in DETAILS:
            print("  -", x)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
