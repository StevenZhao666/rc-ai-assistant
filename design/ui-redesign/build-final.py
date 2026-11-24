# -*- coding: utf-8 -*-
"""Generate design/ui-redesign/final-d.html from app/static/index.html.

Only the <style> block and the <header> markup are replaced. The <script>
(the whole behaviour: api/ask, citations, feedback, modal, i18n) is copied
byte-for-byte so the preview runs on the real backend.
"""
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "app", "static", "index.html")
DST = os.path.join(ROOT, "design", "ui-redesign", "final-d.html")

CSS = r"""
  :root{
    --accent:#8C1220; --accent-2:#B4232C;
    --ink:#1F1715; --ink-2:#4E423E; --ink-3:#786A65;
    --glass:rgba(255,255,255,.72); --glass-2:rgba(255,255,255,.55);
    --edge:rgba(140,18,32,.14); --edge-soft:rgba(140,18,32,.08);
    --hair:rgba(140,18,32,.10);
    --ok:#2F6B4F; --warn:#8A6100;
    --sans:"Microsoft JhengHei","PingFang TC","Noto Sans TC","Microsoft YaHei",sans-serif;
    --mono:"Cascadia Mono",Consolas,"SF Mono",monospace;
  }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  html,body{margin:0;min-height:100%}
  body{
    color:var(--ink); font-family:var(--sans); font-size:15.5px; line-height:1.7;
    background:
      radial-gradient(ellipse 78% 58% at 2% 0%, rgba(122,23,52,.055) 0%, transparent 62%),
      #FAF8F5;
    background-attachment:fixed;
  }

  /* ── 頂欄 ────────────────────────────── */
  header{position:sticky;top:0;z-index:8;background:rgba(255,255,255,.64);
         backdrop-filter:blur(18px) saturate(1.2);-webkit-backdrop-filter:blur(18px) saturate(1.2);
         border-bottom:1px solid var(--hair);padding:10px 18px 9px}
  .hrow{max-width:740px;margin:0 auto;display:flex;align-items:center;gap:10px}
  .hrow.sub{margin-top:8px;gap:8px}
  .brand{display:flex;align-items:center;gap:9px;min-width:0;flex:1}
  .av{width:32px;height:32px;border-radius:10px;overflow:hidden;flex:0 0 auto;
      border:1px solid #EEE6E0;box-shadow:0 1px 3px rgba(50,35,30,.08)}
  .av img{width:100%;height:100%;object-fit:cover;display:block}
  .bt{min-width:0}
  header h1{font-size:15px;font-weight:700;letter-spacing:.02em;margin:0;color:var(--ink);
            white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .bt em{font-style:normal;display:block;margin-top:-1px;font-size:9px;letter-spacing:.18em;color:#8A8078}
  .lang{display:flex;gap:2px;background:#F1EBE5;border:1px solid transparent;
        border-radius:999px;padding:3px;flex:0 0 auto}
  .lang button{font:inherit;font-size:12px;padding:4px 9px;min-height:28px;border-radius:999px;
               cursor:pointer;background:transparent;border:0;color:#6E6761}
  .lang button.on{background:#8C1220;color:#fff;font-weight:600}
  .pill{font-size:10.5px;letter-spacing:.02em;color:#6E6761}
  .pill.btn{font-size:11px;letter-spacing:.02em;
            background:#FFFFFF;border:1px solid #E7E0DA;border-radius:8px;
            padding:5px 10px;cursor:pointer;white-space:nowrap;color:#4E423E}
  .pill.btn:hover{border-color:var(--accent);color:var(--accent)}
  .badges{display:flex;align-items:center;gap:7px;min-width:0;flex:1;overflow:hidden}
  #badge1{font-size:10.5px;color:#8A8078;white-space:nowrap}
  /* 使用者決定：頂欄不再重複「AI 生成 · 僅供參考」（免責條已寫）。
     元素保留、只隱藏：JS 有 $('#badge2').textContent = ...，刪 DOM 會拋錯。 */
  #badge2{display:none}
  #badge2::before{content:"·";margin-right:7px;opacity:.6}

  /* ── 免責 ────────────────────────────── */
  .notice{max-width:740px;margin:14px auto 0;padding:0 18px}
  .notice{font-size:11.5px;line-height:1.65;color:var(--ink-3)}
  .notice b{color:var(--accent);font-weight:600}
  #notice{max-width:740px;margin:14px auto 0;padding:8px 13px;
          background:rgba(255,255,255,.46);border:1px solid var(--edge-soft);border-left:2px solid rgba(140,18,32,.32);
          border-radius:0 10px 10px 0;font-size:12px;line-height:1.6;color:#4E423E;
          backdrop-filter:blur(8px);max-width:calc(740px - 36px)}
  #notice b{color:var(--ink);font-weight:600}
  #notice:empty{display:none}

  /* ── 訊息 ────────────────────────────── */
  main{max-width:740px;margin:0 auto;padding:16px 18px calc(196px + env(safe-area-inset-bottom));position:relative;z-index:1}
  .msg{display:flex;gap:9px;margin:0 0 16px;align-items:flex-start;
       animation:up .42s cubic-bezier(.22,1,.36,1) both}
  @keyframes up{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
  .msg.user{flex-direction:row-reverse}
  .msg .who{flex:0 0 30px;width:30px;height:30px;border-radius:10px;display:grid;place-items:center;
            font-size:11px;font-weight:600;overflow:hidden;margin-top:2px}
  .msg.ai .who{background:#fff;border:1px solid rgba(255,255,255,.95);
               box-shadow:0 2px 8px -4px rgba(140,18,32,.4)}
  .msg.ai .who img{width:100%;height:100%;object-fit:cover;display:block}
  .msg.user .who{background:rgba(140,18,32,.09);color:#6B2B2B;border:1px solid rgba(140,18,32,.14)}

  .bubble{max-width:calc(100% - 40px);border-radius:16px;padding:13px 16px;font-size:16px;
          white-space:pre-wrap;word-break:break-word}
  .msg.user .bubble{background:#E9D6DD;border:1px solid #BE8B9D;
                    border-bottom-right-radius:4px;color:#33272B}
  .msg.ai .bubble{background:#FFFFFF;border:1px solid #E7E0DA;color:#282421;
                  box-shadow:0 1px 3px rgba(50,35,30,.05);
                  border-bottom-left-radius:4px}
  .bubble.fail{border-color:rgba(138,97,0,.34);box-shadow:0 0 0 1px rgba(138,97,0,.08)}

  /* ── 引用 ────────────────────────────── */
  .cite{margin-top:12px;border-top:1px solid #EDE7E1;padding-top:10px;
        font-size:12.5px;color:#4E423E}
  .cite summary{cursor:pointer;list-style:none;font-family:var(--sans);font-size:12px;
                letter-spacing:.02em;color:var(--accent);display:inline-flex;align-items:center;gap:6px;
                padding:9px 12px;margin-left:-12px;min-height:40px;border-radius:12px;
                background:#F6F1EC;border:1px solid #E7E0DA;
                transition:.18s;user-select:none}
  .cite summary:hover{background:#EFE7E0;border-color:rgba(140,18,32,.30)}
  .cite summary::-webkit-details-marker{display:none}
  .cite summary::before{content:"▸";transition:transform .18s;display:inline-block;opacity:.75}
  .cite[open] summary::before{transform:rotate(90deg)}
  .citeItem{margin-top:9px;background:#FFFFFF;border:1px solid #E7E0DA;
            border-radius:12px;padding:11px 13px}
  .citeItem b{color:#1F1715;font-weight:600;font-size:13px}
  .citeMeta{font-size:11.5px;color:#6E6761;margin-left:4px}
  .citeQ{font-size:12px;margin-top:5px;color:#4E423E}
  .citeA{margin-top:6px;font-size:12px;color:#4E423E;white-space:pre-wrap;
         max-height:150px;overflow:auto;border-left:2px solid #E0CBD2;padding-left:9px}
  .citeLink{display:inline-block;margin-top:7px;font-size:11.5px;color:var(--accent);
            text-decoration:none;border-bottom:1px solid rgba(140,18,32,.3)}
  .tag{display:inline-block;font-size:10.5px;padding:1px 7px;border-radius:6px;margin:6px 6px 0 0;
       background:rgba(255,246,228,.85);color:var(--warn);border:1px solid rgba(240,223,184,.9)}

  /* ── 回饋 ────────────────────────────── */
  .fb{display:flex;gap:7px;align-items:center;margin-top:12px}
  .fb button{font-size:12px;background:#F2EBE4;border:1px solid #DED3CA;
             border-radius:8px;padding:8px 12px;min-height:36px;color:#3E332F;cursor:pointer;
             transition:.18s;font-family:inherit}
  .fb button:hover{border-color:var(--accent);color:var(--accent);background:#FFFFFF}
  .fb .done{font-size:12px;color:var(--ok)}

  /* ── 底部 ────────────────────────────── */
  footer{position:fixed;left:0;right:0;bottom:0;z-index:9;
         background:linear-gradient(to top,#FCF8F5 42%,rgba(252,248,245,.92) 74%,rgba(252,248,245,0));
         backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
         padding:0 0 13px}
  .quick{max-width:740px;margin:0 auto;padding:0 30px 9px 18px;display:flex;gap:7px;overflow:auto;
         scrollbar-width:none;
         mask-image:linear-gradient(to right,#000 0,#000 calc(100% - 34px),transparent 100%);
         -webkit-mask-image:linear-gradient(to right,#000 0,#000 calc(100% - 34px),transparent 100%)}
  .quick::-webkit-scrollbar{display:none}
  .quick span{white-space:nowrap;font-size:12.5px;background:#FFFFFF;
              border:1px solid #E7E0DA;border-radius:999px;padding:0 14px;min-height:40px;
              display:inline-flex;align-items:center;color:#4E423E;
              cursor:pointer;transition:.18s;box-shadow:0 1px 2px rgba(50,35,30,.04)}
  .quick span:hover{border-color:var(--accent);color:var(--accent)}
  .box{max-width:740px;margin:0 auto;padding:0 18px;display:flex;align-items:center;gap:8px}
  .box{background:transparent}
  #q{flex:1;border:1px solid #E7E0DA;outline:none;font:inherit;font-size:16px;
     color:var(--ink);background:#FFFFFF;border-radius:999px;padding:12px 18px;
     box-shadow:0 1px 3px rgba(50,35,30,.05);transition:.2s}
  #q::placeholder{color:#6E6761}
  #q:focus{border-color:rgba(140,18,32,.42);box-shadow:0 0 0 3px rgba(140,18,32,.07)}
  .primary{border:0;cursor:pointer;color:#fff;font-family:inherit;font-size:14px;font-weight:600;
           background:#8C1220;border-radius:999px;
           padding:13px 18px;min-height:44px;white-space:nowrap;transition:.2s}
  .primary:hover{background:#78101C}
  .primary:disabled{opacity:.5;cursor:default}
  :focus-visible{outline:2px solid #8C1220;outline-offset:2px}

  /* ── 學號彈窗 ────────────────────────── */
  .mask{position:fixed;inset:0;z-index:20;background:rgba(31,23,21,.42);
        backdrop-filter:blur(6px);display:flex;align-items:flex-end;justify-content:center;
        padding:0 0 0}
  .mask[hidden]{display:none}
  .sheet{width:100%;max-width:480px;background:#FFFDFB;border-radius:20px 20px 0 0;
         padding:22px 20px 24px;box-shadow:0 -18px 50px -20px rgba(31,23,21,.55);
         animation:sheetUp .28s cubic-bezier(.22,1,.36,1) both}
  @keyframes sheetUp{from{transform:translateY(18px);opacity:.6}to{transform:none;opacity:1}}
  .sheet h2{margin:0 0 6px;font-size:17px;letter-spacing:.02em}
  .sheet p{margin:0 0 14px;font-size:12.5px;color:var(--ink-3);line-height:1.7}
  #sidInput{width:100%;font:inherit;font-size:16px;letter-spacing:.14em;padding:11px 13px;
            border:1px solid var(--edge);border-radius:12px;background:#fff;outline:none;
            font-family:var(--mono);text-transform:lowercase}
  #sidInput:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(140,18,32,.08)}
  .err{margin-top:8px;font-size:11.5px;color:#A3151F}
  .sheet .row{display:flex;gap:9px;margin-top:16px}
  .sheet .row .primary{flex:1;padding:12px 0;text-align:center}
  .ghost{flex:0 0 auto;border:1px solid var(--edge);background:transparent;border-radius:999px;
         padding:12px 16px;font:inherit;font-size:13px;color:var(--ink-2);cursor:pointer}
  .ghost:hover{border-color:var(--accent);color:var(--accent)}

  @media (max-width:420px){
    header h1{font-size:13px}
    .msg .who{flex-basis:26px;width:26px;height:26px;border-radius:9px}
    .bubble{max-width:calc(100% - 34px);font-size:14.5px}
  }
"""

HEADER = """<header>
  <div class="hrow">
    <div class="brand">
      <div class="av"><img src="img/kunkun.jpg" alt=""></div>
      <div class="bt">
        <h1 id="hTitle">崑崑 · 張崑崙書院助手</h1>
        <em>KUN KUN · ASSISTANT</em>
      </div>
    </div>
    <div class="lang">
      <button data-lang="zh-Hant" class="on">繁</button>
      <button data-lang="zh-Hans">简</button>
      <button data-lang="en">EN</button>
    </div>
  </div>
  <div class="hrow sub">
    <span class="pill btn" id="who" title="填寫學號">未填學號</span>
    <div class="badges">
      <span class="pill" id="badge1">測試版 · 資料未審核</span>
      <span class="pill" id="badge2">AI 生成 · 僅供參考</span>
    </div>
  </div>
</header>"""

src = io.open(SRC, encoding="utf-8").read()

# 1) swap the <style> block
new, n = re.subn(r"<style>.*?</style>", lambda m: "<style>\n" + CSS.strip() + "\n</style>",
                 src, count=1, flags=re.S)
if n != 1:
    sys.exit("style block not found")
src = new

# 2) swap the <header> block (keeps every id the script touches)
new, n = re.subn(r"<header>.*?</header>", lambda m: HEADER, src, count=1, flags=re.S)
if n != 1:
    sys.exit("header block not found")
src = new

io.open(DST, "w", encoding="utf-8", newline="\n").write(src)
print("written:", DST, len(src), "chars")
# sanity: every id the script may touch must still exist
for i in ("hTitle", "who", "badge1", "badge2", "notice", "log", "quick", "q", "send",
          "mask", "mTitle", "mHint", "sidInput", "sidErr", "sidOk", "sidSkip"):
    print(("  ok  " if ('id="%s"' % i) in src else "  MISSING ") + "#" + i)
