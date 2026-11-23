# MCP 试用连接说明

给同学的 AI 用，**只读**，不需要装我们的项目。

## 地址

```
http://159.75.225.125/ai/mcp          ← 问答/条款/更新（cklc）
http://159.75.225.125/ai/mcp-files    ← 资料库文件（cklc-files）
```

传输方式：**Streamable HTTP**（不是 SSE，不是 stdio）。

## 能做什么（四个工具）

| 工具 | 用途 | 例子 |
|---|---|---|
| `search_kb` | 搜问答 + 资料库 | 「書院能不能養寵物」 |
| `get_item` | 按编号取一条（问答或作品） | `item_id=9, type=qa` |
| `get_clause` | 按条款号取规章原文 | `anchor=3.2` |
| `list_updates` | 最近改了什么 | `since=2026-11-01` |

返回里带 `uid`（如 `kb-0009`）和 `revision`，可核对是哪一版。

参数名注意：取单条用 **`item_id`**（不是 `id`）。

## 各客户端怎么填

### Cherry Studio

设置 → MCP 服务器 → 添加
- 名称：cklc
- 类型：**Streamable HTTP**
- URL：`http://159.75.225.125/ai/mcp`

### Cursor

`~/.cursor/mcp.json`（或设置里 MCP → Add）：

```json
{
  "mcpServers": {
    "cklc": { "url": "http://159.75.225.125/ai/mcp" }
  }
}
```

### Hermes

```bash
hermes mcp add cklc --url http://159.75.225.125/ai/mcp
```

### dsh

```bash
dsh mcp add-http cklc http://159.75.225.125/ai/mcp
```

（dsh 目前有已知的 MCP 竞态 bug，工具可能挂不上；那是它的问题，不是服务端。）

### Claude Desktop

桌面版只认 stdio，用 mcp-remote 转一下：

```json
{
  "mcpServers": {
    "cklc": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://159.75.225.125/ai/mcp"]
    }
  }
}
```

## 试这三句

1. 「書院能不能養寵物？」→ 应命中 `kb-0009`，答“不允许，除非院长特别许可”
2. 「第 17.1 条原文」→ 返回英文条款原文（`chunk-xxxx`）
3. 「最近更新了什么」→ 列出问答与资料库条目

## 限制

- 只读，写不了任何东西
- 无登录，按 IP 限速（每分钟 60 次）
- 只返回已发布、未过期、在生效期内的内容
- 文件服务 `cklc-files` 已开：`/ai/mcp-files`（三个工具：search_files / get_file / list_files）
- 资料库目前为空：测试条目已全部下架（archived），等真投稿

## 出问题看哪

- 连不上：先 `curl -X POST http://159.75.225.125/ai/mcp` 看是不是 421/502
- 有工具但搜不到：换个说法，或先看网页版 `http://159.75.225.125/ai/`
- 想自己跑一份：仓库 `mcp_server.py`，`RC_AI_BASE` 指向上面的地址即可
