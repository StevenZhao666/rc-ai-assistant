"""数据后台的接口测试：鉴权、口径、脱敏。

    .venv/Scripts/python.exe tests/test_admin.py

默认打 127.0.0.1:8001；管理员用虚构号 uc99999（要在 .env 的 ADMINS 或 REVIEWERS 里）。
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("BASE", "http://127.0.0.1:8001")
ADMIN = os.environ.get("TEST_ADMIN", "uc99999")
PASS = FAIL = 0


def call(path: str, who: str | None = ADMIN):
    req = urllib.request.Request(BASE + "/api/admin" + path)
    if who:
        req.add_header("X-Admin", who)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}  {detail}")


def main() -> None:
    code, body = call("/overview", who=None)
    check("无身份被拒", code == 401, f"{code} {body}")

    code, body = call("/overview", who="uc00000")
    check("非管理员被拒", code == 403, f"{code} {body}")

    code, d = call("/overview")
    check("概览可读", code == 200 and "days" in d, str(code))
    check("概览含 7 天序列", len(d.get("days") or []) == 7, str(d.get("days")))
    check("命中率在 0~1 之间", 0.0 <= d.get("hit_rate", -1) <= 1.0, str(d.get("hit_rate")))
    check("知识库有已发布条目", (d.get("kb") or {}).get("published", 0) > 0, str(d.get("kb")))

    code, q = call("/questions?days=30&limit=5")
    check("流水可读", code == 200 and "rows" in q, str(code))
    check("默认脱敏学号", all(("***" in (r.get("student_id") or "")) or r.get("student_id") in ("匿名", "")
                              for r in q["rows"]), str([r.get("student_id") for r in q["rows"]][:3]))
    check("默认不返回答案原文", all("answer" not in r for r in q["rows"]), "")

    code, g = call("/gaps?days=30")
    check("未命中可读", code == 200 and "rows" in g, str(code))
    check("未命中按次数排序", all(g["rows"][i]["count"] >= g["rows"][i + 1]["count"]
                                  for i in range(len(g["rows"]) - 1)), "")

    code, f = call("/feedback?limit=5")
    check("反馈可读", code == 200 and "up" in f, str(code))

    code, k = call("/kb")
    check("知识库健康可读", code == 200 and "status" in k and "source_type" in k, str(code))
    check("状态数与总数一致", sum((k.get("status") or {}).values()) == k.get("total"),
          f"{k.get('status')} vs {k.get('total')}")

    code, a = call("/audit?limit=5")
    check("审计可读", code == 200 and "actions" in a, str(code))

    code, u = call("/usage?days=30")
    check("成本可读", code == 200 and "total" in u and "per_model" in u, str(code))

    code, s = call("/system")
    check("系统信息可读", code == 200 and "db" in s and "logs" in s, str(code))
    check("条数与库一致", s["db"]["items"] >= (k.get("total") or 0), f"{s['db']}")

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
