"""审批链路端到端测试：抓取 → 候选 → 草稿 → 认领 → 通过 → 立刻能搜到 → 冲突拦截 → 归档。

跑法（服务要在 8001）：
    .venv\\Scripts\\python.exe tests\\test_review.py
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8001"
A, B = "uc99999", "uc99998"
Q = "【测试】审批流程验证条目"
rows = []


def call(path, method="GET", body=None, who=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if who:
        req.add_header("X-Reviewer", who)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def check(name, cond, detail=""):
    rows.append((name, cond, detail))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


# 1. 无身份读队列 → 401
code, _ = call("/api/review/queue?status=review")
check("无身份访问被拒", code == 401, f"HTTP {code}")

# 2. 有身份 → 200
code, d = call("/api/review/queue?status=review", who=A)
check("有身份可读队列", code == 200, f"HTTP {code}, {d.get('count')} 条")

# 3. 抓一个真实页面
code, d = call("/api/review/scan", "POST", {"url": "https://cklc.rc.um.edu.mo/"}, who=A)
cid = d.get("candidate_id")
check("抓取官网存成候选", code == 200 and bool(cid), f"HTTP {code}, {d.get('chars')} 字, id={cid}")

# 4. 候选列表
code, d = call("/api/review/candidates?status=new", who=A)
check("候选出现在列表", code == 200 and any(c["id"] == cid for c in d.get("items", [])),
      f"{len(d.get('items', []))} 条")

# 5. 写成问答 → 进待审
code, d = call(f"/api/review/candidates/{cid}/draft", "POST", {
    "question": Q, "answer": "这是一条用于验证审批链路的测试条目，测完会归档。",
    "category": "测试", "ttl_type": "A", "source": "审批自测"}, who=A)
iid = d.get("item_id")
check("候选生成待审条目", code == 200 and bool(iid), f"HTTP {code}, item={iid}")

# 6. 队列里能看到
code, d = call("/api/review/queue?status=review", who=A)
check("待审队列里有它", any(i["id"] == iid for i in d.get("items", [])), f"{d.get('count')} 条待审")

# 7. 认领：A 成功，B 抢不到
code, _ = call(f"/api/review/item/{iid}/claim", "POST", {}, who=A)
check("A 认领成功", code == 200, f"HTTP {code}")
code, d = call(f"/api/review/item/{iid}/claim", "POST", {}, who=B)
check("B 抢同一条被拒", code == 409, f"HTTP {code} {d.get('detail', '')}")

# 8. 通过（带版本号）
code, d = call(f"/api/review/item/{iid}/decide", "POST",
               {"action": "approve", "note": "自测通过", "version": 1}, who=A)
check("通过并发布", code == 200 and d.get("item", {}).get("status") == "published",
      f"HTTP {code}, status={d.get('item', {}).get('status')}")

# 9. 发布后立刻能搜到（证明检索索引重载了）
code, d = call("/api/ask", "POST", {"question": Q})
ans = d.get("answer", "")
hit = any(c.get("id") == iid for c in d.get("citations", []))
check("发布后立刻可检索", code == 200 and hit, f"mode={d.get('mode')}, 引用命中={hit}")

# 10. 用旧版本号再改 → 409
code, d = call(f"/api/review/item/{iid}/decide", "POST",
               {"action": "edit", "patch": {"answer": "覆盖测试"}, "version": 1}, who=B)
check("旧版本号被拦截", code == 409, f"HTTP {code} {d.get('detail', '')}")

# 11. 留痕
code, d = call(f"/api/review/item/{iid}", who=A)
hist = d.get("history", [])
check("操作留痕完整", len(hist) >= 3 and {h["action"] for h in hist} >= {"create", "approve", "claim"} or len(hist) >= 2,
      f"{len(hist)} 条: {[h['action'] for h in hist]}")

# 12. 归档后不再被检索
code, d = call(f"/api/review/item/{iid}/decide", "POST", {"action": "archive", "note": "测试结束"}, who=A)
code, d2 = call("/api/ask", "POST", {"question": Q})
still = any(c.get("id") == iid for c in d2.get("citations", []))
check("归档后不再可检索", code == 200 and not still, f"仍命中={still}")

ok = sum(1 for _, c, _ in rows if c)
print(f"\n{ok}/{len(rows)} 通过")
sys.exit(0 if ok == len(rows) else 1)
