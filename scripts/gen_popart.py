"""Generate 10 Pop-Art theme variants — each with a DISTINCT layout.

Not just recolors: 01 horizontal split, 02 grid, 03 shelf/window, 04
horizontal rail, 05 masonry tiles, 06 dashboard, 07 card wall, 08 banner,
09 magazine, 10 showcase carousel.  Run:
    python scripts/gen_popart.py
Output: web/themes/popart/popart-01.html ... popart-10.html
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "web" / "themes" / "popart"

# Shared content fragments (re-arranged per layout)
STREAM_LOG = """      <div class="stream-line strong">━━━ 🔍 研究中 ━━━</div>
      <div class="stream-line">▶ 编排</div>
      <div class="stream-line dim">📋 视角构成(技术类): 原理拆解·技术专家、部署配置·技术专家</div>
      <div class="stream-line">🔎 研究员·原理拆解 → bing_search:「Qwen3.6-35B-A3B」</div>
      <div class="stream-line">📄 研究员·原理拆解 ← bing_search:「1. Qwen3.6-35B-A3B URL: huggingface.co/...」</div>
      <div class="stream-line">✔ 研究员·原理拆解 完成 — 4,500 tokens / $0.002</div>"""

def CARD(q, time, meta, badge, badge_cls, detail=False):
    d = ""
    if detail:
        d = f"""
      <div class="detail">
        <div class="stats">
          <div class="stat"><div class="val">18</div><div class="lbl">发现</div></div>
          <div class="stat"><div class="val">12</div><div class="lbl">验证</div></div>
          <div class="stat"><div class="val">82</div><div class="lbl">评分</div></div>
          <div class="stat"><div class="val">已完成</div><div class="lbl">状态</div></div>
        </div>
        <div class="report">
          <h2>Qwen3.6-35B-A3B 概览</h2>
          <p><strong>MoE 架构</strong>，35B 总参 3B 激活，2026 年 4 月开源。<a href="#">查看来源</a></p>
          <blockquote>引用示例：INT4 量化后单卡 80GB 可推理。</blockquote>
          <pre><code>vllm serve Qwen/Qwen3.6-35B-A3B</code></pre>
        </div>
      </div>"""
    return f"""    <div class="run-card">
      <div class="top"><span class="q">{q}</span>
        <span class="meta"><span>{time}</span><span>{meta}</span><span class="badge {badge_cls}">{badge}</span></span></div>{d}
    </div>"""

# (name, layout html body, css)
VARIANTS: list[tuple[str, str, str]] = []

# ── 01 横向分栏: 左提交+流式 / 右列表 ──────────────────────────────
VARIANTS.append(("横向分栏", """
<div class="style-tag">POP 01 · 横向分栏</div>
<header><h1>POP DEEP RESEARCH</h1><p>多智能体深度研究 — 输入问题，获得一份有来源引用的综合报告</p></header>
<div class="cols">
  <div class="col-main">
    <div class="submit-box">
      <textarea placeholder="输入你想研究的问题，例如：自建NAS的作用和价格、时序大模型哪个好..."></textarea>
      <button>开始研究</button>
    </div>
    <div class="stream-panel">
      <div class="stream-head"><span>📡 实时进度</span><span class="stream-phase">🔍 研究中</span></div>
      <div class="stream-body">
""" + STREAM_LOG + """
      </div>
    </div>
  </div>
  <div class="col-side">
    <div class="status-bar"><h2>研究记录</h2><span class="auto-badge"><span class="dot"></span>自动刷新</span></div>
    <div class="run-list">
""" + CARD("Qwen3.6-35B-A3B 是什么，部署需要什么硬件？", "14:32", "18 发现 · 82分", "已完成", "badge-completed", detail=True) + """
""" + CARD("自建 NAS 的成本与长期维护", "13:05", "9 发现 · 3 验证", "搜索中", "badge-researching") + """
""" + CARD("D2C 品牌出海值得做吗", "12:41", "0 发现", "失败", "badge-failed") + """
    </div>
  </div>
</div>
""", """
/* POP 01 横向分栏 — 经典黄/粉/青 */
:root { --yellow:#ffd93d; --pink:#ff6b9d; --cyan:#4ecdc4; --red:#ff4b4b; --ink:#1a1a1a; --paper:#fff8f0; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Arial Black", "Microsoft YaHei", sans-serif; background:var(--paper); color:var(--ink); min-height:100vh;
  background-image:radial-gradient(circle, rgba(26,26,26,.07) 1.5px, transparent 1.5px); background-size:22px 22px; }
.container { max-width:1060px; margin:0 auto; padding:32px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:var(--ink); background:var(--yellow);
  border:3px solid var(--ink); padding:2px 8px; z-index:9; box-shadow:4px 4px 0 var(--ink); }
header { text-align:center; padding:24px 0 22px; }
header h1 { font-size:2rem; font-weight:900; letter-spacing:1px; text-shadow:4px 4px 0 var(--pink), -3px -3px 0 var(--cyan); }
header p { margin-top:8px; font-size:.9rem; font-weight:700; }
.cols { display:grid; grid-template-columns: 1fr 1fr; gap:22px; align-items:start; }
.col-main, .col-side { display:flex; flex-direction:column; gap:18px; min-width:0; }
.submit-box { background:var(--yellow); border:4px solid var(--ink); padding:20px; box-shadow:8px 8px 0 var(--ink); }
.submit-box textarea { width:100%; background:#fff; border:3px solid var(--ink); padding:12px 14px; font-size:.95rem; resize:vertical; min-height:120px; font-family:inherit; color:var(--ink); }
.submit-box textarea:focus { outline:none; box-shadow:inset 4px 4px 0 rgba(0,0,0,.1); }
.submit-box button { margin-top:12px; background:var(--pink); color:#fff; border:3px solid var(--ink); padding:10px 28px; font-size:1rem; font-weight:900; cursor:pointer; box-shadow:4px 4px 0 var(--ink); }
.submit-box button:hover { transform:translate(2px,2px); box-shadow:2px 2px 0 var(--ink); }
.stream-panel { background:#fff; border:4px solid var(--ink); box-shadow:8px 8px 0 var(--ink); }
.stream-head { display:flex; align-items:center; gap:8px; padding:11px 14px; font-weight:900; background:var(--cyan); border-bottom:3px solid var(--ink); font-size:.85rem; }
.stream-phase { flex:1; text-align:right; font-size:.8rem; }
.stream-body { padding:10px 14px 12px; font-family:Consolas, monospace; font-size:.75rem; line-height:1.85; font-weight:700; }
.stream-line.strong { background:var(--yellow); display:inline-block; padding:1px 6px; }
.stream-line.dim { opacity:.45; }
.status-bar { display:flex; align-items:center; justify-content:space-between; }
.status-bar h2 { font-size:1.15rem; font-weight:900; text-shadow:3px 3px 0 var(--cyan); }
.auto-badge { font-size:.72rem; font-weight:800; display:flex; align-items:center; gap:5px; }
.auto-badge .dot { width:8px; height:8px; border-radius:50%; background:var(--red); border:2px solid var(--ink); animation:pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:14px; }
.run-card { background:#fff; border:4px solid var(--ink); padding:15px 17px; box-shadow:6px 6px 0 var(--ink); }
.run-card:nth-child(1) { background:var(--cyan); }
.run-card:nth-child(2) { background:var(--yellow); }
.run-card:nth-child(3) { background:var(--pink); color:#fff; }
.run-card .top { display:flex; flex-direction:column; gap:8px; }
.run-card .q { font-weight:900; }
.run-card .meta { display:flex; align-items:center; gap:10px; font-size:.76rem; font-weight:800; flex-wrap:wrap; }
.badge { display:inline-block; padding:2px 10px; font-size:.7rem; font-weight:900; background:#fff; border:2px solid var(--ink); }
.badge-completed { color:#0a7d4c; } .badge-researching { color:#0b5fa5; } .badge-failed { color:var(--red); }
.detail { margin-top:12px; padding-top:12px; border-top:3px dashed rgba(26,26,26,.4); }
.detail .stats { display:flex; gap:22px; margin:10px 0; }
.detail .stats .stat .val { font-size:1.4rem; font-weight:900; }
.detail .stats .stat .lbl { font-size:.68rem; font-weight:800; opacity:.6; }
.detail .report { font-size:.88rem; line-height:1.75; font-weight:600; }
.detail .report h2 { font-size:1rem; font-weight:900; margin-bottom:6px; background:var(--yellow); display:inline-block; padding:1px 8px; }
.detail .report a { color:#0b5fa5; font-weight:900; }
.detail .report blockquote { border-left:5px solid var(--pink); margin:8px 0; padding:3px 12px; }
.detail .report code { background:var(--yellow); padding:1px 6px; font-size:.85em; font-family:Consolas, monospace; font-weight:700; }
.detail .report pre { background:#f2f2f2; border:3px solid var(--ink); padding:10px; overflow-x:auto; font-family:Consolas, monospace; }
@media (max-width:760px) { .cols { grid-template-columns:1fr; } }
"""))

# ── 02 双列网格: 提交通栏 + 2列卡片 ────────────────────────────────
VARIANTS.append(("双列网格", """
<div class="style-tag">POP 02 · 双列网格</div>
<header><h1>POP DEEP RESEARCH</h1><p>多智能体深度研究 — 输入问题，获得一份有来源引用的综合报告</p></header>
<div class="submit-box">
  <textarea placeholder="输入你想研究的问题，例如：自建NAS的作用和价格、时序大模型哪个好..."></textarea>
  <button>开始研究</button>
</div>
<div class="stream-panel">
  <div class="stream-head"><span>📡 实时进度</span><span class="stream-phase">🔍 研究中</span></div>
  <div class="stream-body">
""" + STREAM_LOG + """
  </div>
</div>
<div class="status-bar"><h2>研究记录</h2><span class="auto-badge"><span class="dot"></span>自动刷新</span></div>
<div class="run-grid">
""" + CARD("Qwen3.6-35B-A3B 是什么，部署需要什么硬件？", "14:32", "18 发现 · 82分", "已完成", "badge-completed", detail=True) + """
""" + CARD("自建 NAS 的成本与长期维护", "13:05", "9 发现 · 3 验证", "搜索中", "badge-researching") + """
""" + CARD("D2C 品牌出海值得做吗", "12:41", "0 发现", "失败", "badge-failed") + """
</div>
""", """
/* POP 02 双列网格 — 粉蓝泡泡 */
:root { --pink:#ff6b9d; --blue:#4ecdc4; --lav:#c3a6ff; --ink:#1a1a1a; --bg:#ffe3ee; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Arial Black", "Microsoft YaHei", sans-serif; background:var(--bg); color:var(--ink); min-height:100vh;
  background-image:radial-gradient(circle, rgba(26,26,26,.06) 1.5px, transparent 1.5px); background-size:26px 26px; }
.container { max-width:920px; margin:0 auto; padding:32px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:var(--ink); background:var(--blue);
  border:3px solid var(--ink); padding:2px 8px; z-index:9; box-shadow:4px 4px 0 var(--ink); }
header { text-align:center; padding:22px 0 18px; }
header h1 { font-size:2rem; font-weight:900; text-shadow:4px 4px 0 var(--blue), -3px -3px 0 var(--pink); }
header p { margin-top:8px; font-size:.9rem; font-weight:700; }
.submit-box { background:var(--pink); border:4px solid var(--ink); border-radius:20px; padding:20px; margin-bottom:20px; box-shadow:8px 8px 0 var(--ink); }
.submit-box textarea { width:100%; background:#fff; border:3px solid var(--ink); border-radius:12px; padding:12px 14px; font-size:.95rem; resize:vertical; min-height:70px; font-family:inherit; color:var(--ink); }
.submit-box button { margin-top:12px; background:var(--blue); color:var(--ink); border:3px solid var(--ink); border-radius:999px; padding:10px 28px; font-size:1rem; font-weight:900; cursor:pointer; box-shadow:4px 4px 0 var(--ink); }
.stream-panel { background:#fff; border:4px solid var(--ink); border-radius:16px; margin-bottom:22px; overflow:hidden; box-shadow:8px 8px 0 var(--ink); }
.stream-head { display:flex; align-items:center; gap:8px; padding:11px 14px; font-weight:900; background:var(--lav); border-bottom:3px solid var(--ink); }
.stream-phase { flex:1; text-align:right; font-size:.8rem; }
.stream-body { padding:10px 14px 12px; font-family:Consolas, monospace; font-size:.75rem; line-height:1.85; font-weight:700; }
.stream-line.strong { background:var(--blue); display:inline-block; padding:1px 6px; border-radius:6px; }
.stream-line.dim { opacity:.45; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.status-bar h2 { font-size:1.15rem; font-weight:900; text-shadow:3px 3px 0 var(--blue); }
.auto-badge { font-size:.72rem; font-weight:800; display:flex; align-items:center; gap:5px; }
.auto-badge .dot { width:8px; height:8px; border-radius:50%; background:var(--pink); border:2px solid var(--ink); animation:pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.run-card { background:#fff; border:4px solid var(--ink); border-radius:14px; padding:15px 17px; box-shadow:6px 6px 0 var(--ink); }
.run-card:nth-child(1) { background:var(--blue); }
.run-card:nth-child(2) { background:var(--lav); }
.run-card:nth-child(3) { background:var(--pink); color:#fff; }
.run-card:last-child { grid-column:1 / -1; }
.run-card .top { display:flex; flex-direction:column; gap:8px; }
.run-card .q { font-weight:900; }
.run-card .meta { display:flex; align-items:center; gap:10px; font-size:.76rem; font-weight:800; flex-wrap:wrap; }
.badge { display:inline-block; padding:2px 10px; font-size:.7rem; font-weight:900; background:#fff; border:2px solid var(--ink); border-radius:999px; }
.badge-completed { color:#0a7d4c; } .badge-researching { color:#0b5fa5; } .badge-failed { color:var(--pink); }
.detail { margin-top:12px; padding-top:12px; border-top:3px dashed rgba(26,26,26,.4); }
.detail .stats { display:flex; gap:22px; margin:10px 0; }
.detail .stats .stat .val { font-size:1.4rem; font-weight:900; }
.detail .stats .stat .lbl { font-size:.68rem; font-weight:800; opacity:.6; }
.detail .report { font-size:.88rem; line-height:1.75; font-weight:600; }
.detail .report h2 { font-size:1rem; font-weight:900; margin-bottom:6px; background:var(--pink); color:#fff; display:inline-block; padding:1px 8px; border-radius:6px; }
.detail .report a { color:#0b5fa5; font-weight:900; }
.detail .report blockquote { border-left:5px solid var(--blue); margin:8px 0; padding:3px 12px; }
.detail .report code { background:var(--blue); padding:1px 6px; border-radius:6px; font-size:.85em; font-family:Consolas, monospace; font-weight:700; }
.detail .report pre { background:#f2f2f2; border:3px solid var(--ink); border-radius:10px; padding:10px; overflow-x:auto; font-family:Consolas, monospace; }
@media (max-width:640px) { .run-grid { grid-template-columns:1fr; } }
"""))

# ── 03 橱窗货架: 每卡带"价签"徽章 ───────────────────────────────
VARIANTS.append(("橱窗货架", """
<div class="style-tag">POP 03 · 橱窗货架</div>
<header><h1>POP DEEP RESEARCH</h1><p>研究问题陈列柜 — 每件商品都有标价</p></header>
<div class="banner-submit">
  <textarea placeholder="输入你想研究的问题..."></textarea>
  <button>开始研究</button>
</div>
<div class="shelf">
  <div class="shelf-title">★ 本周上架 ★</div>
  <div class="shelf-item" style="background:var(--cyan);">
    <div class="thumb">🔍</div>
    <div class="info">
      <div class="q">Qwen3.6-35B-A3B 是什么，部署需要什么硬件？</div>
      <div class="meta"><span>14:32</span><span>18 发现 · 12 验证</span></div>
      <div class="price-tag">已完成 · 82分</div>
    </div>
  </div>
  <div class="shelf-item" style="background:var(--yellow);">
    <div class="thumb">⏳</div>
    <div class="info">
      <div class="q">自建 NAS 的成本与长期维护</div>
      <div class="meta"><span>13:05</span><span>9 发现 · 3 验证</span></div>
      <div class="price-tag">搜索中</div>
    </div>
  </div>
  <div class="shelf-item" style="background:var(--pink); color:#fff;">
    <div class="thumb">✖</div>
    <div class="info">
      <div class="q">D2C 品牌出海值得做吗</div>
      <div class="meta"><span>12:41</span><span>0 发现</span></div>
      <div class="price-tag">失败</div>
    </div>
  </div>
</div>
<div class="stream-panel">
  <div class="stream-head"><span>📡 实时进度</span><span class="stream-phase">🔍 研究中</span></div>
  <div class="stream-body">
""" + STREAM_LOG + """
  </div>
</div>
""", """
/* POP 03 橱窗货架 — 橙紫撞色 */
:root { --orange:#ff8c42; --purple:#9b5de5; --yellow:#ffd93d; --pink:#ff6b9d; --cyan:#4ecdc4; --ink:#1a1a1a; --bg:#fff4e6; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Arial Black", "Microsoft YaHei", sans-serif; background:var(--bg); color:var(--ink); min-height:100vh;
  background-image:repeating-linear-gradient(45deg, rgba(155,93,229,.06) 0 14px, transparent 14px 28px); }
.container { max-width:920px; margin:0 auto; padding:32px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:#fff; background:var(--purple);
  border:3px solid var(--ink); padding:2px 8px; z-index:9; box-shadow:4px 4px 0 var(--ink); }
header { text-align:center; padding:22px 0 18px; }
header h1 { font-size:2rem; font-weight:900; text-shadow:4px 4px 0 var(--orange), -3px -3px 0 var(--purple); }
header p { margin-top:8px; font-size:.9rem; font-weight:700; }
.banner-submit { display:flex; gap:14px; background:var(--purple); border:4px solid var(--ink); padding:16px; margin-bottom:22px; box-shadow:8px 8px 0 var(--ink); align-items:center; }
.banner-submit textarea { flex:1; background:#fff; border:3px solid var(--ink); padding:11px 14px; font-size:.95rem; resize:vertical; min-height:64px; font-family:inherit; color:var(--ink); }
.banner-submit button { background:var(--orange); color:var(--ink); border:3px solid var(--ink); padding:10px 24px; font-size:.95rem; font-weight:900; cursor:pointer; box-shadow:4px 4px 0 var(--ink); white-space:nowrap; }
.shelf { border:4px solid var(--ink); background:#fff; padding:18px; box-shadow:8px 8px 0 var(--ink); margin-bottom:22px; }
.shelf-title { font-size:1.05rem; font-weight:900; margin-bottom:14px; text-shadow:2px 2px 0 var(--orange); }
.shelf-item { display:flex; align-items:center; gap:16px; border:4px solid var(--ink); padding:16px; margin-bottom:12px; box-shadow:5px 5px 0 var(--ink); position:relative; }
.shelf-item:last-child { margin-bottom:0; }
.thumb { font-size:2rem; width:64px; height:64px; display:flex; align-items:center; justify-content:center; background:#fff; border:3px solid var(--ink); flex-shrink:0; }
.info { flex:1; min-width:0; }
.info .q { font-weight:900; margin-bottom:6px; }
.info .meta { font-size:.78rem; font-weight:800; opacity:.7; display:flex; gap:12px; }
.price-tag { position:absolute; top:-14px; right:14px; background:#fff; border:3px solid var(--ink); padding:2px 12px; font-weight:900; font-size:.78rem; box-shadow:3px 3px 0 var(--ink); transform:rotate(-3deg); }
.stream-panel { background:#fff; border:4px solid var(--ink); box-shadow:8px 8px 0 var(--ink); }
.stream-head { display:flex; align-items:center; gap:8px; padding:11px 14px; font-weight:900; background:var(--orange); border-bottom:3px solid var(--ink); }
.stream-phase { flex:1; text-align:right; font-size:.8rem; }
.stream-body { padding:10px 14px 12px; font-family:Consolas, monospace; font-size:.75rem; line-height:1.85; font-weight:700; }
.stream-line.strong { background:var(--purple); color:#fff; display:inline-block; padding:1px 6px; }
.stream-line.dim { opacity:.45; }
@media (max-width:600px) { .banner-submit { flex-direction:column; } .shelf-item { flex-direction:column; } }
"""))

# ── 04 横向滚动墙: 卡片横排一行横向滚动 ─────────────────────────
VARIANTS.append(("横向滚动墙", """
<div class="style-tag">POP 04 · 横向滚动墙</div>
<header><h1>POP DEEP RESEARCH</h1><p>研究记录横排滚动 — 拖动手柄或滚轮横向浏览</p></header>
<div class="submit-box">
  <textarea placeholder="输入你想研究的问题，例如：自建NAS的作用和价格、时序大模型哪个好..."></textarea>
  <button>开始研究</button>
</div>
<div class="stream-panel">
  <div class="stream-head"><span>📡 实时进度</span><span class="stream-phase">🔍 研究中</span></div>
  <div class="stream-body">
""" + STREAM_LOG + """
  </div>
</div>
<div class="status-bar"><h2>研究记录 · 横排</h2><span class="auto-badge"><span class="dot"></span>自动刷新</span></div>
<div class="run-rail">
  <div class="rail-card" style="background:var(--green);">
    <div class="q">Qwen3.6-35B-A3B 是什么，部署需要什么硬件？</div>
    <div class="meta">14:32 · 18 发现 · 82分</div>
    <div class="badge badge-completed">已完成</div>
  </div>
  <div class="rail-card" style="background:var(--yellow);">
    <div class="q">自建 NAS 的成本与长期维护</div>
    <div class="meta">13:05 · 9 发现 · 3 验证</div>
    <div class="badge badge-researching">搜索中</div>
  </div>
  <div class="rail-card" style="background:var(--red); color:#fff;">
    <div class="q">D2C 品牌出海值得做吗</div>
    <div class="meta">12:41 · 0 发现</div>
    <div class="badge badge-failed">失败</div>
  </div>
  <div class="rail-card" style="background:var(--cyan);">
    <div class="q">时序大模型哪家强？横向对比</div>
    <div class="meta">11:20 · 25 发现 · 90分</div>
    <div class="badge badge-completed">已完成</div>
  </div>
  <div class="rail-card" style="background:var(--purple); color:#fff;">
    <div class="q">量子计算商用化时间表</div>
    <div class="meta">10:12 · 12 发现</div>
    <div class="badge badge-researching">搜索中</div>
  </div>
</div>
""", """
/* POP 04 横向滚动墙 — 荧光绿/黑黄 */
:root { --green:#54ff9f; --yellow:#ffd93d; --cyan:#4ecdc4; --red:#ff4b4b; --purple:#9b5de5; --ink:#111; --bg:#0d0d0d; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Arial Black", "Microsoft YaHei", sans-serif; background:var(--bg); color:var(--ink); min-height:100vh; }
.container { max-width:1060px; margin:0 auto; padding:32px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:var(--bg); background:var(--green);
  border:3px solid var(--ink); padding:2px 8px; z-index:9; box-shadow:4px 4px 0 var(--ink); }
header { text-align:center; padding:22px 0 18px; }
header h1 { font-size:2rem; font-weight:900; color:var(--green); text-shadow:4px 4px 0 #000; }
header p { color:#aaa; margin-top:8px; font-size:.9rem; font-weight:700; }
.submit-box { background:var(--green); border:4px solid var(--ink); padding:18px; margin-bottom:20px; box-shadow:8px 8px 0 var(--ink); }
.submit-box textarea { width:100%; background:#fff; border:3px solid var(--ink); padding:11px 14px; font-size:.95rem; resize:vertical; min-height:70px; font-family:inherit; color:var(--ink); }
.submit-box button { margin-top:12px; background:var(--yellow); color:var(--ink); border:3px solid var(--ink); padding:10px 26px; font-size:1rem; font-weight:900; cursor:pointer; box-shadow:4px 4px 0 var(--ink); }
.stream-panel { background:#fff; border:4px solid var(--ink); margin-bottom:22px; box-shadow:8px 8px 0 var(--ink); }
.stream-head { display:flex; align-items:center; gap:8px; padding:11px 14px; font-weight:900; background:var(--yellow); border-bottom:3px solid var(--ink); }
.stream-phase { flex:1; text-align:right; font-size:.8rem; }
.stream-body { padding:10px 14px 12px; font-family:Consolas, monospace; font-size:.75rem; line-height:1.85; font-weight:700; }
.stream-line.strong { background:var(--green); display:inline-block; padding:1px 6px; }
.stream-line.dim { opacity:.45; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.status-bar h2 { font-size:1.1rem; font-weight:900; color:var(--green); text-shadow:3px 3px 0 #000; }
.auto-badge { font-size:.72rem; font-weight:800; color:#aaa; display:flex; align-items:center; gap:5px; }
.auto-badge .dot { width:8px; height:8px; border-radius:50%; background:var(--red); border:2px solid #000; animation:pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-rail { display:flex; gap:16px; overflow-x:auto; padding:6px 4px 18px; scroll-snap-type:x mandatory; }
.rail-card { flex:0 0 250px; border:4px solid var(--ink); padding:18px; box-shadow:6px 6px 0 var(--ink); scroll-snap-align:start; display:flex; flex-direction:column; gap:10px; }
.rail-card .q { font-weight:900; font-size:.95rem; }
.rail-card .meta { font-size:.76rem; font-weight:800; opacity:.7; }
.badge { align-self:flex-start; display:inline-block; padding:2px 10px; font-size:.7rem; font-weight:900; background:#fff; border:2px solid var(--ink); }
.badge-completed { color:#0a7d4c; } .badge-researching { color:#0b5fa5; } .badge-failed { color:var(--red); }
.run-rail::-webkit-scrollbar { height:12px; }
.run-rail::-webkit-scrollbar-thumb { background:var(--yellow); border:2px solid #000; }
@media (max-width:600px) { .rail-card { flex-basis:200px; } }
"""))

# ── 05 磁贴瀑布: clip-path 裁切大小交错 ─────────────────────────
VARIANTS.append(("磁贴瀑布", """
<div class="style-tag">POP 05 · 磁贴瀑布</div>
<header><h1>POP DEEP RESEARCH</h1><p>研究磁贴 — 大小交错的多边形陈列</p></header>
<div class="submit-box">
  <textarea placeholder="输入你想研究的问题..."></textarea>
  <button>开始研究</button>
</div>
<div class="tiles">
  <div class="tile tile-feat" style="background:var(--red);">
    <div class="tile-inner">
      <div class="q">Qwen3.6-35B-A3B 是什么，部署需要什么硬件？</div>
      <div class="meta">14:32 · 18 发现 · 82分</div>
      <div class="badge badge-completed">已完成</div>
    </div>
  </div>
  <div class="tile tile-sm" style="background:var(--cyan);">
    <div class="tile-inner"><div class="q">自建 NAS 成本</div><div class="badge badge-researching">搜索中</div></div>
  </div>
  <div class="tile tile-sm" style="background:var(--yellow);">
    <div class="tile-inner"><div class="q">D2C 出海</div><div class="badge badge-failed">失败</div></div>
  </div>
  <div class="tile tile-md" style="background:var(--purple); color:#fff;">
    <div class="tile-inner"><div class="q">时序大模型哪家强？</div><div class="meta">25 发现 · 90分</div><div class="badge badge-completed">已完成</div></div>
  </div>
</div>
<div class="stream-panel">
  <div class="stream-head"><span>📡 实时进度</span><span class="stream-phase">🔍 研究中</span></div>
  <div class="stream-body">
""" + STREAM_LOG + """
  </div>
</div>
""", """
/* POP 05 磁贴瀑布 — 红黑硬派 */
:root { --red:#ff4b4b; --cyan:#4ecdc4; --yellow:#ffd93d; --purple:#5b2a86; --ink:#111; --bg:#f5f5f0; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Arial Black", "Microsoft YaHei", sans-serif; background:var(--bg); color:var(--ink); min-height:100vh;
  background-image:radial-gradient(circle, rgba(17,17,17,.07) 1.5px, transparent 1.5px); background-size:24px 24px; }
.container { max-width:940px; margin:0 auto; padding:32px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:#fff; background:var(--ink);
  border:3px solid var(--red); padding:2px 8px; z-index:9; box-shadow:4px 4px 0 var(--red); }
header { text-align:center; padding:22px 0 18px; }
header h1 { font-size:2.1rem; font-weight:900; letter-spacing:2px; text-shadow:4px 4px 0 var(--red); }
header p { margin-top:8px; font-size:.9rem; font-weight:700; }
.submit-box { background:var(--ink); border:4px solid var(--red); padding:18px; margin-bottom:22px; box-shadow:8px 8px 0 var(--red); }
.submit-box textarea { width:100%; background:#fff; border:3px solid var(--ink); padding:11px 14px; font-size:.95rem; resize:vertical; min-height:70px; font-family:inherit; color:var(--ink); }
.submit-box button { margin-top:12px; background:var(--red); color:#fff; border:3px solid var(--ink); padding:10px 26px; font-size:1rem; font-weight:900; cursor:pointer; box-shadow:4px 4px 0 #000; }
.tiles { display:grid; grid-template-columns:1.6fr 1fr 1fr; grid-auto-rows:150px; gap:14px; margin-bottom:22px; }
.tile { border:4px solid var(--ink); box-shadow:7px 7px 0 var(--ink); clip-path:polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 16px 100%, 0 calc(100% - 16px)); }
.tile-inner { padding:18px; display:flex; flex-direction:column; gap:8px; height:100%; }
.tile-feat { grid-row:span 2; }
.tile-md { grid-column:span 2; }
.tile .q { font-weight:900; font-size:.98rem; }
.tile-sm .q { font-size:.9rem; }
.tile .meta { font-size:.76rem; font-weight:800; opacity:.75; }
.badge { align-self:flex-start; display:inline-block; padding:2px 10px; font-size:.7rem; font-weight:900; background:#fff; border:2px solid var(--ink); }
.badge-completed { color:#0a7d4c; } .badge-researching { color:#0b5fa5; } .badge-failed { color:var(--red); }
.stream-panel { background:#fff; border:4px solid var(--ink); box-shadow:8px 8px 0 var(--ink); }
.stream-head { display:flex; align-items:center; gap:8px; padding:11px 14px; font-weight:900; background:var(--red); color:#fff; border-bottom:3px solid var(--ink); }
.stream-phase { flex:1; text-align:right; font-size:.8rem; }
.stream-body { padding:10px 14px 12px; font-family:Consolas, monospace; font-size:.75rem; line-height:1.85; font-weight:700; }
.stream-line.strong { background:var(--ink); color:var(--yellow); display:inline-block; padding:1px 6px; }
.stream-line.dim { opacity:.45; }
@media (max-width:640px) { .tiles { grid-template-columns:1fr; } .tile-feat, .tile-md { grid-column:1; grid-row:auto; } }
"""))

# ── 06 仪表盘顶栏: 统计大数字横条 + 三栏 ─────────────────────────
VARIANTS.append(("仪表盘顶栏", """
<div class="style-tag">POP 06 · 仪表盘</div>
<header><h1>POP DASHBOARD</h1><p>研究控制台 — 统计一目了然</p></header>
<div class="dash-stats">
  <div class="dash-stat" style="background:var(--red);"><div class="val">18</div><div class="lbl">发现</div></div>
  <div class="dash-stat" style="background:var(--yellow);"><div class="val">12</div><div class="lbl">验证</div></div>
  <div class="dash-stat" style="background:var(--cyan);"><div class="val">82</div><div class="lbl">评分</div></div>
  <div class="dash-stat" style="background:var(--purple); color:#fff;"><div class="val">✓</div><div class="lbl">已完成</div></div>
</div>
<div class="submit-box">
  <textarea placeholder="输入你想研究的问题，例如：自建NAS的作用和价格..."></textarea>
  <button>开始研究</button>
</div>
<div class="stream-panel">
  <div class="stream-head"><span>📡 实时进度</span><span class="stream-phase">🔍 研究中</span></div>
  <div class="stream-body">
""" + STREAM_LOG + """
  </div>
</div>
<div class="status-bar"><h2>研究记录</h2><span class="auto-badge"><span class="dot"></span>自动刷新</span></div>
<div class="run-grid3">
""" + CARD("Qwen3.6-35B-A3B 是什么，部署需要什么硬件？", "14:32", "18 发现 · 82分", "已完成", "badge-completed") + """
""" + CARD("自建 NAS 的成本与长期维护", "13:05", "9 发现 · 3 验证", "搜索中", "badge-researching") + """
""" + CARD("D2C 品牌出海值得做吗", "12:41", "0 发现", "失败", "badge-failed") + """
</div>
""", """
/* POP 06 仪表盘顶栏 — 彩虹条 */
:root { --red:#ff5f4d; --yellow:#ffd93d; --cyan:#4ecdc4; --purple:#9b5de5; --ink:#111; --bg:#fafafa; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Arial Black", "Microsoft YaHei", sans-serif; background:var(--bg); color:var(--ink); min-height:100vh;
  background-image:linear-gradient(90deg, rgba(255,95,77,.05) 0 20%, rgba(255,217,61,.05) 20% 40%, rgba(78,205,196,.05) 40% 60%, rgba(155,93,229,.05) 60% 80%, rgba(255,107,157,.05) 80% 100%); }
.container { max-width:980px; margin:0 auto; padding:32px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:var(--ink); background:var(--yellow);
  border:3px solid var(--ink); padding:2px 8px; z-index:9; box-shadow:4px 4px 0 var(--ink); }
header { text-align:center; padding:22px 0 18px; }
header h1 { font-size:2.1rem; font-weight:900; background:linear-gradient(90deg, var(--red), var(--yellow), var(--cyan), var(--purple));
  -webkit-background-clip:text; background-clip:text; color:transparent; }
header p { margin-top:8px; font-size:.9rem; font-weight:700; }
.dash-stats { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }
.dash-stat { border:4px solid var(--ink); padding:16px; text-align:center; box-shadow:6px 6px 0 var(--ink); }
.dash-stat .val { font-size:2rem; font-weight:900; }
.dash-stat .lbl { font-size:.72rem; font-weight:800; opacity:.8; }
.submit-box { background:var(--cyan); border:4px solid var(--ink); padding:18px; margin-bottom:18px; box-shadow:8px 8px 0 var(--ink); }
.submit-box textarea { width:100%; background:#fff; border:3px solid var(--ink); padding:11px 14px; font-size:.95rem; resize:vertical; min-height:66px; font-family:inherit; color:var(--ink); }
.submit-box button { margin-top:12px; background:var(--red); color:#fff; border:3px solid var(--ink); padding:10px 26px; font-size:1rem; font-weight:900; cursor:pointer; box-shadow:4px 4px 0 var(--ink); }
.stream-panel { background:#fff; border:4px solid var(--ink); margin-bottom:20px; box-shadow:8px 8px 0 var(--ink); }
.stream-head { display:flex; align-items:center; gap:8px; padding:11px 14px; font-weight:900; background:var(--purple); color:#fff; border-bottom:3px solid var(--ink); }
.stream-phase { flex:1; text-align:right; font-size:.8rem; }
.stream-body { padding:10px 14px 12px; font-family:Consolas, monospace; font-size:.75rem; line-height:1.85; font-weight:700; }
.stream-line.strong { background:var(--yellow); display:inline-block; padding:1px 6px; }
.stream-line.dim { opacity:.45; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.status-bar h2 { font-size:1.15rem; font-weight:900; text-shadow:3px 3px 0 var(--cyan); }
.auto-badge { font-size:.72rem; font-weight:800; display:flex; align-items:center; gap:5px; }
.auto-badge .dot { width:8px; height:8px; border-radius:50%; background:var(--red); border:2px solid var(--ink); animation:pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-grid3 { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }
.run-card { background:#fff; border:4px solid var(--ink); padding:15px 16px; box-shadow:6px 6px 0 var(--ink); display:flex; flex-direction:column; gap:9px; }
.run-card:nth-child(1) { background:var(--red); color:#fff; }
.run-card:nth-child(2) { background:var(--yellow); }
.run-card:nth-child(3) { background:var(--purple); color:#fff; }
.run-card .q { font-weight:900; }
.run-card .meta { font-size:.76rem; font-weight:800; opacity:.8; display:flex; gap:10px; flex-wrap:wrap; }
.badge { align-self:flex-start; display:inline-block; padding:2px 10px; font-size:.7rem; font-weight:900; background:#fff; border:2px solid var(--ink); }
.badge-completed { color:#0a7d4c; } .badge-researching { color:#0b5fa5; } .badge-failed { color:var(--red); }
@media (max-width:720px) { .run-grid3 { grid-template-columns:1fr; } .dash-stats { grid-template-columns:repeat(2,1fr); } }
"""))

# ── 07 等分卡片墙: 全宽等大块状 ─────────────────────────────────
VARIANTS.append(("等分卡片墙", """
<div class="style-tag">POP 07 · 卡片墙</div>
<header><h1>POP DEEP RESEARCH</h1><p>研究墙 — 等大块状铺满</p></header>
<div class="submit-box">
  <textarea placeholder="输入你想研究的问题..."></textarea>
  <button>开始研究</button>
</div>
<div class="card-wall">
  <div class="wall-card wall-a">
    <div class="q">Qwen3.6-35B-A3B 是什么，部署需要什么硬件？</div>
    <div class="meta">14:32 · 18 发现 · 82分</div>
    <div class="badge badge-completed">已完成</div>
  </div>
  <div class="wall-card wall-b">
    <div class="q">自建 NAS 的成本与长期维护</div>
    <div class="meta">13:05 · 9 发现 · 3 验证</div>
    <div class="badge badge-researching">搜索中</div>
  </div>
  <div class="wall-card wall-c">
    <div class="q">D2C 品牌出海值得做吗</div>
    <div class="meta">12:41 · 0 发现</div>
    <div class="badge badge-failed">失败</div>
  </div>
  <div class="wall-card wall-d">
    <div class="q">时序大模型哪家强？横向对比</div>
    <div class="meta">11:20 · 25 发现 · 90分</div>
    <div class="badge badge-completed">已完成</div>
  </div>
</div>
<div class="stream-panel">
  <div class="stream-head"><span>📡 实时进度</span><span class="stream-phase">🔍 研究中</span></div>
  <div class="stream-body">
""" + STREAM_LOG + """
  </div>
</div>
""", """
/* POP 07 等分卡片墙 — 奶油漫画 */
:root { --cream:#fff4e0; --yellow:#ffd93d; --pink:#ff6b9d; --blue:#4ecdc4; --red:#ff4b4b; --ink:#1a1a1a; --bg:#fdf6e9; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Comic Sans MS", "Arial Black", "Microsoft YaHei", sans-serif; background:var(--bg); color:var(--ink); min-height:100vh;
  background-image:radial-gradient(circle, rgba(26,26,26,.06) 1.5px, transparent 1.5px); background-size:24px 24px; }
.container { max-width:1000px; margin:0 auto; padding:32px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:var(--ink); background:var(--pink); color:#fff;
  border:3px solid var(--ink); padding:2px 8px; z-index:9; box-shadow:4px 4px 0 var(--ink); }
header { text-align:center; padding:22px 0 18px; }
header h1 { font-size:2.1rem; font-weight:900; text-shadow:4px 4px 0 var(--yellow), -3px -3px 0 var(--blue); }
header p { margin-top:8px; font-size:.9rem; font-weight:700; }
.submit-box { background:var(--cream); border:4px solid var(--ink); border-radius:18px; padding:18px; margin-bottom:20px; box-shadow:8px 8px 0 var(--ink); }
.submit-box textarea { width:100%; background:#fff; border:3px solid var(--ink); border-radius:10px; padding:11px 14px; font-size:.95rem; resize:vertical; min-height:66px; font-family:inherit; color:var(--ink); }
.submit-box button { margin-top:12px; background:var(--blue); color:var(--ink); border:3px solid var(--ink); border-radius:999px; padding:10px 26px; font-size:1rem; font-weight:900; cursor:pointer; box-shadow:4px 4px 0 var(--ink); }
.card-wall { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }
.wall-card { border:4px solid var(--ink); border-radius:14px; padding:18px; box-shadow:6px 6px 0 var(--ink); display:flex; flex-direction:column; gap:9px; min-height:150px; }
.wall-a { background:var(--yellow); } .wall-b { background:var(--blue); } .wall-c { background:var(--pink); color:#fff; } .wall-d { background:#fff; }
.wall-card .q { font-weight:900; }
.wall-card .meta { font-size:.76rem; font-weight:800; opacity:.75; }
.badge { align-self:flex-start; display:inline-block; padding:2px 10px; font-size:.7rem; font-weight:900; background:#fff; border:2px solid var(--ink); border-radius:999px; }
.badge-completed { color:#0a7d4c; } .badge-researching { color:#0b5fa5; } .badge-failed { color:var(--red); }
.stream-panel { background:#fff; border:4px solid var(--ink); border-radius:14px; box-shadow:8px 8px 0 var(--ink); overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:8px; padding:11px 14px; font-weight:900; background:var(--yellow); border-bottom:3px solid var(--ink); }
.stream-phase { flex:1; text-align:right; font-size:.8rem; }
.stream-body { padding:10px 14px 12px; font-family:Consolas, monospace; font-size:.75rem; line-height:1.85; font-weight:700; }
.stream-line.strong { background:var(--blue); display:inline-block; padding:1px 6px; border-radius:6px; }
.stream-line.dim { opacity:.45; }
@media (max-width:760px) { .card-wall { grid-template-columns:repeat(2,1fr); } }
"""))

# ── 08 横幅提交: 左输入右按钮 + 下方双列 ─────────────────────────
VARIANTS.append(("横幅提交", """
<div class="style-tag">POP 08 · 横幅</div>
<header><h1>POP DEEP RESEARCH</h1><p>横幅式提交 — 输入框与按钮并肩</p></header>
<div class="banner">
  <span class="banner-label">研究题目</span>
  <textarea placeholder="输入你想研究的问题，例如：自建NAS的作用和价格..."></textarea>
  <button>GO!</button>
</div>
<div class="stream-panel">
  <div class="stream-head"><span>📡 实时进度</span><span class="stream-phase">🔍 研究中</span></div>
  <div class="stream-body">
""" + STREAM_LOG + """
  </div>
</div>
<div class="status-bar"><h2>研究记录</h2><span class="auto-badge"><span class="dot"></span>自动刷新</span></div>
<div class="run-grid">
""" + CARD("Qwen3.6-35B-A3B 是什么，部署需要什么硬件？", "14:32", "18 发现 · 82分", "已完成", "badge-completed", detail=True) + """
""" + CARD("自建 NAS 的成本与长期维护", "13:05", "9 发现 · 3 验证", "搜索中", "badge-researching") + """
""" + CARD("D2C 品牌出海值得做吗", "12:41", "0 发现", "失败", "badge-failed") + """
</div>
""", """
/* POP 08 横幅提交 — 暗夜反色 */
:root { --bg:#14142e; --pink:#ff5ff0; --cyan:#35e0ff; --yellow:#ffe14d; --ink:#fff; --card:#1e1e40; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Arial Black", "Microsoft YaHei", sans-serif; background:var(--bg); color:var(--ink); min-height:100vh; }
.container { max-width:940px; margin:0 auto; padding:32px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:var(--bg); background:var(--cyan);
  border:3px solid var(--ink); padding:2px 8px; z-index:9; box-shadow:4px 4px 0 var(--pink); }
header { text-align:center; padding:22px 0 18px; }
header h1 { font-size:2rem; font-weight:900; color:var(--pink); text-shadow:4px 4px 0 var(--cyan), -3px -3px 0 #000; }
header p { color:#aaa; margin-top:8px; font-size:.9rem; font-weight:700; }
.banner { display:flex; align-items:stretch; gap:12px; background:var(--card); border:4px solid var(--pink); padding:14px; margin-bottom:20px; box-shadow:8px 8px 0 var(--cyan); }
.banner-label { font-size:.8rem; font-weight:900; writing-mode:vertical-rl; text-align:center; background:var(--pink); color:#14142e; padding:8px 6px; }
.banner textarea { flex:1; background:#0d0d22; border:3px solid #3a3a6e; padding:11px 14px; font-size:.95rem; resize:vertical; min-height:64px; font-family:inherit; color:#fff; }
.banner textarea:focus { outline:none; border-color:var(--cyan); }
.banner button { background:var(--yellow); color:#14142e; border:3px solid var(--ink); padding:0 30px; font-size:1.3rem; font-weight:900; cursor:pointer; box-shadow:4px 4px 0 var(--pink); }
.stream-panel { background:var(--card); border:4px solid var(--cyan); margin-bottom:20px; box-shadow:8px 8px 0 var(--pink); }
.stream-head { display:flex; align-items:center; gap:8px; padding:11px 14px; font-weight:900; color:var(--cyan); border-bottom:3px solid #3a3a6e; }
.stream-phase { flex:1; text-align:right; font-size:.8rem; color:var(--pink); }
.stream-body { padding:10px 14px 12px; font-family:Consolas, monospace; font-size:.75rem; line-height:1.85; font-weight:700; color:#c9c9f0; }
.stream-line.strong { color:var(--yellow); }
.stream-line.dim { opacity:.4; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.status-bar h2 { font-size:1.15rem; font-weight:900; color:var(--pink); text-shadow:3px 3px 0 var(--cyan); }
.auto-badge { font-size:.72rem; font-weight:800; color:#aaa; display:flex; align-items:center; gap:5px; }
.auto-badge .dot { width:8px; height:8px; border-radius:50%; background:var(--yellow); border:2px solid var(--pink); animation:pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.run-card { background:var(--card); border:4px solid #3a3a6e; padding:15px 17px; box-shadow:6px 6px 0 rgba(0,0,0,.4); }
.run-card:nth-child(1) { border-color:var(--yellow); }
.run-card:nth-child(2) { border-color:var(--cyan); }
.run-card:nth-child(3) { border-color:var(--pink); }
.run-card:last-child { grid-column:1 / -1; }
.run-card .top { display:flex; flex-direction:column; gap:8px; }
.run-card .q { font-weight:900; }
.run-card .meta { font-size:.76rem; font-weight:800; color:#8a8ac0; display:flex; gap:10px; flex-wrap:wrap; }
.badge { align-self:flex-start; display:inline-block; padding:2px 10px; font-size:.7rem; font-weight:900; background:#14142e; border:2px solid; }
.badge-completed { color:var(--yellow); border-color:var(--yellow); } .badge-researching { color:var(--cyan); border-color:var(--cyan); } .badge-failed { color:var(--pink); border-color:var(--pink); }
.detail { margin-top:12px; padding-top:12px; border-top:3px dashed #3a3a6e; }
.detail .stats { display:flex; gap:22px; margin:10px 0; }
.detail .stats .stat .val { font-size:1.4rem; font-weight:900; color:var(--cyan); }
.detail .stats .stat .lbl { font-size:.68rem; font-weight:800; color:#8a8ac0; }
.detail .report { font-size:.88rem; line-height:1.75; font-weight:600; color:#c9c9f0; }
.detail .report h2 { font-size:1rem; font-weight:900; color:var(--yellow); margin-bottom:6px; }
.detail .report a { color:var(--cyan); font-weight:900; }
.detail .report blockquote { border-left:5px solid var(--pink); margin:8px 0; padding:3px 12px; color:#8a8ac0; }
.detail .report code { background:#14142e; border:1px solid #3a3a6e; padding:1px 6px; color:var(--yellow); font-size:.85em; font-family:Consolas, monospace; }
.detail .report pre { background:#0d0d22; border:1px solid #3a3a6e; padding:10px; overflow-x:auto; font-family:Consolas, monospace; }
@media (max-width:640px) { .run-grid { grid-template-columns:1fr; } .banner { flex-direction:column; } .banner-label { writing-mode:horizontal-tb; } }
"""))

# ── 09 杂志混排: 特色卡横跨 + 普通卡竖排 ─────────────────────────
VARIANTS.append(("杂志混排", """
<div class="style-tag">POP 09 · 杂志混排</div>
<header><h1>POP RESEARCH WEEKLY</h1><p>本周研究专题 — 头版特稿 + 栏目快讯</p></header>
<div class="submit-box">
  <textarea placeholder="输入你想研究的问题..."></textarea>
  <button>开始研究</button>
</div>
<div class="feature">
  <div class="feature-tag">特稿</div>
  <div class="q">Qwen3.6-35B-A3B 是什么，部署需要什么硬件？</div>
  <div class="meta">14:32 · 18 发现 · 12 验证 · 82分</div>
  <div class="badge badge-completed">已完成</div>
  <div class="detail">
    <div class="stats">
      <div class="stat"><div class="val">18</div><div class="lbl">发现</div></div>
      <div class="stat"><div class="val">82</div><div class="lbl">评分</div></div>
      <div class="stat"><div class="val">✓</div><div class="lbl">状态</div></div>
    </div>
    <div class="report">
      <h2>Qwen3.6-35B-A3B 概览</h2>
      <p><strong>MoE 架构</strong>，35B 总参 3B 激活，2026 年 4 月开源。<a href="#">查看来源</a></p>
      <blockquote>INT4 量化后单卡 80GB 可推理。</blockquote>
    </div>
  </div>
</div>
<div class="mag-cols">
  <div class="mag-col">
    <div class="mag-head">栏目一 · 部署</div>
    <div class="run-card">
      <div class="q">自建 NAS 的成本与长期维护</div>
      <div class="meta">13:05 · 9 发现</div>
      <div class="badge badge-researching">搜索中</div>
    </div>
    <div class="run-card">
      <div class="q">时序大模型哪家强？</div>
      <div class="meta">11:20 · 25 发现</div>
      <div class="badge badge-completed">已完成</div>
    </div>
  </div>
  <div class="mag-col">
    <div class="mag-head">栏目二 · 商业</div>
    <div class="run-card">
      <div class="q">D2C 品牌出海值得做吗</div>
      <div class="meta">12:41 · 0 发现</div>
      <div class="badge badge-failed">失败</div>
    </div>
    <div class="run-card">
      <div class="q">量子计算商用化时间表</div>
      <div class="meta">10:12 · 12 发现</div>
      <div class="badge badge-researching">搜索中</div>
    </div>
  </div>
</div>
<div class="stream-panel">
  <div class="stream-head"><span>📡 实时进度</span><span class="stream-phase">🔍 研究中</span></div>
  <div class="stream-body">
""" + STREAM_LOG + """
  </div>
</div>
""", """
/* POP 09 杂志混排 — 报纸波普 */
:root { --bg:#f0ece4; --red:#d33; --yellow:#e8b800; --ink:#1a1a1a; --dim:#666; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:Georgia, "Times New Roman", "Songti SC", serif; background:var(--bg); color:var(--ink); min-height:100vh; }
.container { max-width:960px; margin:0 auto; padding:36px 24px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:var(--red);
  border:2px solid var(--red); padding:2px 8px; z-index:9; background:var(--bg); text-transform:uppercase; letter-spacing:2px; }
header { text-align:center; padding:20px 0 14px; border-bottom:4px double var(--ink); margin-bottom:22px; }
header h1 { font-size:2.4rem; font-weight:900; letter-spacing:2px; }
header p { margin-top:6px; font-size:.85rem; font-weight:700; color:var(--dim); }
.submit-box { background:#fff; border:3px solid var(--ink); padding:16px; margin-bottom:20px; }
.submit-box textarea { width:100%; background:transparent; border:none; border-bottom:1px solid #999; padding:9px 4px; font-size:.98rem; resize:vertical; min-height:60px; font-family:Georgia, serif; color:var(--ink); }
.submit-box textarea:focus { outline:none; border-bottom-color:var(--red); }
.submit-box button { margin-top:12px; background:var(--ink); color:#fff; border:none; padding:9px 26px; font-size:.9rem; font-weight:900; letter-spacing:1px; cursor:pointer; font-family:inherit; }
.feature { background:#fff; border:3px solid var(--ink); border-top:6px solid var(--red); padding:22px; margin-bottom:20px; }
.feature-tag { display:inline-block; background:var(--red); color:#fff; font-size:.72rem; font-weight:900; padding:2px 12px; margin-bottom:10px; letter-spacing:2px; }
.feature .q { font-size:1.6rem; font-weight:900; margin-bottom:8px; }
.feature .meta { font-size:.82rem; font-weight:700; color:var(--dim); margin-bottom:10px; }
.badge { display:inline-block; padding:2px 10px; font-size:.7rem; font-weight:900; border:2px solid; }
.badge-completed { color:var(--red); border-color:var(--red); } .badge-researching { color:#1a5fb4; border-color:#1a5fb4; } .badge-failed { color:#8a1c1c; border-color:#8a1c1c; }
.feature .detail { margin-top:14px; border-top:1px solid #ccc; padding-top:14px; }
.feature .detail .stats { display:flex; gap:28px; margin:10px 0; }
.feature .detail .stat .val { font-size:1.6rem; font-weight:900; }
.feature .detail .stat .lbl { font-size:.7rem; color:var(--dim); letter-spacing:2px; text-transform:uppercase; }
.feature .detail .report { font-size:.92rem; line-height:1.8; }
.feature .detail .report h2 { font-size:1.15rem; font-weight:900; margin-bottom:6px; border-bottom:2px solid var(--yellow); display:inline-block; }
.feature .detail .report a { color:var(--red); }
.feature .detail .report blockquote { border-left:4px solid var(--yellow); margin:8px 0; padding:3px 14px; color:var(--dim); font-style:italic; }
.mag-cols { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px; }
.mag-col { background:#fff; border:2px solid var(--ink); padding:14px; }
.mag-head { font-size:.8rem; font-weight:900; letter-spacing:2px; border-bottom:2px solid var(--ink); padding-bottom:6px; margin-bottom:10px; text-transform:uppercase; }
.run-card { padding:12px 0; border-bottom:1px dashed #bbb; }
.run-card:last-child { border-bottom:none; }
.run-card .q { font-weight:900; margin-bottom:4px; }
.run-card .meta { font-size:.76rem; font-weight:700; color:var(--dim); margin-bottom:6px; }
.stream-panel { background:#fff; border:3px solid var(--ink); }
.stream-head { display:flex; align-items:center; gap:8px; padding:11px 14px; font-weight:900; background:var(--ink); color:#fff; border-bottom:3px solid var(--red); }
.stream-phase { flex:1; text-align:right; font-size:.8rem; color:var(--yellow); }
.stream-body { padding:10px 14px 12px; font-family:Consolas, monospace; font-size:.75rem; line-height:1.85; font-weight:700; color:#444; }
.stream-line.strong { color:var(--red); }
.stream-line.dim { opacity:.45; }
@media (max-width:640px) { .mag-cols { grid-template-columns:1fr; } }
"""))

# ── 10 分页橱窗: 主角卡放大 + 缩略图导航 ─────────────────────────
VARIANTS.append(("分页橱窗", """
<div class="style-tag">POP 10 · 分页橱窗</div>
<header><h1>POP SHOWCASE</h1><p>研究橱窗 — 主展位 + 缩略图导航</p></header>
<div class="submit-box">
  <textarea placeholder="输入你想研究的问题..."></textarea>
  <button>开始研究</button>
</div>
<div class="showcase">
  <div class="hero-card">
    <div class="hero-tag">当前展出</div>
    <div class="q">Qwen3.6-35B-A3B 是什么，部署需要什么硬件？</div>
    <div class="meta">14:32 · 18 发现 · 12 验证 · 82分</div>
    <div class="badge badge-completed">已完成</div>
    <div class="detail">
      <div class="report">
        <h2>Qwen3.6-35B-A3B 概览</h2>
        <p><strong>MoE 架构</strong>，35B 总参 3B 激活，2026 年 4 月开源。<a href="#">查看来源</a></p>
        <blockquote>INT4 量化后单卡 80GB 可推理。</blockquote>
        <pre><code>vllm serve Qwen/Qwen3.6-35B-A3B</code></pre>
      </div>
    </div>
  </div>
  <div class="thumbnav">
    <div class="thumb" style="background:var(--cyan);"><span class="t-q">自建 NAS 成本</span><span class="t-meta">搜索中</span></div>
    <div class="thumb" style="background:var(--yellow);"><span class="t-q">D2C 出海</span><span class="t-meta">失败</span></div>
    <div class="thumb" style="background:var(--purple); color:#fff;"><span class="t-q">时序大模型对比</span><span class="t-meta">已完成</span></div>
  </div>
</div>
<div class="stream-panel">
  <div class="stream-head"><span>📡 实时进度</span><span class="stream-phase">🔍 研究中</span></div>
  <div class="stream-body">
""" + STREAM_LOG + """
  </div>
</div>
""", """
/* POP 10 分页橱窗 — 赛博荧光 */
:root { --pink:#ff2d78; --cyan:#00e5ff; --yellow:#ffe14d; --purple:#9b5de5; --ink:#0a0a14; --bg:#12122b; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Arial Black", "Microsoft YaHei", sans-serif; background:var(--bg); color:#fff; min-height:100vh;
  background-image:linear-gradient(rgba(0,229,255,.04) 1px, transparent 1px),
  linear-gradient(90deg, rgba(0,229,255,.04) 1px, transparent 1px); background-size:32px 32px; }
.container { max-width:900px; margin:0 auto; padding:32px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:var(--bg); background:var(--cyan);
  border:3px solid #000; padding:2px 8px; z-index:9; box-shadow:4px 4px 0 var(--pink); }
header { text-align:center; padding:22px 0 18px; }
header h1 { font-size:2rem; font-weight:900; color:var(--cyan); text-shadow:0 0 16px rgba(0,229,255,.6), 4px 4px 0 var(--pink); }
header p { color:#8a8ad0; margin-top:8px; font-size:.9rem; font-weight:700; }
.submit-box { background:rgba(18,18,43,.9); border:4px solid var(--pink); padding:18px; margin-bottom:20px; box-shadow:8px 8px 0 var(--cyan); }
.submit-box textarea { width:100%; background:#0a0a20; border:3px solid #3a3a8e; padding:11px 14px; font-size:.95rem; resize:vertical; min-height:66px; font-family:inherit; color:#fff; }
.submit-box textarea:focus { outline:none; border-color:var(--cyan); }
.submit-box button { margin-top:12px; background:var(--yellow); color:var(--ink); border:3px solid #000; padding:10px 26px; font-size:1rem; font-weight:900; cursor:pointer; box-shadow:4px 4px 0 var(--pink); }
.showcase { margin-bottom:20px; }
.hero-card { background:rgba(18,18,43,.92); border:4px solid var(--cyan); padding:26px; box-shadow:10px 10px 0 var(--pink); position:relative; }
.hero-tag { position:absolute; top:-14px; left:20px; background:var(--cyan); color:var(--ink); font-weight:900; font-size:.78rem; padding:3px 12px; border:3px solid #000; box-shadow:3px 3px 0 var(--pink); }
.hero-card .q { font-size:1.7rem; font-weight:900; color:var(--cyan); text-shadow:0 0 12px rgba(0,229,255,.4); margin:6px 0 8px; }
.hero-card .meta { font-size:.82rem; font-weight:800; color:#8a8ad0; margin-bottom:12px; }
.badge { display:inline-block; padding:2px 10px; font-size:.7rem; font-weight:900; border:2px solid; }
.badge-completed { color:var(--yellow); border-color:var(--yellow); } .badge-researching { color:var(--cyan); border-color:var(--cyan); } .badge-failed { color:var(--pink); border-color:var(--pink); }
.hero-card .detail { margin-top:14px; border-top:3px dashed #3a3a8e; padding-top:14px; }
.hero-card .report { font-size:.92rem; line-height:1.8; color:#c9c9f0; }
.hero-card .report h2 { font-size:1.1rem; font-weight:900; color:var(--yellow); margin-bottom:8px; }
.hero-card .report a { color:var(--cyan); font-weight:900; }
.hero-card .report blockquote { border-left:4px solid var(--pink); margin:8px 0; padding:3px 14px; color:#8a8ad0; }
.hero-card .report code { background:#0a0a20; border:1px solid #3a3a8e; padding:1px 6px; color:var(--yellow); font-size:.85em; font-family:Consolas, monospace; }
.hero-card .report pre { background:#0a0a20; border:1px solid #3a3a8e; padding:12px; overflow-x:auto; font-family:Consolas, monospace; }
.thumbnav { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:16px; }
.thumb { border:4px solid #000; padding:14px; box-shadow:5px 5px 0 rgba(0,0,0,.4); cursor:pointer; display:flex; flex-direction:column; gap:6px; }
.thumb .t-q { font-weight:900; font-size:.82rem; }
.thumb .t-meta { font-size:.7rem; font-weight:800; opacity:.75; }
.stream-panel { background:rgba(18,18,43,.9); border:4px solid var(--purple); box-shadow:8px 8px 0 var(--cyan); }
.stream-head { display:flex; align-items:center; gap:8px; padding:11px 14px; font-weight:900; color:var(--cyan); border-bottom:3px solid #3a3a8e; }
.stream-phase { flex:1; text-align:right; font-size:.8rem; color:var(--pink); }
.stream-body { padding:10px 14px 12px; font-family:Consolas, monospace; font-size:.75rem; line-height:1.85; font-weight:700; color:#c9c9f0; }
.stream-line.strong { color:var(--yellow); }
.stream-line.dim { opacity:.4; }
@media (max-width:600px) { .thumbnav { grid-template-columns:1fr; } }
"""))

def gen(html_body: str, css: str, nn: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>POP {nn:02d} — Deep Research 波普布局预览</title>
<style>
{css.strip()}
</style>
</head>
<body>
<div class="container">
{html_body.strip()}
</div>
</body>
</html>
"""

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for i, (name, body, css) in enumerate(VARIANTS, 1):
        path = OUT / f"popart-{i:02d}-{name}.html"
        path.write_text(gen(body, css, i), encoding="utf-8")
        print(f"  wrote {path.name}")

if __name__ == "__main__":
    main()
