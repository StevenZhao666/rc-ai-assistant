# 崑崑 UI 改版 · 设计说明

状态：**样本待确认**，`app/static/index.html` 尚未改动。

## 文件

| 文件 | 用途 |
|---|---|
| `index.html` | 四方案并排对照页（A/B/C/D） |
| `variant-a/b/c/d.html` | 早期静态样张，保留作对照 |
| `build-final.py` | 从 `app/static/index.html` 生成 `final-d.html`：只换 `<style>` 和 `<header>`，`<script>` 原样复制 |
| `final-d.html` | 终稿（产物，不要手改） |
| `preview_server.py` | 预览服务器：`:8002` 出 `final-d.html`，`/api/*` `/img/*` 反代到 `:8001` |
| `ask_kimi.py` / `kimi_prompt.md` / `kimi_ui.md` | Kimi K3.1 第二意见 |

## 为什么是 D

A 静谧纸本（学术但冷）、B 暗室微光（太酷，学生会有距离）、C 暖色卡片（稳，但平淡）。
D 玻璃暖光保留了 Fuyo 网页端那套「渐变 + 玻璃 + 等宽微标签」的质感，但换成书院红与暖白。

## D 的规范（改样式只动这些）

- 色：底 `#FAF8F5`，正文卡 `#FFFFFF`，用户气泡 `#E9D6DD`／边框 `#BE8B9D`，主色 `#8C1220`
- 字：正文 16 / 界面 15.5 / 辅助 12 / 元信息 10.5（不低于 10.5）
- 圆角：16（气泡与卡）/ 12（依据控件）/ 8（按钮）/ 999（只给输入框与快捷问题）
- 间距：8 的倍数；`main` 底 padding `196px + safe-area`
- 玻璃只用于顶栏与底栏，**内容区一律实底**（Kimi 关键意见，见下）

## Kimi 意见的采纳情况

采纳：
1. 内容区去玻璃改实底 → 可读性与「像官方文件」的可信感
2. 用户气泡不能靠透明度 → 改实色，原来 11% 酒红对比仅 1.2:1
3. 删网格、双渐变降为单层 5%
4. 辅助字不小于 12px（元信息 10.5 例外，仅用于版本号这类）
5. 触控：快捷问题与依据控件 ≥40px，发送按钮 44px，补 `:focus-visible`
6. 顶栏两行：第一行头像＋标题＋语言，第二行学号＋状态

未采纳：
- 发送按钮改纯色 —— 已改纯色，采纳
- 「圆角统一 16/12/4」—— 用了 16/12/8，因为按钮 4px 太硬

## 两个待定（需用户拍板）

1. 「AI 生成 · 僅供參考」在顶栏 `#badge2`、免责条、欢迎语出现三次。免责条不能删（法务）。是否隐藏顶栏那一个。
2. 「依據 N · 點開看原文」在展开后文案不变。修复需改 JS 约 3 行（新增 `citeHintOpen` + `toggle` 监听）。

## 构建与预览

```bash
# 重新生成终稿（改 CSS 后必跑）
python design/ui-redesign/build-final.py

# 起预览（后端需先跑在 8001）
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
python design/ui-redesign/preview_server.py     # → http://127.0.0.1:8002/
```

`build-final.py` 结束会逐条打印 16 个 id 的存在检查，任何一个 MISSING 就说明改坏了。

## 介绍视频

`media/video/` 下：

| 文件 | 说明 |
|---|---|
| `kunkun-intro-1080x1920.mp4` | 成片：1080×1920 / 30fps / 34s / 2.3MB |
| `render_intro.py` | Pillow 逐帧渲染器；改 `BEATS` 里的时间轴即可调节奏 |
| `ui-home.png` / `ui-cite.png` | 从 `:8001` 真实页面截的底图（非重绘） |
| `contact.png` | 10 帧抽样拼版，改完先看这个 |

结构：`01 結構`（學生端 → /api/ask → BM25 → 模型鏈 → 答案+出處）／`02 效果`（首屏、引用卡近景、规格数字）。

坑：**`goto_url` 之后 device metrics 会被重置**，页面会按默认宽度渲染，量出来的 DOM 坐标全错。截图前必须重设 `Emulation.setDeviceMetricsOverride` 并断言 `window.innerWidth === 420`。另外 Consolas 不能渲染中文，会出豆腐块，中文标签一律走 `cn_track()` + 微軟正黑體。

## 验收清单（替换源码前必须全过）
- [ ] 16 个 id 全在
- [ ] 420 / 360 宽无横向溢出，标题不截断
- [ ] 真实问答：答案 + 引用卡 + 👍👎 都正常
- [ ] 引用展开、语言切换（繁/简/EN）、学号弹窗、429 降级文案正常
- [ ] 三套测试：`selftest.py`（12）、`regress_personas.py`（16）、`test_review.py`（13）
