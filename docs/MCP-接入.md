# MCP 接入说明

书院资料库通过 MCP 给「同学的 AI」使用：Claude Desktop、Cursor、Cherry Studio 等支持 MCP 的客户端都能接。

服务端只有一个文件：`mcp_server.py`，它调用本机的只读 API（`/api/search`、`/api/library`、`/api/clause`、`/api/updates`）。

## 四个工具

| 工具 | 用途 | 例子 |
|---|---|---|
| `search_kb` | 搜问答与资料库 | “書院能不能養寵物” |
| `get_item` | 取一条（问答或作品） | `item_id=12, type=work` |
| `get_clause` | 取规章条款原文 | `anchor=3.2` |
| `list_updates` | 最近改了什么 | `since=2026-11-01` |

## Claude Desktop（Windows）

1. 打开配置：`%APPDATA%\Claude\claude_desktop_config.json`
2. 加一段（路径按你机器改）：

```json
{
  "mcpServers": {
    "shuyuan": {
      "command": "D:\\Projects\\rc-ai-assistant\\.venv\\Scripts\\python.exe",
      "args": ["D:\\Projects\\rc-ai-assistant\\mcp_server.py"],
      "env": { "RC_AI_BASE": "http://127.0.0.1:8001" }
    }
  }
}
```

3. 完全退出 Claude（托盘也要退），重新打开。
4. 在对话框里点工具图标，应能看到 `search_kb` 等四个。

## Cursor

`Settings → MCP → Add new MCP server`，命令同上；或直接编辑 `~/.cursor/mcp.json`，结构一样。

## 接公网那台

把 `RC_AI_BASE` 改成 `http://159.75.225.125/ai` 即可（只读接口，匿名可访问）。

## 自检

```bash
.venv/Scripts/python.exe tests/test_mcp.py
```

应输出 `8 pass / 0 fail`。这条会真的把服务器拉起来、走 stdio 调四个工具，不是模拟。

## 注意

- 只读：四个工具都写不了数据
- 没有身份：目前匿名可用，靠 IP 限流
- 引用的条款是**当年版本**；跨学年使用时注意 `version` 字段
