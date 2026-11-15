# 昆昆 · 书院问答助手（框架）

一个面向书院/院系的小型问答系统骨架：**知识按“可追溯的断言”存储，答案只来自已审核的资料，答不上来就转人工**。

本项目公开的是**框架与机制**，不含任何真实题库、书院内部资料或个人信息。要跑起来，用你自己的 Excel 导入。

- 后端：FastAPI + SQLite + 纯原生 HTML/JS（无前端构建）
- 检索：中文二元组 + BM25（OpenCC 繁简归一），不依赖向量库
- 模型：任何 OpenAI 兼容接口（可配供应商链，主挂备用自动切换）
- 部署：单进程 + systemd/Apache 反代即可，2C4G 够用

## 为什么不是“又一个聊天机器人”

普通 RAG 的回答不可核对，学生信了错的规章，责任在书院。这里把四件事做进机制里：

1. **每条知识是一条带状态的记录**，`draft → review → published → expired → archived`；检索只吃 `published` 且未过期的。
2. **答案必须带来源**：模型的句子以 `[n]` 标注，后端只展示模型真正引用的条目；资料没有就直说。
3. **时效分层**：A 长期稳定（直接答）、B 每年变（加学年前缀）、C 实时活动（只给链接不转述）。
4. **答不了就转人工**：按原因分流——实时信息给权威渠道，资料缺口给办公室，问题太宽就请对方说具体。越界（代写、医疗、情绪、安全、跨书院）走专用话术，不检索。

## 目录

```
app/
  main.py      路由、限流、记账
  answer.py    提示词、意图判断、越界与兜底分支
  i18n.py      繁/简/英文案
  retrieve.py  分词 + BM25
  db.py        6 张表、状态机、审批锁、反馈
  review.py    审批接口（认领 / 通过 / 驳回 / 归档）
  profile.py   书院基本档案（示例值，请替换成你自己的）
  static/      学生端 index.html、审批端 review.html
scripts/
  build_kb.py  从 Excel 建库（含自动检查、A/B/C 分层、来源指派）
  seed_demo.py 生成一份虚构示例库，用于本地体验
  selftest.py  12 条断言
  expire.py    按有效期下架
tests/
  regress_personas.py  16 条人物场景回归
  test_review.py       13 步审批流程测试
data/
  *.example.py 修正层模板（来源映射、逐条修正）
```

## 跑起来

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Linux: .venv/bin/pip
cp .env.example .env        # 填 LLM_BASE / LLM_KEY / REVIEWERS
python scripts/seed_demo.py # 生成 6 条虚构问答，够把流程跑通
python -m uvicorn app.main:app --port 8001
```

- 学生端 `http://127.0.0.1:8001/`
- 审批端 `http://127.0.0.1:8001/review`（用 `.env` 里 `REVIEWERS` 填的学号）

自测：

```bash
python scripts/selftest.py
python tests/regress_personas.py
python tests/test_review.py
```

## 换成你自己的资料

1. 准备 Excel，两列：`问题`、`答案`（模板见 `docs/题库模板.md`）。
2. （可选）复制 `data/overrides.example.py` → `data/overrides.py`，写逐条修正：错字、要归档的旧条目。
3. （可选）复制 `data/source_map.example.py` → `data/source_map.py`，把问题关键词映射到官方页面。
4. `python scripts/build_kb.py your.xlsx`，看整理报告里的警告项，逐条处理。
5. 进审批端把 `draft` 批成 `published`，学生端才会答。

**建议**：先只放 20~30 条高频问题，跑一周看未命中清单，再补。一次导入几百条会有一半没人问。

## 身份与限额

默认按请求头 `X-Student-Id` 识别（7 位，2 字母 + 5 数字），设备 UUID 与 IP 作为辅助。**这只是防手滑，不是安全机制**——学生改个号就能绕过去。

要真正校验身份，接你校现有的登录态：同域反代 + 一个 `whoami` 接口，后端只信任反代传过来的头。本项目不做第二套密码。

## 隐私

- 不采集成绩、消费、门禁、WiFi 记录等个人数据。
- 提问流水只落 `data/qa_log.jsonl`，用于统计未命中和补资料；`.gitignore` 已排除。
- 审批页有责任声明：内容由审核人确认，系统只做留痕与流转。

## 许可

GPL-3.0，见 `LICENSE`。书院名称、院徽、真实资料与问答内容不在本许可范围内，见 `NOTICE`。
