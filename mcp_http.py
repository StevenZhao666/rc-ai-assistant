"""MCP over HTTP：把 cklc 的四个只读工具挂在 HTTP 上，别人用 URL 就能连。

    RC_AI_BASE=http://159.75.225.125/ai python mcp_http.py
    → http://0.0.0.0:8092/mcp

线上由 systemd（rc-ai-mcp）跑，Apache 反代到 /ai/mcp。
工具定义直接复用 mcp_server.py，两处不各写一份。
"""
from __future__ import annotations

import os

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings

from mcp_server import mcp

HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8092"))
PUBLIC_HOST = os.environ.get("MCP_PUBLIC_HOST", "")     # 例如 159.75.225.125

# 反代后 Host 头是公网地址，默认只放行 localhost 会被 421 拒掉
allowed = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
if PUBLIC_HOST:
    allowed += [PUBLIC_HOST, f"{PUBLIC_HOST}:*"]

app = mcp.streamable_http_app(
    host=HOST,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed,
        allowed_origins=["*"],
    ),
)

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
