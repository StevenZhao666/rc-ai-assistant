"""生成《書院資料庫 · 院長匯報》PPT（繁體）。

    ./.venv/Scripts/python.exe scripts/build_dean_deck.py

輸出：deliverables/結構圖/院長匯報-書院資料庫-繁.pptx
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deliverables" / "結構圖" / "院長匯報-書院資料庫-繁.pptx"
OUT.parent.mkdir(parents=True, exist_ok=True)

RED = RGBColor(0x88, 0x07, 0x0F)
DARK = RGBColor(0x6B, 0x05, 0x0C)
INK = RGBColor(0x24, 0x1F, 0x20)
DIM = RGBColor(0x6F, 0x68, 0x64)
LINE = RGBColor(0xE2, 0xDB, 0xD6)
CREAM = RGBColor(0xFB, 0xF9, 0xF7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SOFT_RED = RGBColor(0xFD, 0xF4, 0xF3)
BLUE_BG = RGBColor(0xEF, 0xF5, 0xFC)
GREEN_BG = RGBColor(0xF0, 0xF8, 0xF3)
AMBER_BG = RGBColor(0xFF, 0xF7, 0xEA)
GRAY_BG = RGBColor(0xF4, 0xF1, 0xEF)

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
        shp.adjustments[0] = 0.08
    return shp


def text(s, x, y, w, h, body, size=14, color=INK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.12):
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
    text(s, 0.62, 0.34, 8, 0.3, t, size=11, color=RED, bold=True)


def title(s, t, size=27):
    text(s, 0.6, 0.66, 12.1, 0.7, t, size=size, bold=True)


def lead(s, t, size=12):
    text(s, 0.62, 1.34, 12, 0.4, t, size=size, color=DIM)


def card(s, x, y, w, h, head, body, fill=WHITE, border=LINE, hsize=14, bsize=10.5):
    rect(s, x, y, w, h, fill=fill, line=border)
    text(s, x + 0.2, y + 0.16, w - 0.4, 0.34, head, size=hsize, bold=True)
    if body:
        text(s, x + 0.2, y + 0.58, w - 0.4, h - 0.7, body, size=bsize, color=DIM, spacing=1.3)


# ── 1 封面 ────────────────────────────────────────────────
def s1(prs):
    s = blank(prs); bg(s, RED)
    rect(s, 0, 5.55, W, 1.95, fill=DARK, radius=False)
    text(s, 0.95, 1.55, 11, 0.5, "張崑崙書院 · 資料庫建設計畫", size=16,
         color=RGBColor(0xFF, 0xD9, 0xD7))
    text(s, 0.9, 2.15, 11.6, 1.0, "書院資料庫", size=48, color=WHITE, bold=True)
    text(s, 0.95, 3.25, 11, 0.9,
         "為什麼不能只用騰訊現成的知識庫\n以及我們打算怎麼做", size=20,
         color=RGBColor(0xFF, 0xE3, 0xE1))
    text(s, 0.95, 5.95, 11, 0.4, "匯報人：趙瀚陽　·　2026 年 11 月", size=12,
         color=RGBColor(0xD9, 0xA9, 0xA6))


# ── 2 三个问题 ────────────────────────────────────────────
def s2(prs):
    s = blank(prs); bg(s)
    kicker(s, "一 · 問題")
    title(s, "現在的三個缺口")
    lead(s, "不是缺一個聊天機器人，是缺一份「說得清出處」的資料。")

    items = [
        ("學生問不到", "規章在 PDF 裡、通知在群裡。\n同一件事，三個人給三個說法。"),
        ("老師查不到", "「去年那版怎麼寫的？」\n沒有人能立刻拿出舊版本。"),
        ("外面接不上", "別的項目、同學的 AI 想用書院資料，\n只能自己爬網頁。"),
    ]
    w, gap = 3.94, 0.14
    for i, (h, b) in enumerate(items):
        card(s, 0.62 + i * (w + gap), 2.0, w, 2.2, h, b, fill=SOFT_RED, border=RGBColor(0xE8, 0xC9, 0xC6))

    text(s, 0.62, 4.62, 12, 0.9,
         "崑崑先解決了第一個缺口的一部分：能回答、能給出出處。\n"
         "但要長期扛住，需要的是底下的資料庫，而不是再買一個聊天工具。",
         size=13, color=INK, spacing=1.35)


# ── 3 已经有的 ────────────────────────────────────────────
def s3(prs):
    s = blank(prs); bg(s)
    kicker(s, "二 · 現狀")
    title(s, "崑崑已經在跑，資料也已經在整理")
    lead(s, "不是從零開始；問題是現在的資料還散在幾張表裡，撐不起對外服務。")

    stats = [("115", "已發布問答"), ("368", "條規章原文條款"), ("240", "條來自學生手冊"),
             ("128", "條來自房間使用規定")]
    for i, (n, lab) in enumerate(stats):
        x = 0.62 + i * 2.98
        rect(s, x, 2.0, 2.84, 1.5, fill=WHITE, line=LINE)
        text(s, x + 0.2, 2.14, 2.4, 0.7, n, size=36, bold=True, color=RED)
        text(s, x + 0.2, 2.9, 2.4, 0.4, lab, size=10.5, color=DIM)

    text(s, 0.62, 3.86, 12, 0.9,
         "已具備：答案可追到條款、審核留痕、時效分層（A 穩定 / B 年度 / C 實時）、\n"
         "答不上來轉人工。這些都是「責任鏈」，不是模型能力。", size=13, spacing=1.35)


# ── 4 四类内容 ────────────────────────────────────────────
def s4(prs):
    s = blank(prs); bg(s)
    kicker(s, "三 · 內容")
    title(s, "資料庫要放四類東西")
    lead(s, "同一個入口查得到，但四類的規則不一樣。")

    data = [
        ("公文", "規章、通知、指引、表格", "帶版本；舊版不能刪；\n新舊版本要能對照", BLUE_BG),
        ("條目", "問答、術語、常見誤解", "每條指向條款；\n要審核才能上架", SOFT_RED),
        ("院生作品", "Skill、工具、專案、文章", "作者同意才公開；\n只顯示名字，不顯示年級", GREEN_BG),
        ("其他資源", "官方網站、學生自建站、工具", "標明是否官方；\n只給連結，不轉述內容", AMBER_BG),
    ]
    w, gap = 2.94, 0.13
    for i, (h, sub, rule, fill) in enumerate(data):
        x = 0.62 + i * (w + gap)
        rect(s, x, 1.95, w, 2.55, fill=fill, line=LINE)
        text(s, x + 0.18, 2.08, w - 0.36, 0.4, h, size=16, bold=True)
        text(s, x + 0.18, 2.5, w - 0.36, 0.6, sub, size=10, color=DIM)
        text(s, x + 0.18, 3.2, w - 0.36, 1.1, rule, size=10, color=INK, spacing=1.3)

    text(s, 0.62, 4.75, 12, 0.9,
         "四類共用一套狀態：草稿 → 待審 → 發布 → 下架 → 歸檔。\n"
         "任何一類，都不允許「上傳即生效」。", size=13, spacing=1.35)


# ── 5 腾讯能做什么 ────────────────────────────────────────
def s5(prs):
    s = blank(prs); bg(s)
    kicker(s, "四 · 騰訊的方案")
    title(s, "騰訊能做的，其實不少")
    lead(s, "先把對方的優點講清楚，再談差別。")

    rows = [
        ("ima 知識庫", "上傳文件就能問，微信、客戶端、小程序都能用；\n中文體驗好，老師自己就能上手。"),
        ("騰訊元器", "低代碼做智能體，有 H5、小程序、API；\n換模型、改提示詞不用寫程式。"),
        ("雲資料庫 / COS", "託管 MySQL、PostgreSQL、物件存儲；\n免運維、有備份，比自己裝機器省事。"),
    ]
    y = 1.95
    for h, b in rows:
        rect(s, 0.62, y, 12.1, 1.15, fill=WHITE, line=LINE)
        text(s, 0.85, y + 0.16, 2.6, 0.4, h, size=14, bold=True)
        text(s, 3.6, y + 0.14, 8.8, 0.9, b, size=11, color=DIM, spacing=1.3)
        y += 1.28

    text(s, 0.62, 5.95, 12, 0.5, "所以：如果只要「能問能答」，用它們最快，也最省人。",
         size=13, color=INK, bold=True)


# ── 6 差别 ───────────────────────────────────────────────
def s6(prs):
    s = blank(prs); bg(s)
    kicker(s, "五 · 差別")
    title(s, "差別不在「答得好不好」，在「出事時說得清嗎」")
    lead(s, "書院要對學生負責，這四件事不能靠模型自覺。")

    rows = [
        ("答案依據", "給文件名", "給到第 3.2 條，可點開原文"),
        ("內容審核", "上傳即生效", "認領、通過、留痕，可追責"),
        ("版本與失效", "沒有版本概念", "舊版保留；換版時標記受影響問答"),
        ("對外使用", "共享連結，難限流", "每個調用方可限額、可審計、可停用"),
    ]
    x0, y0 = 0.62, 2.0
    widths = [2.6, 4.4, 5.1]
    heads = ["", "現成知識庫", "書院資料庫"]
    for j, hd in enumerate(heads):
        x = x0 + sum(widths[:j])
        rect(s, x, y0, widths[j] - 0.08, 0.5, fill=GRAY_BG, line=LINE, radius=False)
        text(s, x + 0.16, y0 + 0.1, widths[j] - 0.4, 0.3, hd, size=11, bold=True, color=DIM)

    for i, (k, a, b) in enumerate(rows):
        y = y0 + 0.5 + i * 0.92
        rect(s, x0, y, sum(widths) - 0.08, 0.84, fill=WHITE if i % 2 == 0 else CREAM,
             line=LINE, radius=False)
        text(s, x0 + 0.16, y + 0.26, widths[0] - 0.3, 0.4, k, size=12, bold=True)
        text(s, x0 + widths[0] + 0.1, y + 0.24, widths[1] - 0.35, 0.6, a, size=11, color=DIM)
        text(s, x0 + widths[0] + widths[1] + 0.1, y + 0.24, widths[2] - 0.4, 0.6, b, size=11)

    text(s, 0.62, 6.62, 12, 0.4,
         "一句話：它們解決「怎麼答」，我們要解決「憑什麼這樣答」。", size=12, color=RED, bold=True)


# ── 7 分层 ───────────────────────────────────────────────
def s7(prs):
    s = blank(prs); bg(s)
    kicker(s, "六 · 怎麼配合")
    title(s, "不是二選一：騰訊做底座，書院做內容")
    lead(s, "把「買得到的」和「買不到的」分開。")

    # 上：内容层
    rect(s, 0.62, 1.9, 12.1, 1.85, fill=SOFT_RED, line=RGBColor(0xE8, 0xC9, 0xC6))
    text(s, 0.85, 2.02, 4, 0.4, "書院自己的（買不到）", size=13, bold=True, color=RED)
    text(s, 0.85, 2.44, 11.6, 1.2,
         "條款原文與版本　·　問答與審核　·　院生作品與授權　·　配額政策與審計要求\n"
         "上面的四類內容、四條規矩，任何產品都不會替我們定。", size=11.5, color=INK, spacing=1.35)

    # 中：接口层（夹在内容与底座之间）
    rect(s, 0.62, 3.95, 12.1, 1.0, fill=WHITE, line=LINE)
    text(s, 0.85, 4.08, 11.6, 0.75,
         "中間一層：只讀 API（4 個）＋ MCP　→　給崑崑、給別的項目、給同學的 AI" + chr(10)
         + "統一限流、日誌與鑑權；想換底座，這一層不用改。", size=11, color=DIM, spacing=1.3)

    # 下：底座
    rect(s, 0.62, 5.12, 12.1, 1.55, fill=BLUE_BG, line=RGBColor(0xCF, 0xE0, 0xF3))
    text(s, 0.85, 5.24, 5, 0.4, "可以直接用騰訊雲的（買得到）", size=13, bold=True, color=RGBColor(0x1B, 0x5F, 0xA8))
    text(s, 0.85, 5.66, 11.6, 0.9,
         "雲資料庫（PostgreSQL）　·　物件存儲 COS（放 PDF 與附件）　·　CDN" + chr(10)
         + "免運維、有備份；用多少付多少。", size=11.5, color=INK, spacing=1.35)


# ── 8 三阶段 ─────────────────────────────────────────────
def s8(prs):
    s = blank(prs); bg(s)
    kicker(s, "七 · 怎麼做")
    title(s, "三步走，每一步都能停")
    lead(s, "先做最容易、最有價值的部分；不追求一次到位。")

    steps = [
        ("第一步 · 現在", "本地先把結構立起來",
         "公文 / 條目 / 作品 / 資源四類進同一個庫；\n不動現有服務，出問題隨時退回。", "0 元"),
        ("第二步 · 對外", "換託管資料庫 + 開只讀接口",
         "雲資料庫 + COS；先給一兩位同學測試 key；\n有配額、有日誌。", "每月百元級"),
        ("第三步 · 開放", "MCP 給同學的 AI",
         "四個只讀工具；作品與資源陸續上架；\n按使用情況再擴。", "按量"),
    ]
    w, gap = 3.94, 0.14
    for i, (k, h, b, cost) in enumerate(steps):
        x = 0.62 + i * (w + gap)
        rect(s, x, 1.95, w, 3.15, fill=WHITE, line=LINE)
        text(s, x + 0.2, 2.08, w - 0.4, 0.3, k, size=11, color=RED, bold=True)
        text(s, x + 0.2, 2.42, w - 0.4, 0.6, h, size=14, bold=True)
        text(s, x + 0.2, 3.1, w - 0.4, 1.5, b, size=10.5, color=DIM, spacing=1.35)
        text(s, x + 0.2, 4.62, w - 0.4, 0.3, cost, size=11, bold=True, color=RGBColor(0x1C, 0x7C, 0x54))

    text(s, 0.62, 5.42, 12, 0.8,
         "每一步都可以停在原地使用：第一步做完，內部就能查；第二步做完，對外能接；\n"
         "第三步才涉及同學的 AI。任何一步覺得不對，退回上一步即可。", size=11.5, color=DIM, spacing=1.35)


# ── 9 需要支持 ───────────────────────────────────────────
def s9(prs):
    s = blank(prs); bg(s)
    kicker(s, "八 · 需要支持")
    title(s, "需要院長支持的三件事")
    lead(s, "技術上我們能推進；這三件卡在書院這邊。")

    rows = [
        ("① 網址與安全憑證", "給一個書院子域（例如 cklc.um.edu.mo 之下）",
         "現在的位址是 IP，沒有證書；接登錄、做對外服務都過不去。"),
        ("② 身份查詢接口", "一份 whoami：確認「這個人是不是本院學生」",
         "沒有它，投稿、作品上架、限額都只能靠自填學號，等於沒有。"),
        ("③ 審核人力", "一到兩位同事負責通過內容",
         "資料庫的價值在審核；沒人審，資料再多也不敢對外。"),
    ]
    y = 1.95
    for h, need, why in rows:
        rect(s, 0.62, y, 12.1, 1.35, fill=WHITE, line=LINE)
        text(s, 0.85, y + 0.16, 4.2, 0.4, h, size=14, bold=True, color=RED)
        text(s, 0.85, y + 0.62, 5.2, 0.6, need, size=11)
        text(s, 6.3, y + 0.3, 6.2, 0.9, why, size=10.5, color=DIM, spacing=1.3)
        y += 1.5

    text(s, 0.62, 6.55, 12, 0.4, "這三件不需要經費，只需要決定。", size=12, color=INK, bold=True)


# ── 10 结尾 ──────────────────────────────────────────────
def s10(prs):
    s = blank(prs); bg(s, RED)
    text(s, 0.95, 2.0, 11.5, 0.5, "一句話", size=14, color=RGBColor(0xFF, 0xD9, 0xD7))
    text(s, 0.9, 2.5, 11.8, 1.6,
         "騰訊能給我們一個「會答的工具」，\n書院要的是一個「答了能負責的資料庫」。",
         size=30, color=WHITE, bold=True, spacing=1.25)
    text(s, 0.95, 4.5, 11.6, 1.0,
         "兩者不衝突：底座用騰訊雲，內容與規矩自己定。\n"
         "先做第一步，不動現有服務；覺得不對，隨時退回。",
         size=14, color=RGBColor(0xFF, 0xE3, 0xE1), spacing=1.4)
    text(s, 0.95, 6.2, 11, 0.4, "下一步：確認三項支持 → 出結構文檔 → 本地驗證", size=11,
         color=RGBColor(0xD9, 0xA9, 0xA6))


def main():
    prs = deck()
    for fn in (s1, s2, s3, s4, s5, s6, s7, s8, s9, s10):
        fn(prs)
    prs.save(OUT)
    print("已生成", OUT, "共", len(prs.slides._sldIdLst), "頁")


if __name__ == "__main__":
    main()
