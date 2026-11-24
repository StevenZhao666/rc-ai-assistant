以下新类名按你现有选择器替换。

### 1. 方向对，但还只是“浅色化＋材质堆叠”
9/10px 等宽字、双渐变、网格、玻璃、内阴影和大量药丸同时出现，会更精致，也更吵。只改三处：**①正文/输入 16px、辅助文字至少 12px；②删网格，只留一层 5% 渐变，发送按钮改纯色；③统一 8px 间距和 16/12/4px 圆角，药丸只留输入框与快捷问题。**
```css
:root{--bg:#FAF8F5;--ink:#282421;--muted:#6E6761;--line:#E7E0DA}
body{
  color:var(--ink);font-size:16px;line-height:1.6;
  background:radial-gradient(circle at 0 0,rgb(122 23 52 / .05),transparent 36%),var(--bg);
}
#log{padding-inline:16px}
.msg .bubble,input{font-size:16px;line-height:1.65}
.meta,.cite summary,.disclaimer{font-size:12px}
.cite{border-radius:12px}
.send{background:#7A1734}
```

### 2. 固定区用玻璃加分，内容区用玻璃减分
顶栏、底栏需要玻璃来表达层级；正文和依据不需要，透背景只会降低可读性。**可信来自实底正文、清楚的依据入口和稳定状态，不来自 blur。**
```css
#log .bubble,#log .cite{
  backdrop-filter:none;
  -webkit-backdrop-filter:none;
  background:#FFF;
  border:1px solid #E7E0DA;
  box-shadow:0 1px 3px rgb(50 35 30 / .05);
}
```

### 3. 只保留一个“警示容器”
完整法务文本由免责条承担，顶栏只留「測試版」；欢迎语里的重复文本若必须保留，就按普通辅助文字显示，不再加框、红边或粗体。中文免责别用等宽字体，**12px/1.55** 才像正式信息，而不是调试日志。
```css
.disclaimer{
  background:#F3F0EC;border:0;border-radius:8px;
  padding:8px 12px;color:#6A625D;
  font-family:inherit;font-size:12px;line-height:1.55;
}
.disclaimer strong{color:inherit;font-weight:600}
.welcome-note{background:none;border:0;color:#6A625D}
```

### 4. 420px 下确实过载
第一行放 **32px 头像＋16px 标题＋三段式语言控件**，第二行只放学号和「測試版」，完整状态移到免责条；学号不要再做药丸。顶栏控制在约 **84–88px**，语言按钮高度至少 36px。
```css
.topbar{padding:8px 12px}
.topbar-row{display:flex;align-items:center;gap:8px;min-width:0}
.topbar-title{
  flex:1;min-width:0;font-size:16px;font-weight:600;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.lang{flex:none;min-height:36px}
.topbar-meta{font-size:12px;color:#6A625D}
```

### 5. 用户气泡确实太接近背景
11% 酒红在 `#FAF8F5` 上的填充对比约 **1.2:1**，叠到暖粉渐变后边界更弱。别再靠透明度，改固定色并加边框：
```css
.msg.user .bubble{
  background:#E9D6DD;
  border:1px solid #B98496;
  color:#33272B;
}
```

### 6. 必须补点按面积和底栏避让
快捷问题、反馈、`<summary>` 至少 **40px 高**，发送按钮 **44px**；`#log` 必须按底栏实际高度留白，否则最后一条依据和反馈会被固定底栏遮住。还要补清晰的键盘焦点。
```css
:root{--composer-h:160px} /* 设为底栏实际高度，不含 safe-area */
#log{
  padding-bottom:calc(var(--composer-h) + 24px + env(safe-area-inset-bottom));
  scroll-padding-bottom:calc(var(--composer-h) + 24px);
}
.cite summary,.fb button,.quick-question{min-height:40px;font-size:12px}
.send{min-width:44px;min-height:44px}
:focus-visible{outline:2px solid #7A1734;outline-offset:2px}
```