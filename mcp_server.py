"""MCP 服务器：把书院资料库的四个只读接口包成 MCP 工具。

    python mcp_server.py                 # stdio（给 Claude Desktop / Cursor 用）
    RC_AI_BASE=http://159.75.225.125/ai python mcp_server.py

工具：
- search_kb(query, type?, limit)   搜问答与资料库
- get_item(id, type)               取一条（qa 或 work/link/doc）
- get_clause(anchor, version?)     取规章条款原文
- list_updates(since?)             最近改了什么

只读。服务端地址用环境变量 RC_AI_BASE，默认本机 8001。
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from mcp.server.mcpserver import MCPServer

BASE = os.environ.get("RC_AI_BASE", "http://127.0.0.1:8001").rstrip("/")
mcp = MCPServer("cklc")


def _get(path: str) -> dict:
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:                     # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}", "url": url}


@mcp.tool(description="搜索书院资料：问答条目与院生作品/网站资源。返回带 type 的结果列表。")
def search_kb(query: str, kind: str = "", limit: int = 8) -> dict:
    q = urllib.parse.quote(query or "")
    d = _get(f"/api/search?q={q}&limit={max(1, min(limit, 20))}")
    if "items" not in d:
        return d
    items = d["items"]
    if kind:
        items = [x for x in items if x.get("type") == kind]
    return {"query": query, "count": len(items), "items": items}


@mcp.tool(description="按编号取一条内容。type=qa 取问答条目；type=work/link/doc 取资料库条目。")
def get_item(item_id: int, type: str = "qa") -> dict:
    if type == "qa":
        return _get(f"/api/qa/{int(item_id)}")
    return _get(f"/api/library/{int(item_id)}")


@mcp.tool(description="按条款号取规章原文，例如 anchor=3.2。可带 version=AY2026-2027。")
def get_clause(anchor: str, version: str = "") -> dict:
    q = urllib.parse.quote(anchor)
    v = urllib.parse.quote(version)
    return _get(f"/api/clause?anchor={q}&version={v}")


@mcp.tool(description="自某日起新增或更新的内容（问答 + 资料库），日期格式 2026-11-01。")
def list_updates(since: str = "") -> dict:
    q = urllib.parse.quote(since)
    return _get(f"/api/updates?since={q}")


if __name__ == "__main__":
    mcp.run("stdio")
