"""MCP over HTTP：cklc-files（查资料库文件）。

    RC_AI_BASE=http://159.75.225.125/ai python mcp_files_http.py
    → http://127.0.0.1:8093/mcp
"""
from __future__ import annotations

import os

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings

from mcp_files_server import mcp

HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8093"))
PUBLIC_HOST = os.environ.get("MCP_PUBLIC_HOST", "")

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
