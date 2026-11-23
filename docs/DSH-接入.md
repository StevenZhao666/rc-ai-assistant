# 在 dsh 里用自然语言问书院

目标：在 dsh 里直接问「書院能不能養寵物？」，它给你**带条目编号的答案**，而不是自己瞎猜。

做法：dsh 里加一条规则 → 凡问书院的事，先跑 `ask.bat`，把输出转述。`ask.bat` 调的是本机的 `/api/ask`（检索 + 模型 + 引用），跟网页上是同一个大脑。

---

## 一、从零装（新机器）

### 1. 拿代码

```bash
git clone https://github.com/StevenZhao666/rc-ai-assistant.git
cd rc-ai-assistant
```

### 2. 建环境

需要 Python 3.11+。

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

打开 `.env`，至少填一项：

```
LLM_KEY=你的DeepSeek密钥
```

（`UPLOAD_CODE` 是投稿邀请码，随便设一个；`REVIEWERS` 是审批人学号，用虚构号测试。）

### 3. 生成知识库

```bash
.venv\Scripts\python.exe scripts\seed_demo.py      # 示例数据，先跑通
.venv\Scripts\python.exe scripts\build_kb.py       # 有原始资料时再导真数据
```

### 4. 起服务

双击 `scripts\start_all.bat`，或：

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001
```

验证：

```bash
.venv\Scripts\python.exe ask.py "書院能不能養寵物"
```

应看到答案 + `依据 1 · 条目 …`。

### 5. 装 dsh（已有可跳过）

按官网装：<https://www.deepseek.com/en/harness/>

装完确认：

```bash
dsh doctor
```

### 6. 把规则写进 dsh

```bash
.venv\Scripts\python.exe scripts\install_dsh_rule.py
```

它会改 `%USERPROFILE%\.dsh-rust\settings.toml` 的 `custom_instructions`，并在同目录留备份。

### 7. 用

```bash
dsh "書院能不能養寵物？"
```

或一次性：

```bash
dsh exec "換房間一年能申請幾次？"
```

期望输出里有：

```
依据 1 · 条目 9 · 張崑崙書院允許寵物嗎？
```

---

## 二、验证装对了

| 步骤 | 命令 | 期望 |
|---|---|---|
| 服务通 | `python ask.py "洗衣房在哪一層"` | 答案 + 依据行 |
| 规则在 | `python scripts/install_dsh_rule.py --show` | 打印那段中文规则 |
| dsh 通 | `dsh exec "書院能否養寵物？"` | 答案里带 `依据 1 · 条目 9` |

三行都过，就是端到端通了。

---

## 三、不用了怎么撤

```bash
.venv\Scripts\python.exe scripts/install_dsh_rule.py --remove
```

规则从 dsh 配置里删掉，其他设置不动。也可以手动把 `settings.toml` 里 `custom_instructions` 那行清空。

---

## 四、为什么不用 MCP

dsh 已经支持 `dsh mcp add`，我们四个只读工具也注册成功了（`dsh mcp list` 能看到 `[on] cklc`），但**会话里拿不到这些工具**——`session/new` 和 MCP 工具注册有竞态，失败还是静默的。

上游记录：[deepseek-ai/deepseek-harness#2273](https://github.com/deepseek-ai/deepseek-harness/discussions/2273)（另见 #1240 / #1239 / #1241）。

所以现在走 `ask.bat` 这条路：稳定、可验证、不依赖 dsh 的 MCP 实现。等上游修了，`mcp.toml` 里那条 `cklc` 直接能用，不用再改。

---

## 五、给别人用（同学的 AI）

- **同一个局域网/本机**：照上面装，`ask.bat` 指 `http://127.0.0.1:8001`
- **不装环境，只想问**：让他打开 `http://159.75.225.125/ai/`，或者 `dsh` 里让它 `curl`：

```bash
curl --noproxy "*" "http://159.75.225.125/ai/api/search?q=寵物"
```

- **接了 MCP 的客户端**（Cherry Studio / Cursor）：按 `docs/MCP-接入.md` 配，`RC_AI_BASE` 指公网地址。
