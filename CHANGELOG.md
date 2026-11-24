# Changelog

## v0.2.0 — 2026-11-24

学生端界面改版（方案 D「玻璃暖光」）。仅动 `app/static/index.html`，回答链路、检索、限流、审批后台均未改。

### 变更

- 底色改暖白 `#FAF8F5` + 单层酒红径向渐变（5%）；移除网格纹理与双渐变（影响正文可读性）
- 顶栏两行：头像 + 标题 + 语言切换 / 学号 + 状态；毛玻璃只用于顶栏与底栏
- 消息气泡改**实底**：AI 白卡 `#FFFFFF` + `#E7E0DA` 边框；用户 `#E9D6DD` + `#BE8B9D` 边框（原半透明酒红 11%，对比仅 1.2:1）
- 依据卡改实底 + 12px 圆角；展开后文案由「點開看原文」切为「收起原文」（i18n 新增 `citeHintOpen`，三语）
- 顶栏不再重复「AI 生成 · 僅供參考」：`#badge2` 保留元素、改 `display:none`（JS 有 `textContent` 写入，删 DOM 会抛错）
- 字号下限：正文 16 / 界面 15.5 / 辅助 12 / 元信息 10.5；触控目标 ≥40px；补 `:focus-visible`
- `#log` 底部留白改为 `196px + env(safe-area-inset-bottom)`

### 验证

- 16 个 JS 依赖的 id 全部保留
- 420 / 360 宽无横向溢出，标题不截断
- 真实问答、引用展开、反馈按钮、语言切换、学号弹窗均正常
- `scripts/selftest.py` 12/12；`tests/test_review.py` 13/13；`tests/regress_personas.py` 15/16
  - 未过一条：wifi 名称/密码题，模型用自身知识作答（`mode=llm`）而非按预期走 `fallback_gap`。可复现 2/2，与本次改动无关（`git diff` 仅 `index.html`，回答链路不读该文件），属知识库缺 wifi 条目。
