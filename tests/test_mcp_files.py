"""cklc-files MCP 端到端测试：拉起来、走 stdio 调三个工具。

    ./.venv/Scripts/python.exe tests/test_mcp_files.py
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
    text = "\n".join(c.text for c in (res.content or []) if getattr(c, "type", "") == "text").strip()
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": text}


async def main():
    params = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "mcp_files_server.py")],
        env={**os.environ, "RC_AI_BASE": os.environ.get("RC_AI_BASE", "http://127.0.0.1:8001")})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = sorted(t.name for t in (await s.list_tools()).tools)
            check("三个工具都注册了", set(names) == {"search_files", "get_file", "list_files"}, str(names))

            d = payload(await s.call_tool("list_files", {"limit": 3}))
            check("list_files 有结果", d.get("total", 0) > 0, str(d)[:160])
            first = (d.get("items") or [{}])[0]
            check("结果带下载地址", str(first.get("url", "")).startswith("http"), str(first.get("url")))

            d2 = payload(await s.call_tool("search_files", {"query": first.get("name", "")[:2]}))
            check("search_files 能按名字搜", d2.get("total", 0) > 0, str(d2)[:160])

            one = payload(await s.call_tool("get_file", {"file_id": first.get("file_id")}))
            check("get_file 能取单条", bool(one.get("item")), str(one)[:160])

            bad = payload(await s.call_tool("get_file", {"file_id": 999999}))
            check("不存在的文件报错", "error" in bad or "detail" in bad, str(bad)[:120])

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
