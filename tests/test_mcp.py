"""MCP 端到端测试：真的把服务器拉起来，走 stdio 调四个工具。

    ./.venv/Scripts/python.exe tests/test_mcp.py
"""
import asyncio
import json
import os
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
            check("四个工具都注册了", set(names) == {"search_kb", "get_item", "get_clause", "list_updates"}, str(names))

            r = payload(await sess.call_tool("search_kb", {"query": "換房間"}))
            check("search_kb 有结果", r.get("count", 0) > 0, str(r)[:160])
            types = {x.get("type") for x in r.get("items", [])}
            check("search_kb 结果带类型", bool(types), str(types))

            r = payload(await sess.call_tool("search_kb", {"query": "公開測試作品甲"}))
            check("search_kb 能搜到资料库条目", any(x.get("type") in ("work", "link", "doc") for x in r.get("items", [])),
                  str(r)[:160])

            r = payload(await sess.call_tool("get_clause", {"anchor": "3.2"}))
            rows = r.get("versions") or []
            check("get_clause 返回原文", bool(rows) and any("訪客" in (x.get("text") or "") for x in rows),
                  str(r)[:160])

            lib = payload(await sess.call_tool("search_kb", {"query": "作品", "limit": 3}))
            item = next((x for x in lib.get("items", []) if x.get("type") in ("work", "link", "doc")), None)
            if item:
                one = payload(await sess.call_tool("get_item", {"item_id": item["id"], "type": item["type"]}))
                check("get_item 能取资料库单条", bool(one.get("item")), str(one)[:160])
            else:
                check("get_item 能取资料库单条", False, "没有可用的资料库条目")

            upd = payload(await sess.call_tool("list_updates", {"since": "2026-01-01"}))
            check("list_updates 可读", "qa" in upd and "library" in upd, str(upd)[:160])

            err = payload(await sess.call_tool("get_clause", {"anchor": "999.999"}))
            check("取不存在的条款返回错误信息", "error" in err or "detail" in err, str(err)[:120])

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
