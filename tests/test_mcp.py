"""MCP 端到端测试：真的把服务器拉起来，走 stdio 调四个工具。

    ./.venv/Scripts/python.exe tests/test_mcp.py
"""
import asyncio
import json
import os
import urllib.request
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent.parent
PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}  {detail}")



def _env(key, default=""):
    if os.environ.get(key):
        return os.environ[key]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    return default


def _make_fixture() -> int:
    """造一条已上架的资料库条目，测试完再归档。"""
    import uuid
    code = _env("UPLOAD_CODE", "cklc-test-2026")
    reviewer = _env("REVIEWERS", "uc99999").split(",")[0].strip() or "uc99999"
    base = os.environ.get("RC_AI_BASE", "http://127.0.0.1:8001").rstrip("/")
    title = "MCP測試作品" + uuid.uuid4().hex[:6]
    boundary = "----b" + uuid.uuid4().hex
    fields = {"code": code, "kind": "work", "title": title, "author": "MCP測試",
              "contact": "mcp@example.com", "note": "自动化测试用", "consent": "1",
              "contact_public": "0"}
    CRLF = chr(13) + chr(10)
    data = b""
    for k, v in fields.items():
        data += f'--{boundary}{CRLF}Content-Disposition: form-data; name="{k}"{CRLF}{CRLF}{v}{CRLF}'.encode()
    data += (f'--{boundary}{CRLF}Content-Disposition: form-data; name="files"; filename="mcp.md"{CRLF}'
             f"Content-Type: text/markdown{CRLF}{CRLF}# mcp fixture{CRLF}").encode()
    data += f"--{boundary}--{CRLF}".encode()
    req = urllib.request.Request(base + "/api/upload", data=data, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        cid = json.loads(r.read())["id"]
    req = urllib.request.Request(base + f"/api/review/uploads/{cid}/decide",
                                 data=json.dumps({"action": "approve", "note": ""}).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json", "X-Reviewer": reviewer})
    with urllib.request.urlopen(req, timeout=60) as r:
        json.loads(r.read())
    lib = json.loads(urllib.request.urlopen(base + "/api/library?limit=50", timeout=30).read())
    item = next(i for i in lib["items"] if i["title"] == title)
    return item["id"], reviewer, base


def _archive(item_id: int, reviewer: str, base: str) -> None:
    # 资料库条目走专用接口，别用 /api/review/item（那是问答库，会误伤）
    req = urllib.request.Request(base + f"/api/review/library/{item_id}/archive",
                                 data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json", "X-Reviewer": reviewer})
    urllib.request.urlopen(req, timeout=30).read()


def payload(res):
    """把 CallToolResult 里的文本取出来并解析 JSON。"""
    parts = []
    for c in (res.content or []):
        if getattr(c, "type", "") == "text":
            parts.append(c.text)
    text = "\n".join(parts).strip()
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": text}


async def main():
    item_id, reviewer, base_url = _make_fixture()
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "mcp_server.py")],
        env={**os.environ, "RC_AI_BASE": os.environ.get("RC_AI_BASE", "http://127.0.0.1:8001")},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as sess:
            await sess.initialize()
            tools = await sess.list_tools()
            names = sorted(t.name for t in tools.tools)
            check("五个工具都注册了",
                  set(names) == {"search_kb", "get_item", "get_clause", "list_updates", "search_clauses"},
                  str(names))

            r = payload(await sess.call_tool("search_kb", {"query": "換房間"}))
            check("search_kb 有结果", r.get("count", 0) > 0, str(r)[:160])
            types = {x.get("type") for x in r.get("items", [])}
            check("search_kb 结果带类型", bool(types), str(types))

            r = payload(await sess.call_tool("search_kb", {"query": "公開測試作品甲"}))
            check("search_kb 能搜到资料库条目", any(x.get("type") in ("work", "link", "doc") for x in r.get("items", [])),
                  str(r)[:160])

            sc = payload(await sess.call_tool("search_clauses", {"query": "訪客過夜", "limit": 2}))
            check("search_clauses 能找到 3.2", any(x.get("anchor") == "3.2" for x in sc.get("items", [])),
                  str(sc)[:160])

            r = payload(await sess.call_tool("get_clause", {"anchor": "3.2"}))
            rows = r.get("versions") or []
            check("get_clause 返回原文", bool(rows) and any("訪客" in (x.get("text") or "") for x in rows),
                  str(r)[:160])

            lib = payload(await sess.call_tool("search_kb", {"query": "MCP測試作品", "limit": 5}))
            item = next((x for x in lib.get("items", []) if x.get("type") in ("work", "link", "doc")), None)
            one = payload(await sess.call_tool("get_item", {"item_id": item_id, "type": "work"}))
            check("get_item 能取资料库单条", bool(one.get("item")), str(one)[:160])

            upd = payload(await sess.call_tool("list_updates", {"since": "2026-01-01"}))
            check("list_updates 可读", "qa" in upd and "library" in upd, str(upd)[:160])

            err = payload(await sess.call_tool("get_clause", {"anchor": "999.999"}))
            check("取不存在的条款返回错误信息", "error" in err or "detail" in err, str(err)[:120])

    try:
        _archive(item_id, reviewer, base_url)
    except Exception as e:                                  # noqa: BLE001
        print(f"[warn] fixture 归档失败：{e}")

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
