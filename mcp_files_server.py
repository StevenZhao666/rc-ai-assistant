"""MCP：cklc-files —— 查书院资料库里的文件（只读）。

    python mcp_files_server.py
    RC_AI_BASE=http://159.75.225.125/ai python mcp_files_server.py

工具：
- search_files(query, kind?)   按关键词找文件
- get_file(file_id)            取一个文件的详情与下载地址
- list_files(kind?, limit)     最近上架的文件

只返回已上架（published）条目里的文件。
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from mcp.server.mcpserver import MCPServer

BASE = os.environ.get("RC_AI_BASE", "http://127.0.0.1:8001").rstrip("/")
# 给用户看的下载地址要用公网前缀；调接口仍走 BASE
PUBLIC = os.environ.get("MCP_PUBLIC_BASE", BASE).rstrip("/")
mcp = MCPServer("cklc-files")


def _get(path: str) -> dict:
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:                      # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}", "url": BASE + path}


@mcp.tool(description="按关键词搜书院资料库里的文件（文件名、所属条目标题或说明）。")
def search_files(query: str, kind: str = "", limit: int = 10) -> dict:
    q = urllib.parse.quote(query or "")
    k = urllib.parse.quote(kind or "")
    d = _get(f"/api/files?q={q}&kind={k}&limit={max(1, min(limit, 50))}")
    if "items" in d:
        for it in d["items"]:
            it["url"] = PUBLIC + it["url"]
    return d


@mcp.tool(description="按编号取一个文件：文件名、大小、所属条目、下载地址。")
def get_file(file_id: int) -> dict:
    d = _get(f"/api/files/{int(file_id)}")
    if "item" in d:
        d["item"]["url"] = PUBLIC + d["item"]["url"]
    return d


@mcp.tool(description="列出最近上架的文件，可按 kind=work|link|doc 过滤。")
def list_files(kind: str = "", limit: int = 20) -> dict:
    return search_files("", kind=kind, limit=limit)


if __name__ == "__main__":
    mcp.run("stdio")
