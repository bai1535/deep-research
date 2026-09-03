"""Generate 20 standalone theme preview pages in web/themes/.

Each page is a self-contained static demo (no backend) mirroring the
real index.html structure, with a hand-written CSS theme.  Run:
    python scripts/gen_themes.py
Output: web/themes/theme-01-<slug>.html ... theme-20-<slug>.html
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "web" / "themes"

SKELETON = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>STYLE {nn:02d} · {name} — Deep Research 主题预览</title>
<style>
{css}
</style>
</head>
<body>
<div class="style-tag">STYLE {nn:02d} · {name}</div>
<div class="container">
  <header>
    <h1>&#128269; Deep Research</h1>
    <p>多智能体深度研究 — 输入问题，获得一份有来源引用的综合报告</p>
  </header>

  <div class="submit-box">
    <textarea placeholder="输入你想研究的问题，例如：自建NAS的作用和价格、时序大模型哪个好..."></textarea>
    <button>开始研究</button>
  </div>

  <div class="stream-panel">
    <div class="stream-head"><span>&#128225; 实时进度</span><span class="stream-phase">&#128269; 研究中</span><span class="stream-toggle">&#9662;</span></div>
    <div class="stream-body">
      <div class="stream-line strong">━━━ 🔍 研究中 ━━━</div>
      <div class="stream-line">▶ 编排</div>
      <div class="stream-line dim">📋 视角构成(技术类): 原理拆解·技术专家、部署配置·技术专家、性能短板·批判者</div>
      <div class="stream-line">🔎 研究员·原理拆解 → bing_search:「Qwen3.6-35B-A3B architecture」</div>
      <div class="stream-line">📄 研究员·原理拆解 ← bing_search:「1. Qwen3.6-35B-A3B URL: https://huggingface.co/...」</div>
      <div class="stream-line">✔ 研究员·原理拆解 完成 — 4,500 tokens / $0.002</div>
    </div>
  </div>

  <div class="status-bar"><h2>研究记录</h2><span class="auto-badge"><span class="dot"></span>自动刷新中</span></div>

  <div class="run-list">
    <div class="run-card">
      <div class="top"><span class="q">Qwen3.6-35B-A3B 是什么，部署需要什么硬件？</span>
        <span class="meta"><span>14:32</span><span>18 发现 · 12 验证 · 82分</span><span class="badge badge-completed">已完成</span></span></div>
      <div class="detail open">
        <div class="stats">
          <div class="stat"><div class="val">18</div><div class="lbl">发现</div></div>
          <div class="stat"><div class="val">12</div><div class="lbl">验证</div></div>
          <div class="stat"><div class="val">82</div><div class="lbl">评分</div></div>
          <div class="stat"><div class="val">已完成</div><div class="lbl">状态</div></div>
        </div>
        <div class="report">
          <h2>Qwen3.6-35B-A3B 概览</h2>
          <p>这是报告摘要。<strong>MoE 架构</strong>，35B 总参 3B 激活，2026 年 4 月开源。<a href="#">查看来源</a></p>
          <blockquote>引用示例：INT4 量化后单卡 80GB 可推理。</blockquote>
          <pre><code>vllm serve Qwen/Qwen3.6-35B-A3B</code></pre>
        </div>
      </div>
    </div>
    <div class="run-card">
      <div class="top"><span class="q">自建 NAS 的成本与长期维护</span>
        <span class="meta"><span>13:05</span><span>9 发现 · 3 验证</span><span class="badge badge-researching">搜索中</span></span></div>
    </div>
    <div class="run-card">
      <div class="top"><span class="q">D2C 品牌出海值得做吗</span>
        <span class="meta"><span>12:41</span><span>0 发现</span><span class="badge badge-failed">失败</span></span></div>
    </div>
  </div>
</div>
</body>
</html>
"""

# ── 20 themes: (slug, display name, css) ──────────────────────────────
THEMES: list[tuple[str, str, str]] = []

THEMES.append(("neon", "赛博霓虹", """
/* 01 赛博霓虹 — 深空 + 青/品红/紫发光 */
:root {
  --bg-0: #05060f; --card: rgba(15,17,36,.66); --border: rgba(0,229,255,.16);
  --cyan: #00e5ff; --pink: #ff2d78; --purple: #a855f7;
  --green: #39ffa0; --yellow: #ffd166; --red: #ff4d6d;
  --text: #e8ebff; --dim: #8b90b8;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  font-family: -apple-system, "Segoe UI", "PingFang SC", sans-serif; color: var(--text); min-height:100vh;
  background:
    radial-gradient(1100px 700px at 85% -10%, rgba(255,45,120,.13), transparent 60%),
    radial-gradient(900px 650px at 8% 18%, rgba(0,229,255,.09), transparent 55%),
    radial-gradient(1000px 700px at 45% 115%, rgba(168,85,247,.12), transparent 60%),
    linear-gradient(180deg, #070818, #05060f 55%, #080a1a);
}
body::before { content:''; position:fixed; inset:0; pointer-events:none; z-index:0;
  background-image: linear-gradient(rgba(0,229,255,.045) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(0,229,255,.045) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(ellipse at 50% 0%, black 30%, transparent 78%);
  -webkit-mask-image: radial-gradient(ellipse at 50% 0%, black 30%, transparent 78%); }
.container { max-width:960px; margin:0 auto; padding:24px 16px; position:relative; z-index:1; }
.style-tag { position:fixed; top:12px; right:16px; font-size:.7rem; letter-spacing:2px;
  color: var(--cyan); opacity:.75; text-shadow: 0 0 8px rgba(0,229,255,.5); z-index:9; }
header { text-align:center; padding:48px 0 30px; }
header h1 { font-size:2rem; font-weight:800; letter-spacing:2px;
  background: linear-gradient(92deg, var(--cyan), var(--purple), var(--pink));
  -webkit-background-clip:text; background-clip:text; color:transparent;
  filter: drop-shadow(0 0 12px rgba(0,229,255,.35)); }
header p { color:var(--dim); margin-top:8px; font-size:.92rem; }
.submit-box { background:var(--card); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
  border:1px solid var(--border); border-radius:16px; padding:24px; margin-bottom:30px;
  box-shadow:0 0 26px rgba(0,229,255,.07); position:relative; }
.submit-box::before { content:''; position:absolute; top:-1px; left:12%; right:12%; height:1px;
  background:linear-gradient(90deg, transparent, var(--cyan), var(--pink), transparent);
  filter:drop-shadow(0 0 6px rgba(0,229,255,.6)); }
.submit-box textarea { width:100%; background:rgba(4,6,14,.72); border:1px solid rgba(0,229,255,.14);
  border-radius:10px; color:var(--text); padding:14px 16px; font-size:1rem; resize:vertical;
  min-height:80px; font-family:inherit; }
.submit-box textarea:focus { outline:none; border-color:var(--cyan); box-shadow:0 0 14px rgba(0,229,255,.22); }
.submit-box button { margin-top:14px; background:linear-gradient(135deg, var(--pink), var(--purple));
  color:#fff; border:none; border-radius:10px; padding:12px 30px; font-size:1rem; font-weight:700;
  cursor:pointer; box-shadow:0 0 20px rgba(255,45,120,.35); }
.stream-panel { background:var(--card); backdrop-filter:blur(12px); border:1px solid rgba(0,229,255,.22);
  border-radius:13px; margin-bottom:16px; overflow:hidden; box-shadow:0 0 24px rgba(0,229,255,.08); }
.stream-head { display:flex; align-items:center; gap:12px; padding:13px 16px; font-weight:700; }
.stream-head::before { content:''; width:8px; height:8px; border-radius:50%; background:var(--green);
  box-shadow:0 0 8px var(--green); animation:pulse 1.8s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.25} }
.stream-phase { flex:1; text-align:right; color:var(--cyan); font-size:.82rem; text-shadow:0 0 8px rgba(0,229,255,.5); }
.stream-toggle { color:var(--dim); }
.stream-body { max-height:300px; overflow-y:auto; padding:10px 16px 14px; border-top:1px solid rgba(0,229,255,.14);
  background:rgba(2,4,12,.82); font-family:Consolas, monospace; font-size:.78rem; line-height:1.85; }
.stream-line { color:rgba(139,144,184,.9); }
.stream-line.strong { color:var(--cyan); font-weight:700; text-shadow:0 0 8px rgba(0,229,255,.45); }
.stream-line.dim { color:var(--dim); opacity:.6; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; text-shadow:0 0 10px rgba(0,229,255,.4); }
.auto-badge { font-size:.75rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:7px; height:7px; border-radius:50%; background:var(--green); box-shadow:0 0 8px var(--green); animation:pulse 2s infinite; }
.run-list { display:flex; flex-direction:column; gap:11px; }
.run-card { background:var(--card); backdrop-filter:blur(10px); border:1px solid var(--border);
  border-radius:13px; padding:16px 20px; cursor:pointer; box-shadow:0 0 14px rgba(0,229,255,.04); }
.run-card:hover { border-color:rgba(0,229,255,.5); box-shadow:0 0 26px rgba(0,229,255,.16); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.82rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:3px 11px; border-radius:14px; font-size:.75rem; font-weight:700; border:1px solid transparent; }
.badge-completed { background:rgba(57,255,160,.1); color:var(--green); border-color:rgba(57,255,160,.4); box-shadow:0 0 10px rgba(57,255,160,.22); }
.badge-researching { background:rgba(0,229,255,.1); color:var(--cyan); border-color:rgba(0,229,255,.4); box-shadow:0 0 10px rgba(0,229,255,.22); }
.badge-failed { background:rgba(255,77,109,.1); color:var(--red); border-color:rgba(255,77,109,.4); box-shadow:0 0 10px rgba(255,77,109,.22); }
.detail { background:var(--card); border:1px solid var(--border); border-radius:13px; padding:18px 22px; margin-top:14px; }
.detail .stats { display:flex; gap:26px; margin:12px 0; flex-wrap:wrap; }
.detail .stats .stat { text-align:center; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:800;
  background:linear-gradient(90deg, var(--cyan), var(--purple));
  -webkit-background-clip:text; background-clip:text; color:transparent; }
.detail .stats .stat .lbl { font-size:.75rem; color:var(--dim); }
.detail .report { background:rgba(4,6,14,.78); border:1px solid rgba(0,229,255,.12); border-radius:10px;
  padding:18px 22px; margin-top:14px; font-size:.92rem; line-height:1.7; }
.detail .report h2 { color:var(--cyan); margin:0 0 8px; text-shadow:0 0 10px rgba(0,229,255,.3); }
.detail .report a { color:var(--cyan); text-decoration:none; }
.detail .report blockquote { border-left:3px solid var(--purple); margin:8px 0; padding:4px 12px; color:var(--dim); }
.detail .report code { background:rgba(168,85,247,.14); color:#d8b4fe; padding:2px 6px; border-radius:4px; font-size:.85em; }
.detail .report pre { background:rgba(2,4,12,.9); border:1px solid rgba(0,229,255,.12); padding:12px; border-radius:8px; overflow-x:auto; }
::-webkit-scrollbar { width:9px; }
::-webkit-scrollbar-thumb { background:rgba(0,229,255,.22); border-radius:5px; }
::selection { background:rgba(0,229,255,.25); }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("minimal", "极简白", """
/* 02 极简白 — 留白、细线、无装饰 */
:root { --bg:#fff; --card:#fff; --border:#e5e7eb; --text:#111827; --dim:#9ca3af;
  --cyan:#3b82f6; --green:#16a34a; --yellow:#ca8a04; --red:#dc2626; --purple:#7c3aed; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, "Segoe UI", "PingFang SC", sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
.container { max-width:860px; margin:0 auto; padding:48px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; letter-spacing:2px; color:var(--dim); z-index:9; }
header { padding:24px 0 40px; }
header h1 { font-size:1.6rem; font-weight:600; letter-spacing:-0.5px; }
header p { color:var(--dim); margin-top:6px; font-size:.9rem; }
.submit-box { border-bottom:1px solid var(--border); padding-bottom:32px; margin-bottom:36px; }
.submit-box textarea { width:100%; border:1px solid var(--border); border-radius:8px; padding:14px 16px; font-size:1rem; resize:vertical; min-height:80px; font-family:inherit; color:var(--text); }
.submit-box textarea:focus { outline:none; border-color:var(--cyan); }
.submit-box button { margin-top:14px; background:var(--text); color:#fff; border:none; border-radius:6px; padding:11px 26px; font-size:.95rem; font-weight:500; cursor:pointer; }
.stream-panel { border:1px solid var(--border); border-radius:8px; margin-bottom:32px; overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:10px; padding:12px 16px; font-weight:600; font-size:.9rem; border-bottom:1px solid var(--border); }
.stream-phase { flex:1; text-align:right; color:var(--dim); font-size:.8rem; font-weight:400; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:10px 16px 14px; font-family:ui-monospace, Consolas, monospace; font-size:.76rem; line-height:1.9; color:#374151; }
.stream-line.strong { color:var(--text); font-weight:600; }
.stream-line.dim { color:#d1d5db; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.05rem; font-weight:600; }
.auto-badge { font-size:.75rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:6px; height:6px; border-radius:50%; background:var(--green); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:0; }
.run-card { border-bottom:1px solid var(--border); padding:18px 4px; cursor:pointer; }
.run-card:hover .q { color:var(--cyan); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:500; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; transition:color .15s; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.72rem; font-weight:500; border:1px solid var(--border); color:var(--dim); }
.badge-completed { color:var(--green); border-color:rgba(22,163,74,.3); }
.badge-researching { color:var(--cyan); border-color:rgba(59,130,246,.3); }
.badge-failed { color:var(--red); border-color:rgba(220,38,38,.3); }
.detail { padding:20px 4px 8px; }
.detail .stats { display:flex; gap:32px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.4rem; font-weight:700; }
.detail .stats .stat .lbl { font-size:.72rem; color:var(--dim); }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.75; color:#374151; }
.detail .report h2 { font-size:1.05rem; font-weight:600; margin-bottom:8px; }
.detail .report a { color:var(--cyan); text-decoration:none; }
.detail .report blockquote { border-left:2px solid var(--border); margin:8px 0; padding:2px 14px; color:var(--dim); }
.detail .report code { background:#f3f4f6; padding:2px 6px; border-radius:4px; font-size:.85em; }
.detail .report pre { background:#f9fafb; border:1px solid var(--border); padding:12px; border-radius:6px; overflow-x:auto; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("paper", "纸质复古", """
/* 03 纸质复古 — 米黄纸、衬线、文章排版 */
:root { --paper:#f5f0e6; --ink:#2f2a22; --faint:#8a8171; --accent:#b5412f; --border:#ddd3c0; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:Georgia, "Songti SC", "Noto Serif SC", serif; background:var(--paper); color:var(--ink); min-height:100vh; }
.container { max-width:780px; margin:0 auto; padding:48px 24px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; letter-spacing:2px; color:var(--faint); z-index:9; }
header { text-align:center; padding:32px 0 40px; border-bottom:2px solid var(--ink); }
header h1 { font-size:1.9rem; font-weight:700; letter-spacing:3px; }
header p { color:var(--faint); margin-top:10px; font-size:.9rem; font-style:italic; }
.submit-box { padding:28px 0; border-bottom:1px solid var(--border); margin-bottom:32px; }
.submit-box textarea { width:100%; background:rgba(255,255,255,.5); border:1px solid var(--border); border-radius:4px; padding:14px 16px; font-size:1rem; resize:vertical; min-height:80px; font-family:inherit; color:var(--ink); }
.submit-box textarea:focus { outline:none; border-color:var(--accent); }
.submit-box button { margin-top:14px; background:var(--accent); color:#fdfaf3; border:none; border-radius:3px; padding:11px 28px; font-size:.95rem; font-weight:600; letter-spacing:2px; cursor:pointer; font-family:inherit; }
.stream-panel { border:1px solid var(--border); background:rgba(255,255,255,.35); margin-bottom:32px; }
.stream-head { display:flex; align-items:center; gap:10px; padding:12px 16px; font-weight:700; border-bottom:1px solid var(--border); }
.stream-phase { flex:1; text-align:right; color:var(--accent); font-size:.8rem; font-weight:400; font-style:italic; }
.stream-toggle { color:var(--faint); }
.stream-body { padding:12px 16px; font-family:Georgia, serif; font-size:.8rem; line-height:2; color:#5d5546; }
.stream-line.strong { color:var(--ink); font-weight:700; }
.stream-line.dim { color:#b8af9c; font-style:italic; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:700; letter-spacing:2px; }
.auto-badge { font-size:.75rem; color:var(--faint); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:6px; height:6px; border-radius:50%; background:var(--accent); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:0; }
.run-card { border-bottom:1px solid var(--border); padding:18px 4px; cursor:pointer; }
.run-card:hover .q { color:var(--accent); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:var(--faint); flex-shrink:0; }
.badge { display:inline-block; padding:2px 10px; font-size:.72rem; border:1px solid var(--border); color:var(--faint); border-radius:2px; }
.badge-completed { color:var(--accent); border-color:rgba(181,65,47,.4); }
.badge-researching { color:#7c6a2e; border-color:rgba(124,106,46,.4); }
.badge-failed { color:#9a3b3b; border-color:rgba(154,59,59,.4); }
.detail { padding:20px 4px 8px; }
.detail .stats { display:flex; gap:32px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:700; font-family:Georgia, serif; }
.detail .stats .stat .lbl { font-size:.72rem; color:var(--faint); letter-spacing:1px; }
.detail .report { margin-top:14px; font-size:.95rem; line-height:1.9; color:#4a4338; }
.detail .report h2 { font-size:1.15rem; font-weight:700; margin-bottom:10px; border-bottom:1px solid var(--border); padding-bottom:6px; }
.detail .report a { color:var(--accent); }
.detail .report blockquote { border-left:3px solid var(--accent); margin:10px 0; padding:4px 16px; color:var(--faint); font-style:italic; }
.detail .report code { background:rgba(181,65,47,.08); padding:2px 6px; font-size:.85em; font-family:Consolas, monospace; }
.detail .report pre { background:rgba(255,255,255,.5); border:1px solid var(--border); padding:12px; overflow-x:auto; font-family:Consolas, monospace; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("apple", "苹果风", """
/* 04 苹果风 — 浅灰、毛玻璃、大圆角 */
:root { --bg:#f5f5f7; --card:rgba(255,255,255,.72); --border:rgba(0,0,0,.08); --text:#1d1d1f;
  --accent:#0071e3; --green:#34c759; --yellow:#ff9f0a; --red:#ff3b30; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, BlinkMacSystemFont, "SF Pro SC", "PingFang SC", sans-serif;
  background:var(--bg); color:var(--text); min-height:100vh;
  -webkit-font-smoothing:antialiased; }
.container { max-width:860px; margin:0 auto; padding:48px 20px; }
.style-tag { position:fixed; top:16px; right:20px; font-size:.68rem; color:rgba(0,0,0,.35); z-index:9; }
header { text-align:center; padding:32px 0 40px; }
header h1 { font-size:2.2rem; font-weight:700; letter-spacing:-1px; }
header p { color:rgba(0,0,0,.5); margin-top:10px; font-size:.95rem; }
.submit-box { background:var(--card); backdrop-filter:blur(20px) saturate(180%); -webkit-backdrop-filter:blur(20px) saturate(180%);
  border:1px solid var(--border); border-radius:22px; padding:26px; margin-bottom:30px; box-shadow:0 8px 32px rgba(0,0,0,.06); }
.submit-box textarea { width:100%; background:rgba(255,255,255,.85); border:1px solid var(--border); border-radius:14px;
  padding:14px 18px; font-size:1rem; resize:vertical; min-height:80px; font-family:inherit; color:var(--text); }
.submit-box textarea:focus { outline:none; border-color:var(--accent); box-shadow:0 0 0 4px rgba(0,113,227,.15); }
.submit-box button { margin-top:14px; background:var(--accent); color:#fff; border:none; border-radius:980px;
  padding:11px 30px; font-size:1rem; font-weight:500; cursor:pointer; transition:transform .15s, opacity .15s; }
.submit-box button:hover { opacity:.9; transform:scale(1.02); }
.stream-panel { background:var(--card); backdrop-filter:blur(20px) saturate(180%); -webkit-backdrop-filter:blur(20px) saturate(180%);
  border:1px solid var(--border); border-radius:18px; margin-bottom:24px; overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:10px; padding:14px 18px; font-weight:600; font-size:.92rem; }
.stream-phase { flex:1; text-align:right; color:var(--accent); font-size:.82rem; font-weight:500; }
.stream-toggle { color:rgba(0,0,0,.35); }
.stream-body { padding:12px 18px 14px; font-family:ui-monospace, SF Mono, Consolas, monospace; font-size:.77rem; line-height:1.9; color:rgba(0,0,0,.65); background:rgba(255,255,255,.5); border-top:1px solid var(--border); }
.stream-line.strong { color:var(--text); font-weight:600; }
.stream-line.dim { color:rgba(0,0,0,.3); }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:600; }
.auto-badge { font-size:.75rem; color:rgba(0,0,0,.45); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:7px; height:7px; border-radius:50%; background:var(--green); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:12px; }
.run-card { background:var(--card); backdrop-filter:blur(20px) saturate(180%); -webkit-backdrop-filter:blur(20px) saturate(180%);
  border:1px solid var(--border); border-radius:18px; padding:18px 22px; cursor:pointer; box-shadow:0 4px 20px rgba(0,0,0,.05); }
.run-card:hover { box-shadow:0 8px 30px rgba(0,0,0,.1); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:rgba(0,0,0,.45); flex-shrink:0; }
.badge { display:inline-block; padding:3px 12px; border-radius:999px; font-size:.72rem; font-weight:600; }
.badge-completed { background:rgba(52,199,89,.12); color:var(--green); }
.badge-researching { background:rgba(0,113,227,.1); color:var(--accent); }
.badge-failed { background:rgba(255,59,48,.1); color:var(--red); }
.detail { background:var(--card); border:1px solid var(--border); border-radius:18px; padding:20px 24px; margin-top:14px; }
.detail .stats { display:flex; gap:32px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:700; }
.detail .stats .stat .lbl { font-size:.72rem; color:rgba(0,0,0,.45); }
.detail .report { margin-top:14px; font-size:.93rem; line-height:1.75; color:rgba(0,0,0,.75); }
.detail .report h2 { font-size:1.1rem; font-weight:700; margin-bottom:8px; }
.detail .report a { color:var(--accent); text-decoration:none; }
.detail .report blockquote { border-left:3px solid rgba(0,0,0,.15); margin:8px 0; padding:4px 14px; color:rgba(0,0,0,.5); }
.detail .report code { background:rgba(0,0,0,.06); padding:2px 6px; border-radius:6px; font-size:.85em; }
.detail .report pre { background:rgba(0,0,0,.05); border-radius:10px; padding:12px; overflow-x:auto; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("deepspace", "深空科技", """
/* 05 深空科技 — 深蓝渐变、星空、科技蓝 */
:root { --bg-0:#020617; --bg-1:#0f172a; --card:rgba(15,23,42,.8); --border:rgba(148,163,184,.15);
  --accent:#38bdf8; --green:#34d399; --yellow:#fbbf24; --red:#f87171; --text:#e2e8f0; --dim:#64748b; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, "Segoe UI", "PingFang SC", sans-serif; color:var(--text); min-height:100vh;
  background:radial-gradient(1200px 600px at 50% -20%, rgba(56,189,248,.08), transparent 60%),
  linear-gradient(180deg, var(--bg-0), var(--bg-1) 60%, #020617); }
/* 星空点点 */
body::before { content:''; position:fixed; inset:0; pointer-events:none; z-index:0;
  background-image: radial-gradient(1.5px 1.5px at 20% 30%, rgba(255,255,255,.5), transparent),
                    radial-gradient(1px 1px at 40% 70%, rgba(255,255,255,.4), transparent),
                    radial-gradient(1.5px 1.5px at 60% 20%, rgba(255,255,255,.35), transparent),
                    radial-gradient(1px 1px at 80% 50%, rgba(255,255,255,.45), transparent),
                    radial-gradient(1.5px 1.5px at 90% 80%, rgba(255,255,255,.3), transparent),
                    radial-gradient(1px 1px at 10% 85%, rgba(255,255,255,.4), transparent),
                    radial-gradient(1px 1px at 50% 45%, rgba(255,255,255,.3), transparent),
                    radial-gradient(1px 1px at 30% 55%, rgba(255,255,255,.35), transparent),
                    radial-gradient(1.5px 1.5px at 75% 15%, rgba(255,255,255,.4), transparent),
                    radial-gradient(1px 1px at 65% 65%, rgba(255,255,255,.3), transparent); }
.container { max-width:900px; margin:0 auto; padding:40px 20px; position:relative; z-index:1; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; letter-spacing:2px; color:var(--accent); opacity:.7; z-index:9; }
header { text-align:center; padding:40px 0 32px; }
header h1 { font-size:1.9rem; font-weight:700; letter-spacing:1px; color:#f0f9ff; }
header h1 span, header h1 { text-shadow:0 0 20px rgba(56,189,248,.35); }
header p { color:var(--dim); margin-top:8px; font-size:.92rem; }
.submit-box { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:24px; margin-bottom:28px;
  box-shadow:0 4px 30px rgba(0,0,0,.4); }
.submit-box textarea { width:100%; background:rgba(2,6,23,.7); border:1px solid var(--border); border-radius:8px;
  padding:14px 16px; font-size:1rem; resize:vertical; min-height:80px; font-family:inherit; color:var(--text); }
.submit-box textarea:focus { outline:none; border-color:var(--accent); box-shadow:0 0 0 3px rgba(56,189,248,.15); }
.submit-box button { margin-top:14px; background:linear-gradient(135deg, #0ea5e9, #2563eb); color:#fff; border:none;
  border-radius:8px; padding:12px 30px; font-size:1rem; font-weight:600; cursor:pointer; }
.stream-panel { background:var(--card); border:1px solid var(--border); border-radius:12px; margin-bottom:24px; overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:10px; padding:13px 16px; font-weight:600; font-size:.9rem; color:#f0f9ff; }
.stream-phase { flex:1; text-align:right; color:var(--accent); font-size:.82rem; font-weight:500; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:11px 16px 14px; border-top:1px solid var(--border); font-family:Consolas, monospace; font-size:.77rem; line-height:1.9; color:rgba(226,232,240,.75); }
.stream-line.strong { color:var(--accent); font-weight:700; }
.stream-line.dim { color:rgba(100,116,139,.7); }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:600; color:#f0f9ff; }
.auto-badge { font-size:.75rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:7px; height:7px; border-radius:50%; background:var(--green); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:10px; }
.run-card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 20px; cursor:pointer; }
.run-card:hover { border-color:rgba(56,189,248,.4); box-shadow:0 0 20px rgba(56,189,248,.08); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:3px 11px; border-radius:999px; font-size:.72rem; font-weight:600; border:1px solid; }
.badge-completed { color:var(--green); border-color:rgba(52,211,153,.4); background:rgba(52,211,153,.08); }
.badge-researching { color:var(--accent); border-color:rgba(56,189,248,.4); background:rgba(56,189,248,.08); }
.badge-failed { color:var(--red); border-color:rgba(248,113,113,.4); background:rgba(248,113,113,.08); }
.detail { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:18px 22px; margin-top:12px; }
.detail .stats { display:flex; gap:30px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.45rem; font-weight:700; color:#f0f9ff; }
.detail .stats .stat .lbl { font-size:.72rem; color:var(--dim); }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.75; color:rgba(226,232,240,.85); }
.detail .report h2 { color:var(--accent); margin-bottom:8px; font-size:1.05rem; }
.detail .report a { color:var(--accent); text-decoration:none; }
.detail .report blockquote { border-left:3px solid var(--accent); margin:8px 0; padding:4px 14px; color:var(--dim); }
.detail .report code { background:rgba(56,189,248,.1); padding:2px 6px; border-radius:4px; font-size:.85em; color:#7dd3fc; }
.detail .report pre { background:rgba(2,6,23,.8); border:1px solid var(--border); padding:12px; border-radius:8px; overflow-x:auto; }
::-webkit-scrollbar { width:8px; }
::-webkit-scrollbar-thumb { background:rgba(56,189,248,.25); border-radius:4px; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("glass", "玻璃拟态", """
/* 06 玻璃拟态 — 彩色渐变底 + 磨砂玻璃卡片 */
:root { --text:#1e1b4b; --dim:#6d6a9e; --white:rgba(255,255,255,.55); }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, "Segoe UI", "PingFang SC", sans-serif; color:var(--text); min-height:100vh;
  background:linear-gradient(135deg, #a78bfa 0%, #f472b6 30%, #fb923c 55%, #34d399 80%, #22d3ee 100%); }
body::before { content:''; position:fixed; inset:0; pointer-events:none; z-index:0;
  background:radial-gradient(600px 400px at 15% 20%, rgba(255,255,255,.25), transparent 60%),
  radial-gradient(500px 350px at 85% 75%, rgba(255,255,255,.2), transparent 60%); }
.container { max-width:880px; margin:0 auto; padding:40px 20px; position:relative; z-index:1; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; letter-spacing:2px; color:rgba(255,255,255,.85); text-shadow:0 1px 4px rgba(0,0,0,.2); z-index:9; }
header { text-align:center; padding:36px 0 30px; }
header h1 { font-size:2rem; font-weight:800; color:#fff; text-shadow:0 2px 12px rgba(0,0,0,.2); }
header p { color:rgba(255,255,255,.85); margin-top:8px; font-size:.92rem; }
.glass { background:var(--white); backdrop-filter:blur(18px) saturate(160%); -webkit-backdrop-filter:blur(18px) saturate(160%);
  border:1px solid rgba(255,255,255,.6); border-radius:20px; box-shadow:0 8px 32px rgba(31,38,135,.15); }
.submit-box { padding:24px; margin-bottom:26px; }
.submit-box textarea { width:100%; background:rgba(255,255,255,.6); border:1px solid rgba(255,255,255,.7);
  border-radius:12px; padding:14px 16px; font-size:1rem; resize:vertical; min-height:80px; font-family:inherit; color:var(--text); }
.submit-box textarea:focus { outline:none; border-color:rgba(255,255,255,.95); }
.submit-box button { margin-top:14px; background:rgba(255,255,255,.8); color:var(--text); border:none;
  border-radius:12px; padding:12px 30px; font-size:1rem; font-weight:700; cursor:pointer; backdrop-filter:blur(8px); }
.stream-panel { margin-bottom:22px; overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:10px; padding:14px 18px; font-weight:700; font-size:.92rem; }
.stream-phase { flex:1; text-align:right; color:#7c3aed; font-size:.82rem; font-weight:600; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:12px 18px 14px; border-top:1px solid rgba(255,255,255,.6); font-family:Consolas, monospace;
  font-size:.77rem; line-height:1.9; color:#4c4891; }
.stream-line.strong { color:#7c3aed; font-weight:700; }
.stream-line.dim { color:rgba(109,106,158,.6); }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:700; color:#fff; text-shadow:0 1px 6px rgba(0,0,0,.2); }
.auto-badge { font-size:.75rem; color:rgba(255,255,255,.9); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:7px; height:7px; border-radius:50%; background:#fff; animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:12px; }
.run-card { padding:18px 22px; cursor:pointer; }
.run-card:hover { box-shadow:0 12px 40px rgba(31,38,135,.25); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:700; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:3px 12px; border-radius:999px; font-size:.72rem; font-weight:700; background:rgba(255,255,255,.7); }
.badge-completed { color:#059669; }
.badge-researching { color:#7c3aed; }
.badge-failed { color:#e11d48; }
.detail { padding:18px 22px; margin-top:12px; }
.detail .stats { display:flex; gap:30px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:800; }
.detail .stats .stat .lbl { font-size:.72rem; color:var(--dim); }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.75; color:#4c4891; }
.detail .report h2 { color:#7c3aed; margin-bottom:8px; }
.detail .report a { color:#7c3aed; text-decoration:none; }
.detail .report blockquote { border-left:3px solid rgba(124,58,237,.4); margin:8px 0; padding:4px 14px; color:var(--dim); }
.detail .report code { background:rgba(255,255,255,.7); padding:2px 6px; border-radius:6px; font-size:.85em; }
.detail .report pre { background:rgba(255,255,255,.65); border-radius:10px; padding:12px; overflow-x:auto; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("terminal", "终端暗黑", """
/* 07 终端暗黑 — 纯黑底、荧光绿等宽字、CRT */
:root { --bg:#0a0f0a; --card:#0d130d; --border:#1c2a1c; --text:#33ff66; --dim:#1f6b3a;
  --green:#33ff66; --yellow:#d4ff4f; --red:#ff5555; --cyan:#33e0ff; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Cascadia Code", "Fira Code", Consolas, monospace; background:var(--bg); color:var(--text); min-height:100vh; }
/* CRT scanline */
body::after { content:''; position:fixed; inset:0; pointer-events:none; z-index:2;
  background:repeating-linear-gradient(0deg, rgba(0,0,0,.18) 0px, rgba(0,0,0,.18) 1px, transparent 1px, transparent 3px); }
.container { max-width:900px; margin:0 auto; padding:36px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; color:var(--dim); z-index:9; }
header { text-align:center; padding:36px 0 30px; }
header h1 { font-size:1.8rem; font-weight:700; letter-spacing:2px; text-shadow:0 0 12px rgba(51,255,102,.5); }
header p { color:var(--dim); margin-top:8px; font-size:.85rem; }
.submit-box { border:1px solid var(--border); padding:20px; margin-bottom:24px; background:var(--card); }
.submit-box textarea { width:100%; background:#060906; border:1px solid var(--border); color:var(--text);
  padding:12px 14px; font-size:.95rem; resize:vertical; min-height:80px; font-family:inherit; caret-color:var(--green); }
.submit-box textarea:focus { outline:none; border-color:var(--green); box-shadow:0 0 10px rgba(51,255,102,.2); }
.submit-box button { margin-top:12px; background:transparent; color:var(--green); border:1px solid var(--green);
  padding:10px 26px; font-size:.9rem; font-weight:700; letter-spacing:1px; cursor:pointer; font-family:inherit; }
.submit-box button:hover { background:rgba(51,255,102,.1); box-shadow:0 0 12px rgba(51,255,102,.3); }
.stream-panel { border:1px solid var(--border); margin-bottom:22px; background:var(--card); }
.stream-head { display:flex; align-items:center; gap:10px; padding:11px 14px; font-weight:700; border-bottom:1px solid var(--border); font-size:.85rem; }
.stream-phase { flex:1; text-align:right; color:var(--cyan); font-size:.8rem; font-weight:400; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:10px 14px 12px; font-size:.77rem; line-height:1.9; }
.stream-line.strong { color:var(--green); font-weight:700; }
.stream-line.dim { color:var(--dim); }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.status-bar h2 { font-size:1rem; font-weight:700; }
.auto-badge { font-size:.72rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:7px; height:7px; border-radius:50%; background:var(--green); animation:pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.2} }
.run-list { display:flex; flex-direction:column; gap:8px; }
.run-card { border:1px solid var(--border); padding:14px 16px; cursor:pointer; background:var(--card); }
.run-card:hover { border-color:var(--green); box-shadow:0 0 10px rgba(51,255,102,.15); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.76rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:2px 10px; font-size:.7rem; font-weight:700; border:1px solid; }
.badge-completed { color:var(--green); border-color:var(--green); }
.badge-researching { color:var(--cyan); border-color:var(--cyan); }
.badge-failed { color:var(--red); border-color:var(--red); }
.detail { border:1px solid var(--border); padding:16px 18px; margin-top:10px; background:#060906; }
.detail .stats { display:flex; gap:28px; margin:10px 0; }
.detail .stats .stat .val { font-size:1.4rem; font-weight:700; color:var(--green); text-shadow:0 0 8px rgba(51,255,102,.5); }
.detail .stats .stat .lbl { font-size:.7rem; color:var(--dim); }
.detail .report { margin-top:12px; font-size:.88rem; line-height:1.8; color:#7dffa3; }
.detail .report h2 { color:var(--green); margin-bottom:8px; font-size:1rem; }
.detail .report a { color:var(--cyan); }
.detail .report blockquote { border-left:2px solid var(--green); margin:8px 0; padding:4px 12px; color:var(--dim); }
.detail .report code { background:rgba(51,255,102,.08); padding:2px 6px; color:var(--yellow); font-size:.85em; }
.detail .report pre { background:#020402; border:1px solid var(--border); padding:12px; overflow-x:auto; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("neumorph", "新拟物", """
/* 08 新拟物 Neumorphism — 浅灰底、内凹/外凸浮雕 */
:root { --bg:#e4ebf1; --shadow-dark:#c8d0d9; --shadow-light:#ffffff; --text:#3d4a5c; --dim:#8a96a8;
  --green:#3eb489; --cyan:#4aa8d8; --red:#d96a6a; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, "Segoe UI", "PingFang SC", sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
.container { max-width:880px; margin:0 auto; padding:40px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; color:var(--dim); z-index:9; }
header { text-align:center; padding:36px 0 30px; }
header h1 { font-size:1.8rem; font-weight:700; color:#5a6a80; text-shadow:2px 2px 4px var(--shadow-dark), -2px -2px 4px var(--shadow-light); }
header p { color:var(--dim); margin-top:8px; font-size:.92rem; }
.soft { border-radius:18px; background:var(--bg); box-shadow:8px 8px 20px var(--shadow-dark), -8px -8px 20px var(--shadow-light); }
.submit-box { padding:24px; margin-bottom:26px; }
.submit-box textarea { width:100%; background:var(--bg); border:none; border-radius:12px; color:var(--text);
  padding:14px 16px; font-size:1rem; resize:vertical; min-height:80px; font-family:inherit;
  box-shadow:inset 4px 4px 10px var(--shadow-dark), inset -4px -4px 10px var(--shadow-light); }
.submit-box textarea:focus { outline:none; }
.submit-box button { margin-top:14px; background:var(--bg); color:var(--green); border:none; border-radius:12px;
  padding:12px 30px; font-size:1rem; font-weight:700; cursor:pointer;
  box-shadow:6px 6px 14px var(--shadow-dark), -6px -6px 14px var(--shadow-light); }
.submit-box button:active { box-shadow:inset 4px 4px 10px var(--shadow-dark), inset -4px -4px 10px var(--shadow-light); }
.stream-panel { margin-bottom:22px; overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:10px; padding:14px 18px; font-weight:700; }
.stream-phase { flex:1; text-align:right; color:var(--cyan); font-size:.82rem; font-weight:500; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:12px 18px 14px; font-family:Consolas, monospace; font-size:.77rem; line-height:1.9; color:#66758a; }
.stream-line.strong { color:var(--green); font-weight:700; }
.stream-line.dim { color:#aab4c2; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:700; color:#5a6a80; }
.auto-badge { font-size:.75rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:7px; height:7px; border-radius:50%; background:var(--green); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:14px; }
.run-card { padding:18px 22px; cursor:pointer; }
.run-card:hover { box-shadow:4px 4px 14px var(--shadow-dark), -4px -4px 14px var(--shadow-light); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:4px 13px; border-radius:12px; font-size:.72rem; font-weight:700;
  box-shadow:3px 3px 8px var(--shadow-dark), -3px -3px 8px var(--shadow-light); }
.badge-completed { color:var(--green); }
.badge-researching { color:var(--cyan); }
.badge-failed { color:var(--red); }
.detail { padding:18px 22px; margin-top:14px; }
.detail .stats { display:flex; gap:30px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:700; color:#5a6a80; }
.detail .stats .stat .lbl { font-size:.72rem; color:var(--dim); }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.75; color:#66758a; }
.detail .report h2 { color:#5a6a80; margin-bottom:8px; }
.detail .report a { color:var(--cyan); text-decoration:none; }
.detail .report blockquote { border-left:3px solid var(--green); margin:8px 0; padding:4px 14px; color:var(--dim); }
.detail .report code { background:var(--bg); padding:2px 6px; border-radius:6px; font-size:.85em;
  box-shadow:inset 2px 2px 5px var(--shadow-dark), inset -2px -2px 5px var(--shadow-light); }
.detail .report pre { background:var(--bg); border-radius:10px; padding:12px; overflow-x:auto;
  box-shadow:inset 3px 3px 8px var(--shadow-dark), inset -3px -3px 8px var(--shadow-light); }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("vivid", "活力渐变", """
/* 09 活力渐变 — 明亮多色、圆润活泼 */
:root { --text:#5b21b6; --dim:#9d7dd8; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, "Segoe UI", "PingFang SC", sans-serif; color:var(--text); min-height:100vh;
  background:linear-gradient(135deg, #fde68a 0%, #f9a8d4 30%, #c4b5fd 60%, #a5f3fc 100%); }
body::before { content:''; position:fixed; inset:0; pointer-events:none; z-index:0;
  background:radial-gradient(400px 300px at 80% 15%, rgba(255,255,255,.4), transparent 60%),
  radial-gradient(350px 280px at 10% 80%, rgba(255,255,255,.35), transparent 60%); }
.container { max-width:860px; margin:0 auto; padding:40px 20px; position:relative; z-index:1; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:700; color:var(--text); opacity:.6; z-index:9; }
header { text-align:center; padding:36px 0 30px; }
header h1 { font-size:2rem; font-weight:800; color:#fff; text-shadow:0 2px 10px rgba(91,33,182,.3); }
header p { color:rgba(91,33,182,.75); margin-top:8px; font-size:.92rem; font-weight:500; }
.submit-box { background:rgba(255,255,255,.75); backdrop-filter:blur(10px); border-radius:24px; padding:24px; margin-bottom:24px;
  box-shadow:0 10px 40px rgba(91,33,182,.12); }
.submit-box textarea { width:100%; background:#fff; border:2px solid transparent; border-radius:16px;
  padding:14px 16px; font-size:1rem; resize:vertical; min-height:80px; font-family:inherit; color:var(--text); }
.submit-box textarea:focus { outline:none; border-color:#c4b5fd; }
.submit-box button { margin-top:14px; background:linear-gradient(135deg, #f472b6, #8b5cf6); color:#fff; border:none;
  border-radius:999px; padding:12px 32px; font-size:1rem; font-weight:700; cursor:pointer;
  box-shadow:0 6px 20px rgba(139,92,246,.35); transition:transform .15s; }
.submit-box button:hover { transform:scale(1.04); }
.stream-panel { background:rgba(255,255,255,.75); backdrop-filter:blur(10px); border-radius:20px; margin-bottom:22px; overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:10px; padding:14px 18px; font-weight:700; font-size:.92rem; }
.stream-phase { flex:1; text-align:right; color:#8b5cf6; font-size:.82rem; font-weight:600; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:12px 18px 14px; border-top:2px dashed rgba(139,92,246,.2); font-family:Consolas, monospace;
  font-size:.77rem; line-height:1.9; color:#7c6bb8; }
.stream-line.strong { color:#8b5cf6; font-weight:700; }
.stream-line.dim { color:rgba(157,125,216,.6); }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:800; color:#fff; text-shadow:0 2px 8px rgba(91,33,182,.35); }
.auto-badge { font-size:.75rem; color:var(--text); font-weight:600; display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:8px; height:8px; border-radius:50%; background:#f472b6; animation:pulse 1.8s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:12px; }
.run-card { background:rgba(255,255,255,.75); backdrop-filter:blur(10px); border-radius:18px; padding:18px 22px; cursor:pointer; }
.run-card:hover { box-shadow:0 10px 30px rgba(91,33,182,.18); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:700; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:3px 12px; border-radius:999px; font-size:.72rem; font-weight:700; color:#fff; }
.badge-completed { background:linear-gradient(135deg, #34d399, #059669); }
.badge-researching { background:linear-gradient(135deg, #60a5fa, #3b82f6); }
.badge-failed { background:linear-gradient(135deg, #fb7185, #e11d48); }
.detail { background:rgba(255,255,255,.75); border-radius:18px; padding:18px 22px; margin-top:12px; }
.detail .stats { display:flex; gap:30px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:800;
  background:linear-gradient(135deg, #f472b6, #8b5cf6); -webkit-background-clip:text; background-clip:text; color:transparent; }
.detail .stats .stat .lbl { font-size:.72rem; color:var(--dim); font-weight:600; }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.75; color:#7c6bb8; }
.detail .report h2 { color:#8b5cf6; margin-bottom:8px; }
.detail .report a { color:#8b5cf6; text-decoration:none; font-weight:600; }
.detail .report blockquote { border-left:3px solid #f472b6; margin:8px 0; padding:4px 14px; color:var(--dim); }
.detail .report code { background:rgba(139,92,246,.1); padding:2px 6px; border-radius:6px; font-size:.85em; color:#8b5cf6; }
.detail .report pre { background:#fff; border-radius:12px; padding:12px; overflow-x:auto; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("aurora", "极光", """
/* 10 极光 — 深底流动绿紫极光 */
:root { --bg:#060a14; --card:rgba(10,16,30,.7); --border:rgba(120,240,200,.14); --text:#e6f7f0; --dim:#5f7a72;
  --green:#4dffc3; --purple:#b388ff; --pink:#ff7ad9; --yellow:#ffe66d; --red:#ff6b8a; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, "Segoe UI", "PingFang SC", sans-serif; color:var(--text); min-height:100vh; background:var(--bg); overflow-x:hidden; }
body::before { content:''; position:fixed; inset:-20%; pointer-events:none; z-index:0;
  background:conic-gradient(from 90deg at 60% 40%, rgba(77,255,195,.13), transparent 25%, rgba(179,136,255,.13), transparent 50%, rgba(255,122,217,.1), transparent 75%, rgba(77,255,195,.13));
  filter:blur(60px); animation:aurora 18s linear infinite; }
@keyframes aurora { to { transform:rotate(360deg); } }
.container { max-width:880px; margin:0 auto; padding:40px 20px; position:relative; z-index:1; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; color:var(--green); opacity:.7; z-index:9; }
header { text-align:center; padding:40px 0 30px; }
header h1 { font-size:1.9rem; font-weight:700; letter-spacing:1px;
  background:linear-gradient(90deg, var(--green), var(--purple), var(--pink));
  -webkit-background-clip:text; background-clip:text; color:transparent;
  filter:drop-shadow(0 0 16px rgba(77,255,195,.3)); }
header p { color:var(--dim); margin-top:8px; font-size:.92rem; }
.submit-box { background:var(--card); backdrop-filter:blur(14px); border:1px solid var(--border); border-radius:16px;
  padding:24px; margin-bottom:26px; box-shadow:0 0 40px rgba(77,255,195,.05); }
.submit-box textarea { width:100%; background:rgba(4,8,18,.75); border:1px solid var(--border); border-radius:10px;
  padding:14px 16px; font-size:1rem; resize:vertical; min-height:80px; font-family:inherit; color:var(--text); }
.submit-box textarea:focus { outline:none; border-color:rgba(77,255,195,.5); box-shadow:0 0 14px rgba(77,255,195,.15); }
.submit-box button { margin-top:14px; background:linear-gradient(135deg, rgba(77,255,195,.85), rgba(179,136,255,.85));
  color:#04121a; border:none; border-radius:999px; padding:12px 30px; font-size:1rem; font-weight:800; cursor:pointer; }
.stream-panel { background:var(--card); backdrop-filter:blur(14px); border:1px solid var(--border); border-radius:14px; margin-bottom:22px; overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:10px; padding:14px 18px; font-weight:700; }
.stream-head::before { content:''; width:8px; height:8px; border-radius:50%; background:var(--green); box-shadow:0 0 10px var(--green); animation:pulse 1.8s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.25} }
.stream-phase { flex:1; text-align:right; color:var(--green); font-size:.82rem; text-shadow:0 0 8px rgba(77,255,195,.5); }
.stream-toggle { color:var(--dim); }
.stream-body { padding:12px 18px 14px; border-top:1px solid var(--border); font-family:Consolas, monospace; font-size:.77rem; line-height:1.9; color:rgba(230,247,240,.8); }
.stream-line.strong { color:var(--green); font-weight:700; text-shadow:0 0 8px rgba(77,255,195,.4); }
.stream-line.dim { color:rgba(95,122,114,.7); }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:700; }
.auto-badge { font-size:.75rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:7px; height:7px; border-radius:50%; background:var(--green); box-shadow:0 0 8px var(--green); animation:pulse 2s infinite; }
.run-list { display:flex; flex-direction:column; gap:11px; }
.run-card { background:var(--card); backdrop-filter:blur(14px); border:1px solid var(--border); border-radius:12px; padding:16px 20px; cursor:pointer; }
.run-card:hover { border-color:rgba(77,255,195,.4); box-shadow:0 0 22px rgba(77,255,195,.1); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:3px 11px; border-radius:999px; font-size:.72rem; font-weight:700; border:1px solid; }
.badge-completed { color:var(--green); border-color:rgba(77,255,195,.4); }
.badge-researching { color:var(--purple); border-color:rgba(179,136,255,.4); }
.badge-failed { color:var(--red); border-color:rgba(255,107,138,.4); }
.detail { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px 22px; margin-top:12px; }
.detail .stats { display:flex; gap:30px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:700;
  background:linear-gradient(90deg, var(--green), var(--purple)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.detail .stats .stat .lbl { font-size:.72rem; color:var(--dim); }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.75; color:rgba(230,247,240,.85); }
.detail .report h2 { color:var(--green); margin-bottom:8px; }
.detail .report a { color:var(--green); text-decoration:none; }
.detail .report blockquote { border-left:3px solid var(--purple); margin:8px 0; padding:4px 14px; color:var(--dim); }
.detail .report code { background:rgba(179,136,255,.1); padding:2px 6px; border-radius:4px; font-size:.85em; color:#d3b8ff; }
.detail .report pre { background:rgba(4,8,18,.85); border:1px solid var(--border); padding:12px; border-radius:8px; overflow-x:auto; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("inkwash", "水墨中国风", """
/* 11 水墨中国风 — 米白、墨色晕染、朱红点缀 */
:root { --paper:#faf7f0; --ink:#2c2a26; --ink-soft:#6b675e; --faint:#a8a294; --red:#b23a2e; --border:#e2dccd; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Songti SC", "Noto Serif SC", Georgia, serif; background:var(--paper); color:var(--ink); min-height:100vh; }
body::before { content:''; position:fixed; inset:0; pointer-events:none; z-index:0; opacity:.5;
  background:radial-gradient(700px 500px at 85% 10%, rgba(178,58,46,.05), transparent 60%),
  radial-gradient(600px 450px at 10% 90%, rgba(44,42,38,.05), transparent 60%); }
.container { max-width:820px; margin:0 auto; padding:48px 24px; position:relative; z-index:1; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; letter-spacing:3px; color:var(--faint); z-index:9; }
header { text-align:center; padding:36px 0 30px; }
header h1 { font-size:2rem; font-weight:700; letter-spacing:8px; }
header h1::after { content:'✦'; display:block; font-size:.8rem; color:var(--red); margin-top:8px; }
header p { color:var(--ink-soft); margin-top:10px; font-size:.9rem; letter-spacing:2px; }
.submit-box { border:1px solid var(--border); background:rgba(255,255,255,.4); padding:24px; margin-bottom:28px; position:relative; }
.submit-box::before { content:''; position:absolute; top:0; left:0; width:42px; height:3px; background:var(--red); }
.submit-box textarea { width:100%; background:transparent; border:none; border-bottom:1px solid var(--border);
  padding:12px 4px; font-size:1rem; resize:vertical; min-height:76px; font-family:inherit; color:var(--ink); }
.submit-box textarea:focus { outline:none; border-bottom-color:var(--red); }
.submit-box button { margin-top:16px; background:var(--ink); color:var(--paper); border:none; padding:10px 32px;
  font-size:.95rem; letter-spacing:3px; cursor:pointer; font-family:inherit; }
.submit-box button:hover { background:var(--red); }
.stream-panel { border:1px solid var(--border); background:rgba(255,255,255,.35); margin-bottom:26px; }
.stream-head { display:flex; align-items:center; gap:10px; padding:12px 16px; font-weight:700; letter-spacing:2px; border-bottom:1px solid var(--border); }
.stream-phase { flex:1; text-align:right; color:var(--red); font-size:.8rem; font-weight:400; letter-spacing:1px; }
.stream-toggle { color:var(--faint); }
.stream-body { padding:12px 16px; font-family:Consolas, monospace; font-size:.76rem; line-height:2; color:var(--ink-soft); }
.stream-line.strong { color:var(--ink); font-weight:700; }
.stream-line.dim { color:#c4beaf; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:700; letter-spacing:3px; }
.auto-badge { font-size:.75rem; color:var(--faint); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:6px; height:6px; border-radius:50%; background:var(--red); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:0; }
.run-card { border-bottom:1px solid var(--border); padding:18px 6px; cursor:pointer; }
.run-card:hover .q { color:var(--red); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; transition:color .15s; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:var(--faint); flex-shrink:0; }
.badge { display:inline-block; padding:2px 12px; font-size:.72rem; border:1px solid var(--border); letter-spacing:1px; }
.badge-completed { color:var(--red); border-color:rgba(178,58,46,.4); }
.badge-researching { color:#6b675e; border-color:rgba(107,103,94,.4); }
.badge-failed { color:#9a3b3b; border-color:rgba(154,59,59,.4); }
.detail { border:1px solid var(--border); background:rgba(255,255,255,.4); padding:18px 22px; margin-top:14px; }
.detail .stats { display:flex; gap:32px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:700; font-family:Georgia, serif; }
.detail .stats .stat .lbl { font-size:.72rem; color:var(--faint); letter-spacing:2px; }
.detail .report { margin-top:14px; font-size:.95rem; line-height:1.9; color:var(--ink-soft); }
.detail .report h2 { font-weight:700; margin-bottom:10px; letter-spacing:2px; }
.detail .report a { color:var(--red); }
.detail .report blockquote { border-left:3px solid var(--red); margin:10px 0; padding:4px 16px; color:var(--faint); font-style:italic; }
.detail .report code { background:rgba(44,42,38,.05); padding:2px 6px; font-size:.85em; font-family:Consolas, monospace; }
.detail .report pre { background:rgba(255,255,255,.5); border:1px solid var(--border); padding:12px; overflow-x:auto; font-family:Consolas, monospace; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("wabisabi", "日式和风", """
/* 12 日式和风 — 米色木色、禅意留白 */
:root { --bg:#f3efe6; --card:#faf8f2; --border:#dcd5c3; --text:#3f3a32; --dim:#9c9382;
  --green:#6b7f5e; --red:#b4533d; --wood:#b99a77; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Hiragino Mincho ProN", "Songti SC", "Noto Serif SC", Georgia, serif; background:var(--bg); color:var(--text); min-height:100vh; }
.container { max-width:820px; margin:0 auto; padding:48px 24px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.66rem; letter-spacing:3px; color:var(--dim); z-index:9; }
header { text-align:center; padding:40px 0 32px; }
header h1 { font-size:1.9rem; font-weight:600; letter-spacing:6px; color:#4a443a; }
header p { color:var(--dim); margin-top:10px; font-size:.88rem; letter-spacing:1px; }
.submit-box { background:var(--card); border:1px solid var(--border); border-radius:4px; padding:26px; margin-bottom:28px;
  box-shadow:0 2px 14px rgba(0,0,0,.03); }
.submit-box textarea { width:100%; background:transparent; border:1px solid var(--border); border-radius:3px;
  padding:13px 15px; font-size:.95rem; resize:vertical; min-height:78px; font-family:inherit; color:var(--text); }
.submit-box textarea:focus { outline:none; border-color:var(--green); }
.submit-box button { margin-top:14px; background:var(--green); color:#faf8f2; border:none; border-radius:3px;
  padding:11px 30px; font-size:.92rem; letter-spacing:2px; cursor:pointer; font-family:inherit; }
.stream-panel { background:var(--card); border:1px solid var(--border); border-radius:4px; margin-bottom:24px; overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:10px; padding:13px 18px; font-weight:600; letter-spacing:1px; font-size:.9rem; border-bottom:1px solid var(--border); }
.stream-phase { flex:1; text-align:right; color:var(--green); font-size:.8rem; font-weight:400; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:12px 18px 14px; font-family:Consolas, monospace; font-size:.76rem; line-height:2; color:#7a7262; }
.stream-line.strong { color:var(--text); font-weight:700; }
.stream-line.dim { color:#d3ccbc; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.05rem; font-weight:600; letter-spacing:2px; }
.auto-badge { font-size:.74rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:6px; height:6px; border-radius:50%; background:var(--green); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:10px; }
.run-card { background:var(--card); border:1px solid var(--border); border-radius:4px; padding:16px 20px; cursor:pointer; }
.run-card:hover { border-color:var(--wood); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.78rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:2px 11px; border-radius:999px; font-size:.7rem; border:1px solid var(--border); color:var(--dim); }
.badge-completed { color:var(--green); border-color:rgba(107,127,94,.4); }
.badge-researching { color:var(--red); border-color:rgba(180,83,61,.4); }
.badge-failed { color:#a05545; border-color:rgba(160,85,69,.4); }
.detail { background:var(--card); border:1px solid var(--border); border-radius:4px; padding:18px 22px; margin-top:12px; }
.detail .stats { display:flex; gap:30px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.4rem; font-weight:600; }
.detail .stats .stat .lbl { font-size:.7rem; color:var(--dim); letter-spacing:1px; }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.85; color:#7a7262; }
.detail .report h2 { font-weight:600; margin-bottom:8px; color:var(--text); }
.detail .report a { color:var(--green); }
.detail .report blockquote { border-left:2px solid var(--wood); margin:8px 0; padding:4px 14px; color:var(--dim); font-style:italic; }
.detail .report code { background:rgba(107,127,94,.08); padding:2px 6px; font-size:.85em; font-family:Consolas, monospace; }
.detail .report pre { background:rgba(255,255,255,.6); border:1px solid var(--border); padding:12px; overflow-x:auto; font-family:Consolas, monospace; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("popart", "波普艺术", """
/* 13 波普艺术 — 亮色块、粗黑描边、漫画 */
:root { --yellow:#ffd93d; --pink:#ff6b9d; --cyan:#4ecdc4; --red:#ff4b4b; --ink:#1a1a1a; --paper:#fff8f0; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Arial Black", "Microsoft YaHei", sans-serif; background:var(--paper); color:var(--ink); min-height:100vh;
  background-image:radial-gradient(circle, rgba(26,26,26,.07) 1.5px, transparent 1.5px); background-size:22px 22px; }
.container { max-width:880px; margin:0 auto; padding:40px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:var(--ink); background:var(--yellow);
  border:2px solid var(--ink); padding:2px 8px; z-index:9; box-shadow:3px 3px 0 var(--ink); }
header { text-align:center; padding:36px 0 28px; }
header h1 { font-size:2.2rem; font-weight:900; letter-spacing:1px; text-shadow:4px 4px 0 var(--pink), -3px -3px 0 var(--cyan); }
header p { margin-top:10px; font-size:.92rem; font-weight:700; }
.submit-box { background:var(--yellow); border:4px solid var(--ink); padding:22px; margin-bottom:26px; box-shadow:8px 8px 0 var(--ink); }
.submit-box textarea { width:100%; background:#fff; border:3px solid var(--ink); padding:13px 15px; font-size:.95rem; resize:vertical; min-height:78px; font-family:inherit; color:var(--ink); }
.submit-box textarea:focus { outline:none; box-shadow:inset 4px 4px 0 rgba(0,0,0,.1); }
.submit-box button { margin-top:14px; background:var(--pink); color:#fff; border:3px solid var(--ink);
  padding:10px 30px; font-size:1rem; font-weight:900; cursor:pointer; box-shadow:4px 4px 0 var(--ink); transition:transform .1s; }
.submit-box button:hover { transform:translate(2px, 2px); box-shadow:2px 2px 0 var(--ink); }
.stream-panel { background:#fff; border:4px solid var(--ink); margin-bottom:24px; box-shadow:8px 8px 0 var(--ink); }
.stream-head { display:flex; align-items:center; gap:10px; padding:13px 16px; font-weight:900; background:var(--cyan); border-bottom:3px solid var(--ink); }
.stream-phase { flex:1; text-align:right; font-size:.82rem; }
.stream-toggle { font-weight:900; }
.stream-body { padding:12px 16px 14px; font-family:Consolas, monospace; font-size:.77rem; line-height:1.9; font-weight:700; }
.stream-line.strong { background:var(--yellow); display:inline-block; padding:1px 8px; }
.stream-line.dim { opacity:.45; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.2rem; font-weight:900; letter-spacing:1px; text-shadow:3px 3px 0 var(--cyan); }
.auto-badge { font-size:.75rem; font-weight:800; display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:9px; height:9px; border-radius:50%; background:var(--red); border:2px solid var(--ink); animation:pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:16px; }
.run-card { background:#fff; border:4px solid var(--ink); padding:16px 20px; cursor:pointer; box-shadow:6px 6px 0 var(--ink); transition:transform .1s; }
.run-card:hover { transform:translate(2px, 2px); box-shadow:3px 3px 0 var(--ink); }
.run-card:nth-child(1) { background:var(--cyan); } .run-card:nth-child(2) { background:var(--yellow); } .run-card:nth-child(3) { background:var(--pink); color:#fff; }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:900; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.78rem; font-weight:800; flex-shrink:0; }
.badge { display:inline-block; padding:2px 10px; font-size:.7rem; font-weight:900; background:#fff; border:2px solid var(--ink); }
.badge-completed { color:#0a7d4c; } .badge-researching { color:#0b5fa5; } .badge-failed { color:var(--red); }
.detail { background:#fff; border:4px solid var(--ink); padding:18px 20px; margin-top:12px; box-shadow:4px 4px 0 var(--ink); }
.detail .stats { display:flex; gap:30px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.6rem; font-weight:900; }
.detail .stats .stat .lbl { font-size:.7rem; font-weight:800; opacity:.6; }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.8; font-weight:600; }
.detail .report h2 { font-size:1.1rem; font-weight:900; margin-bottom:8px; background:var(--yellow); display:inline-block; padding:1px 8px; }
.detail .report a { color:#0b5fa5; font-weight:900; }
.detail .report blockquote { border-left:6px solid var(--pink); margin:8px 0; padding:4px 14px; }
.detail .report code { background:var(--yellow); padding:2px 6px; font-size:.85em; font-family:Consolas, monospace; font-weight:700; }
.detail .report pre { background:#f2f2f2; border:3px solid var(--ink); padding:12px; overflow-x:auto; font-family:Consolas, monospace; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("editorial", "编辑杂志", """
/* 14 编辑杂志 — 大衬线标题、编辑排版 */
:root { --bg:#fcfbf9; --ink:#111; --dim:#6b6b6b; --accent:#c8102e; --border:#ddd; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:Georgia, "Times New Roman", "Songti SC", serif; background:var(--bg); color:var(--ink); min-height:100vh; }
.container { max-width:900px; margin:0 auto; padding:40px 24px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.66rem; letter-spacing:3px; color:var(--dim); text-transform:uppercase; z-index:9; }
header { text-align:center; padding:40px 0 20px; border-bottom:3px double var(--ink); margin-bottom:28px; }
header h1 { font-size:2.6rem; font-weight:700; letter-spacing:1px; }
header p { color:var(--dim); margin-top:12px; font-size:.9rem; font-style:italic; }
.submit-box { padding:24px 0; border-bottom:1px solid var(--border); margin-bottom:30px; }
.submit-box textarea { width:100%; border:1px solid var(--border); border-radius:2px; padding:14px 16px; font-size:.98rem;
  resize:vertical; min-height:80px; font-family:Georgia, serif; color:var(--ink); background:#fff; }
.submit-box textarea:focus { outline:none; border-color:var(--accent); }
.submit-box button { margin-top:14px; background:var(--ink); color:#fff; border:none; border-radius:2px;
  padding:11px 30px; font-size:.9rem; font-weight:700; letter-spacing:2px; cursor:pointer; font-family:Georgia, serif; text-transform:uppercase; }
.stream-panel { border:1px solid var(--border); background:#fff; margin-bottom:28px; }
.stream-head { display:flex; align-items:center; gap:10px; padding:14px 18px; font-weight:700; border-bottom:1px solid var(--border); font-size:.9rem; }
.stream-phase { flex:1; text-align:right; color:var(--accent); font-size:.8rem; font-weight:400; font-style:italic; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:13px 18px; font-family:Consolas, monospace; font-size:.76rem; line-height:1.95; color:#444; }
.stream-line.strong { color:var(--ink); font-weight:700; font-family:Georgia, serif; }
.stream-line.dim { color:#bbb; font-style:italic; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; border-bottom:1px solid var(--border); padding-bottom:10px; }
.status-bar h2 { font-size:1.15rem; font-weight:700; letter-spacing:1px; text-transform:uppercase; }
.auto-badge { font-size:.72rem; color:var(--dim); display:flex; align-items:center; gap:6px; font-style:italic; }
.auto-badge .dot { width:6px; height:6px; border-radius:50%; background:var(--accent); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:0; }
.run-card { padding:20px 4px; cursor:pointer; border-bottom:1px solid var(--border); }
.run-card:first-child { border-top:1px solid var(--border); }
.run-card:hover .q { color:var(--accent); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-size:1.05rem; font-weight:700; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.78rem; color:var(--dim); flex-shrink:0; font-style:italic; }
.badge { display:inline-block; padding:2px 10px; font-size:.68rem; font-weight:700; border:1px solid var(--border); letter-spacing:1px; }
.badge-completed { color:var(--accent); border-color:rgba(200,16,46,.4); }
.badge-researching { color:#1a5fb4; border-color:rgba(26,95,180,.4); }
.badge-failed { color:#8a1c1c; border-color:rgba(138,28,28,.4); }
.detail { padding:20px 4px 8px; }
.detail .stats { display:flex; gap:36px; margin:14px 0; border-top:1px solid var(--border); border-bottom:1px solid var(--border); padding:14px 0; }
.detail .stats .stat .val { font-size:1.6rem; font-weight:700; font-family:Georgia, serif; }
.detail .stats .stat .lbl { font-size:.7rem; color:var(--dim); letter-spacing:2px; text-transform:uppercase; }
.detail .report { margin-top:16px; font-size:.95rem; line-height:1.85; color:#2a2a2a; }
.detail .report h2 { font-size:1.25rem; font-weight:700; margin-bottom:10px; }
.detail .report a { color:var(--accent); }
.detail .report blockquote { border-left:4px solid var(--accent); margin:10px 0; padding:6px 18px; color:var(--dim); font-style:italic; font-size:.92rem; }
.detail .report code { background:#f4f4f4; padding:2px 6px; font-size:.85em; font-family:Consolas, monospace; }
.detail .report pre { background:#f8f8f8; border:1px solid var(--border); padding:14px; overflow-x:auto; font-family:Consolas, monospace; font-size:.85rem; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("corporate", "企业蓝", """
/* 15 企业蓝 — 蓝白稳重、方正、专业 */
:root { --bg:#f4f7fb; --card:#fff; --border:#dbe4f0; --text:#1f2d3d; --dim:#7a8ba3;
  --blue:#2563eb; --green:#059669; --red:#dc2626; --dark:#0f1e33; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
.container { max-width:900px; margin:0 auto; padding:40px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; letter-spacing:2px; color:var(--dim); z-index:9; }
header { text-align:center; padding:36px 0 28px; }
header h1 { font-size:1.8rem; font-weight:700; color:var(--dark); }
header p { color:var(--dim); margin-top:8px; font-size:.92rem; }
.submit-box { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:24px; margin-bottom:26px; box-shadow:0 2px 10px rgba(15,30,51,.04); }
.submit-box textarea { width:100%; background:#f8fafc; border:1px solid var(--border); border-radius:6px;
  padding:14px 16px; font-size:1rem; resize:vertical; min-height:80px; font-family:inherit; color:var(--text); }
.submit-box textarea:focus { outline:none; border-color:var(--blue); box-shadow:0 0 0 3px rgba(37,99,235,.1); }
.submit-box button { margin-top:14px; background:var(--blue); color:#fff; border:none; border-radius:6px;
  padding:12px 32px; font-size:1rem; font-weight:600; cursor:pointer; }
.stream-panel { background:var(--card); border:1px solid var(--border); border-radius:8px; margin-bottom:24px; overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:10px; padding:13px 16px; font-weight:600; font-size:.9rem; border-bottom:1px solid var(--border); background:#f8fafc; }
.stream-phase { flex:1; text-align:right; color:var(--blue); font-size:.82rem; font-weight:500; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:11px 16px 13px; font-family:Consolas, monospace; font-size:.77rem; line-height:1.9; color:#526079; }
.stream-line.strong { color:var(--dark); font-weight:700; }
.stream-line.dim { color:#b6c2d4; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:700; color:var(--dark); }
.auto-badge { font-size:.75rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:6px; height:6px; border-radius:50%; background:var(--green); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:10px; }
.run-card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px 20px; cursor:pointer; }
.run-card:hover { border-color:var(--blue); box-shadow:0 4px 16px rgba(37,99,235,.08); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:3px 11px; border-radius:6px; font-size:.72rem; font-weight:600; }
.badge-completed { background:#ecfdf5; color:var(--green); }
.badge-researching { background:#eff6ff; color:var(--blue); }
.badge-failed { background:#fef2f2; color:var(--red); }
.detail { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:18px 22px; margin-top:12px; }
.detail .stats { display:flex; gap:30px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:700; color:var(--dark); }
.detail .stats .stat .lbl { font-size:.72rem; color:var(--dim); }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.75; color:#526079; }
.detail .report h2 { color:var(--dark); margin-bottom:8px; font-size:1.05rem; }
.detail .report a { color:var(--blue); text-decoration:none; }
.detail .report blockquote { border-left:3px solid var(--blue); margin:8px 0; padding:4px 14px; color:var(--dim); }
.detail .report code { background:#f1f5f9; padding:2px 6px; border-radius:4px; font-size:.85em; }
.detail .report pre { background:#f8fafc; border:1px solid var(--border); padding:12px; border-radius:6px; overflow-x:auto; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("blackmin", "纯黑现代", """
/* 16 纯黑现代 — 纯黑白字、零彩色、极简 */
:root { --bg:#000; --card:#0a0a0a; --border:#1f1f1f; --text:#fff; --dim:#555; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, "Segoe UI", "PingFang SC", sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
.container { max-width:860px; margin:0 auto; padding:44px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; letter-spacing:3px; color:var(--dim); z-index:9; }
header { text-align:center; padding:48px 0 32px; }
header h1 { font-size:2rem; font-weight:200; letter-spacing:4px; color:#fff; }
header p { color:var(--dim); margin-top:10px; font-size:.88rem; letter-spacing:1px; }
.submit-box { padding:24px 0; margin-bottom:28px; }
.submit-box textarea { width:100%; background:transparent; border:none; border-bottom:1px solid var(--border);
  padding:12px 2px; font-size:1.05rem; resize:vertical; min-height:80px; font-family:inherit; color:#fff; }
.submit-box textarea:focus { outline:none; border-bottom-color:#fff; }
.submit-box button { margin-top:16px; background:#fff; color:#000; border:none; padding:12px 36px;
  font-size:.95rem; font-weight:600; letter-spacing:2px; cursor:pointer; }
.submit-box button:hover { background:#ddd; }
.stream-panel { border:1px solid var(--border); margin-bottom:24px; }
.stream-head { display:flex; align-items:center; gap:10px; padding:14px 18px; font-weight:600; border-bottom:1px solid var(--border); letter-spacing:1px; }
.stream-phase { flex:1; text-align:right; color:var(--dim); font-size:.8rem; font-weight:400; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:13px 18px; font-family:Consolas, monospace; font-size:.77rem; line-height:1.9; color:#aaa; }
.stream-line.strong { color:#fff; font-weight:700; }
.stream-line.dim { color:#333; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:300; letter-spacing:2px; }
.auto-badge { font-size:.74rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:6px; height:6px; border-radius:50%; background:#fff; animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.2} }
.run-list { display:flex; flex-direction:column; gap:0; }
.run-card { border-bottom:1px solid var(--border); padding:18px 2px; cursor:pointer; }
.run-card:hover .q { color:#aaa; }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:400; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:2px 10px; font-size:.7rem; border:1px solid var(--border); letter-spacing:1px; }
.badge-completed { color:#fff; border-color:#fff; }
.badge-researching { color:var(--dim); }
.badge-failed { color:var(--dim); border-color:#333; }
.detail { padding:20px 2px 8px; }
.detail .stats { display:flex; gap:32px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:200; }
.detail .stats .stat .lbl { font-size:.7rem; color:var(--dim); letter-spacing:2px; }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.8; color:#bbb; }
.detail .report h2 { color:#fff; font-weight:400; margin-bottom:8px; letter-spacing:1px; }
.detail .report a { color:#fff; }
.detail .report blockquote { border-left:2px solid var(--border); margin:8px 0; padding:4px 14px; color:var(--dim); }
.detail .report code { background:#111; padding:2px 6px; font-size:.85em; font-family:Consolas, monospace; }
.detail .report pre { background:#0a0a0a; border:1px solid var(--border); padding:12px; overflow-x:auto; font-family:Consolas, monospace; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("ocean", "海洋珊瑚", """
/* 17 海洋珊瑚 — 青蓝→珊瑚渐变、圆润柔和 */
:root { --text:#0f3d4e; --dim:#6a9aa8; --white:rgba(255,255,255,.82); }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, "Segoe UI", "PingFang SC", sans-serif; color:var(--text); min-height:100vh;
  background:linear-gradient(160deg, #a8e6ff 0%, #7cd4f5 35%, #ffb3a7 75%, #ff9a8b 100%); }
body::before { content:''; position:fixed; inset:0; pointer-events:none; z-index:0;
  background:radial-gradient(500px 350px at 20% 25%, rgba(255,255,255,.3), transparent 60%),
  radial-gradient(450px 320px at 80% 70%, rgba(255,255,255,.25), transparent 60%); }
.container { max-width:860px; margin:0 auto; padding:40px 20px; position:relative; z-index:1; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; letter-spacing:2px; color:rgba(15,61,78,.6); z-index:9; }
header { text-align:center; padding:36px 0 30px; }
header h1 { font-size:2rem; font-weight:800; color:#fff; text-shadow:0 2px 14px rgba(15,61,78,.25); }
header p { color:rgba(15,61,78,.75); margin-top:8px; font-size:.92rem; font-weight:500; }
.submit-box { background:var(--white); backdrop-filter:blur(12px); border-radius:22px; padding:24px; margin-bottom:24px; box-shadow:0 10px 40px rgba(15,61,78,.12); }
.submit-box textarea { width:100%; background:rgba(255,255,255,.85); border:2px solid transparent; border-radius:14px;
  padding:14px 16px; font-size:1rem; resize:vertical; min-height:80px; font-family:inherit; color:var(--text); }
.submit-box textarea:focus { outline:none; border-color:#ffb3a7; }
.submit-box button { margin-top:14px; background:linear-gradient(135deg, #4ecdc4, #ff9a8b); color:#fff; border:none;
  border-radius:999px; padding:12px 32px; font-size:1rem; font-weight:700; cursor:pointer; box-shadow:0 6px 20px rgba(255,154,139,.4); }
.stream-panel { background:var(--white); backdrop-filter:blur(12px); border-radius:18px; margin-bottom:22px; overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:10px; padding:14px 18px; font-weight:700; font-size:.92rem; }
.stream-phase { flex:1; text-align:right; color:#0e8fa5; font-size:.82rem; font-weight:600; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:12px 18px 14px; border-top:1px solid rgba(15,61,78,.1); font-family:Consolas, monospace; font-size:.77rem; line-height:1.9; color:#3d7a8a; }
.stream-line.strong { color:#0e8fa5; font-weight:700; }
.stream-line.dim { color:rgba(106,154,168,.6); }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:800; color:#fff; text-shadow:0 2px 10px rgba(15,61,78,.3); }
.auto-badge { font-size:.75rem; color:rgba(15,61,78,.8); font-weight:600; display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:8px; height:8px; border-radius:50%; background:#ff9a8b; animation:pulse 1.8s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:12px; }
.run-card { background:var(--white); backdrop-filter:blur(12px); border-radius:16px; padding:18px 22px; cursor:pointer; }
.run-card:hover { box-shadow:0 12px 34px rgba(15,61,78,.18); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:700; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.8rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:3px 12px; border-radius:999px; font-size:.72rem; font-weight:700; }
.badge-completed { background:rgba(78,205,196,.15); color:#0e8fa5; }
.badge-researching { background:rgba(255,179,167,.25); color:#e0654f; }
.badge-failed { background:rgba(255,107,107,.15); color:#e05252; }
.detail { background:var(--white); border-radius:16px; padding:18px 22px; margin-top:12px; }
.detail .stats { display:flex; gap:30px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:800;
  background:linear-gradient(135deg, #4ecdc4, #ff9a8b); -webkit-background-clip:text; background-clip:text; color:transparent; }
.detail .stats .stat .lbl { font-size:.72rem; color:var(--dim); font-weight:600; }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.75; color:#3d7a8a; }
.detail .report h2 { color:#0e8fa5; margin-bottom:8px; }
.detail .report a { color:#e0654f; text-decoration:none; font-weight:600; }
.detail .report blockquote { border-left:3px solid #ffb3a7; margin:8px 0; padding:4px 14px; color:var(--dim); }
.detail .report code { background:rgba(78,205,196,.12); padding:2px 6px; border-radius:6px; font-size:.85em; color:#0e8fa5; }
.detail .report pre { background:rgba(255,255,255,.8); border-radius:10px; padding:12px; overflow-x:auto; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("nordic", "北欧简约", """
/* 18 北欧简约 — 浅灰蓝、木色、极简线条 */
:root { --bg:#f2f4f5; --card:#fff; --border:#e0e4e5; --text:#2d3436; --dim:#9aa5a8;
  --blue:#5b8a9c; --wood:#c8a27e; --green:#7d9b76; --red:#c07a6a; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, "Segoe UI", "PingFang SC", sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
.container { max-width:860px; margin:0 auto; padding:44px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; letter-spacing:3px; color:var(--dim); z-index:9; }
header { text-align:center; padding:40px 0 28px; }
header h1 { font-size:1.9rem; font-weight:300; letter-spacing:3px; }
header p { color:var(--dim); margin-top:8px; font-size:.9rem; }
.submit-box { background:var(--card); border-radius:4px; padding:26px; margin-bottom:28px; box-shadow:0 2px 8px rgba(0,0,0,.04); }
.submit-box textarea { width:100%; background:var(--bg); border:none; border-radius:3px; padding:14px 16px;
  font-size:1rem; resize:vertical; min-height:80px; font-family:inherit; color:var(--text); }
.submit-box textarea:focus { outline:none; box-shadow:0 0 0 2px rgba(91,138,156,.25); }
.submit-box button { margin-top:14px; background:var(--blue); color:#fff; border:none; border-radius:3px;
  padding:12px 32px; font-size:.95rem; font-weight:500; letter-spacing:1px; cursor:pointer; }
.stream-panel { background:var(--card); border-radius:4px; margin-bottom:24px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.04); }
.stream-head { display:flex; align-items:center; gap:10px; padding:13px 18px; font-weight:600; font-size:.9rem; border-bottom:1px solid var(--border); }
.stream-phase { flex:1; text-align:right; color:var(--blue); font-size:.8rem; font-weight:400; }
.stream-toggle { color:var(--dim); }
.stream-body { padding:12px 18px 14px; font-family:Consolas, monospace; font-size:.76rem; line-height:1.9; color:#6b7578; }
.stream-line.strong { color:var(--text); font-weight:700; }
.stream-line.dim { color:#cdd4d6; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.05rem; font-weight:600; letter-spacing:1px; }
.auto-badge { font-size:.74rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:6px; height:6px; border-radius:50%; background:var(--green); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.run-list { display:flex; flex-direction:column; gap:10px; }
.run-card { background:var(--card); border-radius:4px; padding:17px 20px; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,.04); }
.run-card:hover { box-shadow:0 4px 14px rgba(0,0,0,.08); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:500; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.78rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:2px 11px; border-radius:999px; font-size:.7rem; border:1px solid var(--border); color:var(--dim); }
.badge-completed { color:var(--green); border-color:rgba(125,155,118,.4); }
.badge-researching { color:var(--blue); border-color:rgba(91,138,156,.4); }
.badge-failed { color:var(--red); border-color:rgba(192,122,106,.4); }
.detail { background:var(--card); border-radius:4px; padding:18px 22px; margin-top:12px; }
.detail .stats { display:flex; gap:32px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.4rem; font-weight:300; }
.detail .stats .stat .lbl { font-size:.7rem; color:var(--dim); letter-spacing:1px; }
.detail .report { margin-top:14px; font-size:.92rem; line-height:1.8; color:#6b7578; }
.detail .report h2 { color:var(--text); font-weight:600; margin-bottom:8px; }
.detail .report a { color:var(--blue); }
.detail .report blockquote { border-left:2px solid var(--wood); margin:8px 0; padding:4px 14px; color:var(--dim); font-style:italic; }
.detail .report code { background:var(--bg); padding:2px 6px; font-size:.85em; font-family:Consolas, monospace; }
.detail .report pre { background:var(--bg); padding:12px; overflow-x:auto; font-family:Consolas, monospace; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("pixel", "像素游戏", """
/* 19 像素游戏 8-bit — 像素风、亮色块、硬边阴影 */
:root { --bg:#101040; --card:#1a1a5a; --border:#000; --text:#fff; --dim:#8a8ac0;
  --yellow:#ffd93d; --green:#4ade80; --cyan:#4ecdc4; --red:#ff4b4b; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Courier New", Consolas, monospace; background:var(--bg); color:var(--text); min-height:100vh;
  background-image:linear-gradient(rgba(255,255,255,.03) 1px, transparent 1px),
  linear-gradient(90deg, rgba(255,255,255,.03) 1px, transparent 1px); background-size:16px 16px; }
.container { max-width:880px; margin:0 auto; padding:40px 20px; }
.style-tag { position:fixed; top:14px; right:20px; font-size:.68rem; font-weight:900; color:var(--yellow);
  background:var(--card); border:3px solid var(--border); padding:3px 8px; z-index:9; box-shadow:4px 4px 0 #000; }
header { text-align:center; padding:36px 0 26px; }
header h1 { font-size:2rem; font-weight:900; letter-spacing:2px; color:var(--yellow); text-shadow:3px 3px 0 #000; }
header p { color:var(--dim); margin-top:8px; font-size:.85rem; }
.pixel { border:3px solid #000; box-shadow:5px 5px 0 #000; image-rendering:pixelated; }
.submit-box { background:var(--card); padding:22px; margin-bottom:26px; }
.submit-box textarea { width:100%; background:#000; border:3px solid #000; outline:2px solid #333;
  padding:13px 15px; font-size:.95rem; resize:vertical; min-height:78px; font-family:"Courier New", monospace; color:var(--text); }
.submit-box textarea:focus { outline-color:var(--yellow); }
.submit-box button { margin-top:14px; background:var(--green); color:#000; border:3px solid #000; box-shadow:4px 4px 0 #000;
  padding:10px 28px; font-size:.95rem; font-weight:900; cursor:pointer; font-family:"Courier New", monospace; transition:transform .08s; }
.submit-box button:hover { transform:translate(2px, 2px); box-shadow:2px 2px 0 #000; }
.stream-panel { background:var(--card); margin-bottom:22px; overflow:hidden; }
.stream-head { display:flex; align-items:center; gap:10px; padding:12px 16px; font-weight:900; background:#2a2a7a; border-bottom:3px solid #000; }
.stream-phase { flex:1; text-align:right; color:var(--cyan); font-size:.8rem; }
.stream-toggle { font-weight:900; }
.stream-body { padding:11px 16px 13px; font-size:.76rem; line-height:1.9; color:#b0b0e0; }
.stream-line.strong { color:var(--yellow); font-weight:900; }
.stream-line.dim { color:#4a4a90; }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.1rem; font-weight:900; color:var(--cyan); text-shadow:2px 2px 0 #000; }
.auto-badge { font-size:.74rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:8px; height:8px; background:var(--yellow); animation:pulse 1s steps(2) infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0} }
.run-list { display:flex; flex-direction:column; gap:14px; }
.run-card { background:var(--card); padding:15px 18px; cursor:pointer; }
.run-card:hover { transform:translate(2px, 2px); box-shadow:3px 3px 0 #000; }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:900; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.76rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:2px 9px; font-size:.68rem; font-weight:900; border:2px solid #000; }
.badge-completed { background:var(--green); color:#000; }
.badge-researching { background:var(--cyan); color:#000; }
.badge-failed { background:var(--red); color:#fff; }
.detail { background:var(--card); padding:17px 19px; margin-top:12px; }
.detail .stats { display:flex; gap:28px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.5rem; font-weight:900; color:var(--yellow); text-shadow:2px 2px 0 #000; }
.detail .stats .stat .lbl { font-size:.7rem; color:var(--dim); }
.detail .report { margin-top:12px; font-size:.88rem; line-height:1.8; color:#b0b0e0; }
.detail .report h2 { color:var(--cyan); font-size:1rem; margin-bottom:8px; }
.detail .report a { color:var(--yellow); }
.detail .report blockquote { border-left:4px solid var(--yellow); margin:8px 0; padding:4px 12px; color:var(--dim); }
.detail .report code { background:#000; border:2px solid #333; padding:1px 6px; color:var(--green); font-size:.85em; }
.detail .report pre { background:#000; border:2px solid #333; padding:12px; overflow-x:auto; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

THEMES.append(("hud", "科幻HUD", """
/* 20 科幻 HUD — 全息青绿、角标、科技网格 */
:root { --bg:#010a08; --card:rgba(8,32,26,.7); --border:rgba(46,255,196,.2); --text:#b8ffe8;
  --green:#2effc4; --cyan:#4dffec; --yellow:#c8ff4d; --red:#ff5f6d; --dim:#3d7a68; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Cascadia Code", "Share Tech Mono", Consolas, monospace; background:var(--bg); color:var(--text); min-height:100vh;
  background-image:linear-gradient(rgba(46,255,196,.04) 1px, transparent 1px),
  linear-gradient(90deg, rgba(46,255,196,.04) 1px, transparent 1px); background-size:34px 34px; }
body::before { content:''; position:fixed; inset:0; pointer-events:none; z-index:0;
  background:radial-gradient(700px 500px at 70% 20%, rgba(46,255,196,.06), transparent 60%),
  radial-gradient(600px 420px at 15% 80%, rgba(77,255,236,.05), transparent 60%); }
.container { max-width:900px; margin:0 auto; padding:40px 20px; position:relative; z-index:1; }
.style-tag { position:fixed; top:12px; right:16px; font-size:.66rem; letter-spacing:3px; color:var(--green);
  border:1px solid rgba(46,255,196,.35); padding:3px 10px; z-index:9; background:rgba(1,10,8,.8); clip-path:polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%); }
header { text-align:center; padding:44px 0 30px; position:relative; }
header::after { content:''; display:block; width:60%; height:1px; margin:0 auto; margin-top:24px;
  background:linear-gradient(90deg, transparent, var(--green), transparent); }
header h1 { font-size:1.8rem; font-weight:700; letter-spacing:4px; color:var(--green); text-shadow:0 0 14px rgba(46,255,196,.5); }
header p { color:var(--dim); margin-top:8px; font-size:.8rem; letter-spacing:2px; }
.submit-box { background:var(--card); border:1px solid var(--border); padding:22px; margin-bottom:26px; position:relative; }
.submit-box::before, .submit-box::after { content:''; position:absolute; width:14px; height:14px; border:2px solid var(--green); }
.submit-box::before { top:-2px; left:-2px; border-right:none; border-bottom:none; }
.submit-box::after { bottom:-2px; right:-2px; border-left:none; border-top:none; }
.submit-box textarea { width:100%; background:rgba(1,10,8,.85); border:1px solid rgba(46,255,196,.2);
  padding:13px 15px; font-size:.92rem; resize:vertical; min-height:80px; font-family:inherit; color:var(--text); caret-color:var(--green); }
.submit-box textarea:focus { outline:none; border-color:rgba(46,255,196,.5); box-shadow:0 0 14px rgba(46,255,196,.12); }
.submit-box button { margin-top:14px; background:transparent; color:var(--green); border:1px solid var(--green);
  padding:11px 30px; font-size:.9rem; font-weight:700; letter-spacing:2px; cursor:pointer; font-family:inherit; }
.submit-box button:hover { background:rgba(46,255,196,.1); box-shadow:0 0 16px rgba(46,255,196,.25); }
.stream-panel { background:var(--card); border:1px solid var(--border); margin-bottom:22px; position:relative; }
.stream-head { display:flex; align-items:center; gap:10px; padding:13px 18px; font-weight:700; letter-spacing:1px; border-bottom:1px solid var(--border); color:var(--cyan); }
.stream-head::before { content:'▸'; color:var(--green); animation:pulse 1.2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.2} }
.stream-phase { flex:1; text-align:right; color:var(--green); font-size:.8rem; text-shadow:0 0 8px rgba(46,255,196,.5); }
.stream-toggle { color:var(--dim); }
.stream-body { padding:12px 18px 14px; font-size:.76rem; line-height:1.9; color:rgba(184,255,232,.8); }
.stream-line.strong { color:var(--green); font-weight:700; text-shadow:0 0 8px rgba(46,255,196,.4); }
.stream-line.dim { color:rgba(61,122,104,.8); }
.status-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.status-bar h2 { font-size:1.05rem; font-weight:700; color:var(--cyan); letter-spacing:2px; }
.auto-badge { font-size:.72rem; color:var(--dim); display:flex; align-items:center; gap:6px; }
.auto-badge .dot { width:7px; height:7px; background:var(--green); box-shadow:0 0 8px var(--green); animation:pulse 1.6s infinite; }
.run-list { display:flex; flex-direction:column; gap:10px; }
.run-card { background:var(--card); border:1px solid var(--border); padding:15px 19px; cursor:pointer; position:relative; }
.run-card:hover { border-color:rgba(46,255,196,.5); box-shadow:0 0 18px rgba(46,255,196,.08); }
.run-card .top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.run-card .q { font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.run-card .meta { display:flex; align-items:center; gap:12px; font-size:.76rem; color:var(--dim); flex-shrink:0; }
.badge { display:inline-block; padding:2px 10px; font-size:.68rem; font-weight:700; border:1px solid; letter-spacing:1px; }
.badge-completed { color:var(--green); border-color:rgba(46,255,196,.45); background:rgba(46,255,196,.06); }
.badge-researching { color:var(--cyan); border-color:rgba(77,255,236,.45); background:rgba(77,255,236,.06); }
.badge-failed { color:var(--red); border-color:rgba(255,95,109,.45); background:rgba(255,95,109,.06); }
.detail { background:var(--card); border:1px solid var(--border); padding:17px 20px; margin-top:12px; }
.detail .stats { display:flex; gap:28px; margin:12px 0; }
.detail .stats .stat .val { font-size:1.4rem; font-weight:700; color:var(--green); text-shadow:0 0 10px rgba(46,255,196,.4); }
.detail .stats .stat .lbl { font-size:.68rem; color:var(--dim); letter-spacing:2px; }
.detail .report { margin-top:12px; font-size:.88rem; line-height:1.8; color:rgba(184,255,232,.85); }
.detail .report h2 { color:var(--cyan); font-size:1rem; margin-bottom:8px; }
.detail .report a { color:var(--green); }
.detail .report blockquote { border-left:2px solid var(--green); margin:8px 0; padding:4px 12px; color:var(--dim); }
.detail .report code { background:rgba(46,255,196,.08); border:1px solid rgba(46,255,196,.2); padding:1px 6px; color:var(--yellow); font-size:.85em; }
.detail .report pre { background:rgba(1,10,8,.9); border:1px solid var(--border); padding:12px; overflow-x:auto; }
@media (max-width:600px) { .run-card .top { flex-direction:column; align-items:flex-start; gap:6px; } }
"""))

print("ALL THEMES:", len(THEMES))

# ── generate ─────────────────────────────────────────────────────────
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for i, (slug, name, css) in enumerate(THEMES, 1):
        html = SKELETON.format(nn=i, name=name, css=css.strip())
        path = OUT / f"theme-{i:02d}-{slug}.html"
        path.write_text(html, encoding="utf-8")
        print(f"  wrote {path.name} ({len(css.splitlines())} css lines)")

if __name__ == "__main__":
    main()
