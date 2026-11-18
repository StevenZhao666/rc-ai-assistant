"""生成《書院資料庫》說明 PPT（繁體，面向同學／助教／同事）。

    ./.venv/Scripts/python.exe scripts/build_db_deck.py

輸出：deliverables/結構圖/書院資料庫-說明-繁.pptx
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deliverables" / "結構圖" / "書院資料庫-說明-繁.pptx"
OUT.parent.mkdir(parents=True, exist_ok=True)

RED = RGBColor(0x88, 0x07, 0x0F)
DARK = RGBColor(0x6B, 0x05, 0x0C)
INK = RGBColor(0x1F, 0x1B, 0x1C)
DIM = RGBColor(0x5F, 0x58, 0x54)
LINE = RGBColor(0xDE, 0xD6, 0xD0)
CREAM = RGBColor(0xFC, 0xFA, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SOFT_RED = RGBColor(0xFD, 0xF3, 0xF2)
BLUE_BG = RGBColor(0xEE, 0xF5, 0xFC)
GREEN_BG = RGBColor(0xEF, 0xF8, 0xF2)
AMBER_BG = RGBColor(0xFF, 0xF7, 0xE9)
GRAY_BG = RGBColor(0xF3, 0xEF, 0xEC)

FONT = "Microsoft JhengHei"
W, H = 13.333, 7.5


def deck():
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    return prs


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def rect(s, x, y, w, h, fill=None, line=None, radius=True, lw=Pt(1)):
    shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                             Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = lw
    shp.shadow.inherit = False
    if radius:
        shp.adjustments[0] = 0.07
    return shp


def text(s, x, y, w, h, body, size=15, color=INK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.2):
    box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, 0)
    for i, line in enumerate(body.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        r = p.add_run(); r.text = line
        r.font.name = FONT; r.font.size = Pt(size)
        r.font.bold = bold; r.font.color.rgb = color
    return box


def bg(s, color=CREAM):
    rect(s, 0, 0, W, H, fill=color, radius=False)


def kicker(s, t):
    text(s, 0.62, 0.34, 8, 0.3, t, size=12, color=RED, bold=True)


def title(s, t, size=30):
    text(s, 0.6, 0.64, 12.1, 0.72, t, size=size, bold=True)


def lead(s, t, size=13):
    text(s, 0.62, 1.36, 12, 0.42, t, size=size, color=DIM)


def card(s, x, y, w, h, head, body, fill=WHITE, border=LINE, hsize=16, bsize=12):
    rect(s, x, y, w, h, fill=fill, line=border)
    text(s, x + 0.22, y + 0.16, w - 0.44, 0.36, head, size=hsize, bold=True)
    if body:
        text(s, x + 0.22, y + 0.62, w - 0.44, h - 0.76, body, size=bsize, color=DIM, spacing=1.35)


# ── 1 封面 ────────────────────────────────────────────────
def s1(prs):
    s = blank(prs); bg(s, RED)
    rect(s, 0, 5.5, W, 2.0, fill=DARK, radius=False)
    text(s, 0.95, 1.5, 11, 0.5, "張崑崙書院", size=17, color=RGBColor(0xFF, 0xD9, 0xD7))
    text(s, 0.9, 2.05, 11.6, 1.0, "書院資料庫", size=52, color=WHITE, bold=True)
    text(s, 0.95, 3.2, 11.4, 1.1,
         "一個查得到原文、說得清出處的資料庫\n以及它和現成知識庫產品的差別",
         size=21, color=RGBColor(0xFF, 0xE4, 0xE2), spacing=1.35)
    text(s, 0.95, 5.9, 11, 0.4, "2026 年 11 月　·　給同學、助教與同事的說明", size=13,
         color=RGBColor(0xDC, 0xAD, 0xAA))


# ── 2 三个缺口 ────────────────────────────────────────────
def s2(prs):
    s = blank(prs); bg(s)
    kicker(s, "一 · 問題")
    title(s, "現在的三個缺口")
    lead(s, "不是缺一個聊天機器人，是缺一份說得清出處的資料。")

    items = [
        ("同學查不到", "規章在 PDF 裡、通知在群組裡。\n同一件事，問三個人有三種說法。"),
        ("助教重複回答", "每年新生問同樣的問題；\n換一屆，全部再講一次。"),
        ("外面接不上", "別的專案、同學自己的 AI 想用書院資料，\n只能自己去爬網頁。"),
    ]
    w, gap = 3.94, 0.14
    for i, (h, b) in enumerate(items):
        card(s, 0.62 + i * (w + gap), 2.0, w, 2.25, h, b,
             fill=SOFT_RED, border=RGBColor(0xE6, 0xC6, 0xC3), hsize=17, bsize=12)

    text(s, 0.62, 4.75, 12, 0.9,
         "崑崑先解決了一部分：能回答、能給出處。\n"
         "但要長期撐住，靠的是底下的資料庫，不是再買一個聊天工具。",
         size=15, spacing=1.4)


# ── 3 现状 ───────────────────────────────────────────────
def s3(prs):
    s = blank(prs); bg(s)
    kicker(s, "二 · 現狀")
    title(s, "已經在跑，資料也已經在整理")
    lead(s, "不是從零開始；問題是資料還散在幾張表裡，撐不起對外服務。")

    stats = [("115", "已發布問答"), ("368", "條原文條款"), ("240", "條學生手冊"),
             ("128", "條房間使用規定")]
    for i, (n, lab) in enumerate(stats):
        x = 0.62 + i * 2.98
        rect(s, x, 2.0, 2.84, 1.55, fill=WHITE, line=LINE)
        text(s, x + 0.22, 2.12, 2.4, 0.75, n, size=40, bold=True, color=RED)
        text(s, x + 0.22, 2.95, 2.4, 0.4, lab, size=12, color=DIM)

    text(s, 0.62, 3.95, 12.1, 1.0,
         "已有四項能力：答案追到條款、審核留痕、時效分層（A 穩定 / B 年度 / C 實時）、答不上來轉人工。\n"
         "這些是責任鏈，不是模型能力——換哪個模型都不會自動有。", size=15, spacing=1.45)


# ── 4 四类内容 ────────────────────────────────────────────
def s4(prs):
    s = blank(prs); bg(s)
    kicker(s, "三 · 內容")
    title(s, "資料庫要放四類東西")
    lead(s, "同一個入口查得到，但四類的規矩不一樣。")

    data = [
        ("公文", "規章、通知、指引、表格", "帶版本；舊版不刪；\n新舊版本可對照", BLUE_BG),
        ("條目", "問答、術語、常見誤解", "每條指向條款；\n審核後才上架", SOFT_RED),
        ("院生作品", "Skill、工具、專案、文章", "作者同意才公開；\n只顯示名字", GREEN_BG),
        ("其他資源", "官網、學生自建站、工具", "標明是否官方；\n只給連結不轉述", AMBER_BG),
    ]
    w, gap = 2.94, 0.13
    for i, (h, sub, rule, fill) in enumerate(data):
        x = 0.62 + i * (w + gap)
        rect(s, x, 1.98, w, 2.7, fill=fill, line=LINE)
        text(s, x + 0.2, 2.1, w - 0.4, 0.42, h, size=18, bold=True)
        text(s, x + 0.2, 2.56, w - 0.4, 0.6, sub, size=11.5, color=DIM)
        text(s, x + 0.2, 3.3, w - 0.4, 1.2, rule, size=12, color=INK, spacing=1.35)

    text(s, 0.62, 4.95, 12, 0.9,
         "四類共用一套狀態：草稿 → 待審 → 發布 → 下架 → 歸檔。\n"
         "任何一類，都不允許「上傳即生效」。", size=15, spacing=1.4)


# ── 5 对谁有用 ────────────────────────────────────────────
def s5(prs):
    s = blank(prs); bg(s)
    kicker(s, "四 · 誰受惠")
    title(s, "不同的人，拿到不同的東西")
    lead(s, "同一個庫，四種用法。")

    rows = [
        ("同學", "問得到，還能點開原文", "不必再問「這是誰說的」；遇到規定、費用、期限，能自己核對。", SOFT_RED),
        ("助教 / 博士生", "重複的問題不用再答", "新生常見問題交給系統；自己查舊版本、查條款更快。", BLUE_BG),
        ("辦公室同事", "少接重複電話", "答覆有依據、有版本；問的人自己看得到出處。", GREEN_BG),
        ("做專案的人", "有現成接口可用", "只讀 API 與 MCP，不必再爬網頁、抄資料。", AMBER_BG),
    ]
    y = 1.95
    for h, sub, body, fill in rows:
        rect(s, 0.62, y, 12.1, 1.12, fill=fill, line=LINE)
        text(s, 0.85, y + 0.14, 3.0, 0.4, h, size=16, bold=True)
        text(s, 3.85, y + 0.12, 4.2, 0.4, sub, size=13, bold=True, color=INK)
        text(s, 3.85, y + 0.55, 8.6, 0.5, body, size=12, color=DIM)
        y += 1.24


# ── 6 现成产品能做什么 ────────────────────────────────────
def s6(prs):
    s = blank(prs); bg(s)
    kicker(s, "五 · 現成產品")
    title(s, "現成的知識庫產品，長處很明確")
    lead(s, "先把優點說清楚，再談我們為什麼還要做。")

    rows = [
        ("上手快", "上傳文件就能問，不用寫程式；同事自己就能用。"),
        ("渠道現成", "微信、網頁、小程式都有入口，不必自己開發。"),
        ("免運維", "模型、索引、儲存都由廠商打理，沒有機器要顧。"),
        ("中文體驗好", "中文問答、文件解析都成熟，省去調校。"),
    ]
    y = 1.95
    for h, b in rows:
        rect(s, 0.62, y, 12.1, 1.05, fill=WHITE, line=LINE)
        text(s, 0.88, y + 0.14, 3.2, 0.4, h, size=16, bold=True)
        text(s, 4.1, y + 0.14, 8.3, 0.7, b, size=12.5, color=DIM, spacing=1.3)
        y += 1.18

    text(s, 0.62, 6.65, 12, 0.4, "所以：如果只要「能問能答」，用現成產品最快、最省人。",
         size=14, color=INK, bold=True)


# ── 7 差别：自主可控 ──────────────────────────────────────
def s7(prs):
    s = blank(prs); bg(s)
    kicker(s, "六 · 差別")
    title(s, "差別不在答得好不好，在「東西在誰手上」")
    lead(s, "四件事，決定這個庫能不能長期由書院自己維護。")

    rows = [
        ("資料歸屬", "存在廠商的知識庫裡", "存在書院自己的資料庫；廠商換了，資料還在"),
        ("依據", "給文件名或片段", "給到第 3.2 條，可點開原文"),
        ("版本與責任", "沒有版本概念", "誰審的、哪一版、何時失效，都留痕"),
        ("開關與遷移", "共享連結，難限流", "接口可開可關、配額可調；換雲端上層不用重寫"),
    ]
    x0, y0 = 0.62, 1.95
    widths = [2.7, 4.3, 5.1]
    heads = ["", "現成知識庫", "書院自己的庫"]
    for j, hd in enumerate(heads):
        x = x0 + sum(widths[:j])
        rect(s, x, y0, widths[j] - 0.08, 0.52, fill=GRAY_BG, line=LINE, radius=False)
        text(s, x + 0.16, y0 + 0.1, widths[j] - 0.4, 0.32, hd, size=12, bold=True, color=DIM)

    for i, (k, a, b) in enumerate(rows):
        y = y0 + 0.52 + i * 0.98
        rect(s, x0, y, sum(widths) - 0.08, 0.9, fill=WHITE if i % 2 == 0 else CREAM,
             line=LINE, radius=False)
        text(s, x0 + 0.16, y + 0.28, widths[0] - 0.3, 0.42, k, size=13.5, bold=True)
        text(s, x0 + widths[0] + 0.1, y + 0.26, widths[1] - 0.35, 0.62, a, size=12, color=DIM)
        text(s, x0 + widths[0] + widths[1] + 0.1, y + 0.26, widths[2] - 0.4, 0.62, b, size=12)

    text(s, 0.62, 6.7, 12, 0.4,
         "一句話：現成產品解決「怎麼答」，我們要解決「答了之後，東西還在不在自己手上」。",
         size=13, color=RED, bold=True)


# ── 8 分层 ───────────────────────────────────────────────
def s8(prs):
    s = blank(prs); bg(s)
    kicker(s, "七 · 怎麼配合")
    title(s, "不是二選一：能用買的用買的")
    lead(s, "把「買得到」和「買不到」分開。")

    rect(s, 0.62, 1.92, 12.1, 1.75, fill=SOFT_RED, line=RGBColor(0xE6, 0xC6, 0xC3))
    text(s, 0.86, 2.04, 6, 0.4, "書院自己的（買不到）", size=15, bold=True, color=RED)
    text(s, 0.86, 2.46, 11.5, 1.05,
         "條款原文與版本　·　問答與審核　·　院生作品與授權　·　配額政策與審計要求\n"
         "這四類內容、四條規矩，任何產品都不會替書院定。", size=12.5, color=INK, spacing=1.4)

    rect(s, 0.62, 3.86, 12.1, 1.0, fill=WHITE, line=LINE)
    text(s, 0.86, 3.98, 11.6, 0.8,
         "中間一層：只讀 API（4 個）＋ MCP　→　給崑崑、給別的專案、給同學的 AI\n"
         "統一限流、日誌與鑑權；想換底座，這一層不用改。", size=12, color=DIM, spacing=1.35)

    rect(s, 0.62, 5.0, 12.1, 1.55, fill=BLUE_BG, line=RGBColor(0xCC, 0xDE, 0xF2))
    text(s, 0.86, 5.12, 6, 0.4, "可以直接用雲服務的（買得到）", size=15, bold=True,
         color=RGBColor(0x1B, 0x5F, 0xA8))
    text(s, 0.86, 5.54, 11.5, 0.9,
         "雲資料庫（PostgreSQL）　·　物件存儲（放 PDF 與附件）　·　CDN\n"
         "免運維、有備份；用多少付多少。", size=12.5, color=INK, spacing=1.4)


# ── 9 三步走 ─────────────────────────────────────────────
def s9(prs):
    s = blank(prs); bg(s)
    kicker(s, "八 · 怎麼做")
    title(s, "三步走，每一步都能停")
    lead(s, "先做最有價值、最容易的部分；不追求一次到位。")

    steps = [
        ("第一步 · 現在", "本地把結構立起來", "四類內容進同一個庫；\n不動現有服務，出問題隨時退回。", "0 元"),
        ("第二步 · 對外", "換託管資料庫 + 只讀接口", "雲資料庫 + 物件存儲；\n先給一兩位同學測試 key。", "每月百元級"),
        ("第三步 · 開放", "MCP 給同學的 AI", "四個只讀工具；作品與資源陸續上架。", "按量"),
    ]
    w, gap = 3.94, 0.14
    for i, (k, h, b, cost) in enumerate(steps):
        x = 0.62 + i * (w + gap)
        rect(s, x, 1.95, w, 3.2, fill=WHITE, line=LINE)
        text(s, x + 0.22, 2.08, w - 0.44, 0.32, k, size=12, color=RED, bold=True)
        text(s, x + 0.22, 2.44, w - 0.44, 0.62, h, size=15, bold=True)
        text(s, x + 0.22, 3.18, w - 0.44, 1.5, b, size=12, color=DIM, spacing=1.4)
        text(s, x + 0.22, 4.66, w - 0.44, 0.32, cost, size=12, bold=True,
             color=RGBColor(0x1C, 0x7C, 0x54))

    text(s, 0.62, 5.45, 12, 0.9,
         "每一步都能停在原地使用：第一步做完，內部就能查；第二步做完，對外能接；\n"
         "第三步才涉及同學的 AI。任何一步覺得不對，退回上一步即可。", size=13, color=DIM, spacing=1.4)


# ── 10 收尾 ──────────────────────────────────────────────
def s10(prs):
    s = blank(prs); bg(s, RED)
    text(s, 0.95, 1.9, 11.5, 0.5, "一句話", size=15, color=RGBColor(0xFF, 0xD9, 0xD7))
    text(s, 0.9, 2.4, 11.8, 1.7,
         "買得到「會答」，\n買不到「說得清、管得住、拿得走」。",
         size=34, color=WHITE, bold=True, spacing=1.3)
    text(s, 0.95, 4.6, 11.6, 1.0,
         "底座用買的，內容與規矩自己定；\n先在本地做，不影響現在的服務。",
         size=16, color=RGBColor(0xFF, 0xE4, 0xE2), spacing=1.45)
    text(s, 0.95, 6.25, 11, 0.4, "下一步：結構定稿 → 本地驗證 → 再談對外", size=12,
         color=RGBColor(0xDC, 0xAD, 0xAA))


def main():
    prs = deck()
    for fn in (s1, s2, s3, s4, s5, s6, s7, s8, s9, s10):
        fn(prs)
    prs.save(OUT)
    print("已生成", OUT, "共", len(prs.slides._sldIdLst), "頁")


if __name__ == "__main__":
    main()
