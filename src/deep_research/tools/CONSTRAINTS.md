# tools/ 约束 — 搜索与抓取

> 这是本项目故障率最高的层。改任何搜索/抓取逻辑前，先读完本文件，再改代码。

## 注册顺序（当前代码，`tools/__init__.py`）

默认 `get_search_tools()` / `get_free_search_tools()`（完全不消耗 Firecrawl）：

```
BaiduSearchTool（免费 CN 引擎，首选）
→ BingSearchTool（免费 CN 引擎）
```

质量门重搜 `get_quality_search_tools()` 才追加：

```
→ WikipediaSearchTool（Firecrawl keyless 桥接，消耗额度）
→ WikidataLookupTool（Firecrawl keyless 桥接，消耗额度）
→ FirecrawlSearchTool（keyless 或 FIRECRAWL_API_KEY）
→ TavilySearchTool（有 TAVILY_API_KEY 才追加）
```

DuckDuckGo（`name="web_search"`）已移除：底层 `www.bing.com` 在 CN 结构性不可达。
注意：列表顺序影响 schema 呈现，但**模型按 description 选择工具**；description 已按中文/英文场景分工。

## 各后端的事实（2026-08 实测 + logs）

| 工具 | 状态 | 关键事实 |
|---|---|---|
| `bing_search` | ✅ 可用 | 245–323ms，返回 4–5 条；英文技术文档/GitHub/论文首选；解析时会把 `bing.com/ck` 跳转解码回真实 URL |
| `baidu_search` | ✅ 可用 | 620–744ms，返回 4–5 条；中文新内容最强；结果是 `baidu.com/link?url=...` 跳转包装，偶发反爬错误 |
| `firecrawl_search` | ⚠️ 配额/限流 | 默认不注册；仅质量门重搜启用；支持 keyless；429 命中后与 web_fetch 共享 60s 进程级 cooldown；`Insufficient credits` 会进程级禁用 |
| `tavily_search` | ⚠️ 配额 | 有 key 才注册；首次 `exceeds your plan` 后进程级禁用，之后所有实例不再重试 |
| `wikipedia_search` | ✅ 可用（Firecrawl keyless 桥接） | 搜索/摘要走 Firecrawl keyless；绕开被墙的 wikipedia.org 直连 |
| `wikidata_lookup` | ✅ 可用（Firecrawl keyless 桥接） | 搜索 QID + EntityData JSON 走 Firecrawl keyless；绕开被墙的 wikidata.org 直连 |
| `web_search`(DDG) | 🚫 已移除 | 不再注册；非 CN 部署需从 git 历史恢复并迁移到 `ddgs` 包 |

## 搜索工具的统一返回格式

成功：`[{"title": str, "url": str, "body"/"content": str}, ...]`
失败：`[{"error": "..."}]`（不是抛异常）。
LLM 看到的格式化文本由各工具 `format_result()` 产生。

## 共享禁用与冷却（`core/tool.py` + 本包）

- 不可恢复错误（配额/计费/auth/credit/payment/expired）→ `disable_tool_key(key)`，进程级永久。
- 429 rate limit → `set_backend_cooldown(key, 60s)`，进程级短冷却，到期自动恢复。
- **搜索与抓取共享同一个 backend key**：
  `FirecrawlSearchTool.execute()` 先查 `in_backend_cooldown("firecrawl")`；
  `WebFetchTool` 的 Firecrawl/Tavily 后端同样查 `is_tool_key_disabled` / `in_backend_cooldown`。
  这样并行 agent 会一起退避，而不是各自撞限流。

## WebFetch 的级联与熔断（`web_fetch.py`）

- 顺序：Firecrawl scrape → Tavily extract → httpx 裸抓取；每层独立 try/except，失败降级。
- 实例级 breaker 仍保留，用于空结果计数/半开探测等**服务退化**判断；
  进程级禁用/冷却只处理不可恢复和 429，两层语义不要混。
- 页面 403/404 登录墙不算服务降级，不要“修”成熔断服务。
- httpx 兜底偶发 `CERTIFICATE_VERIFY_FAILED`，属目标站证书问题，单调用降级即可。

## 来源可信度分类（`web_fetch.py::_classify_url`）

- 用有序 pattern 列表，**首个匹配生效**；GitHub 必须排在 `.com` catch-all 前面。
- 输出 `[来源: 标签 ★★★★]` 前缀，`synthesis_crew.py::SCORER_TASK` 据此给来源可靠性打分：
  ★★★★=5、★★★=4、★★=2、★=1；无 ★★★★ 来源的声明最多 3 分。
- 当前已知缺陷：Baidu 跳转链接会按 `baidu.com` 分到“商业网站 ★★”，而不是最终落地页；
  这会让 Baidu 来源在 Scorer 中被低估，做搜索质量改进时优先修。

## 结构化调用日志（`core/call_log.py`）

每次工具调用都会追加一行到 `logs/search_calls.jsonl`：

```json
{"run_id": "...", "trace_id": "...", "agent": "researcher-xxx",
 "tool": "bing_search", "query": "...", "status": "ok",
 "duration_ms": 264.1, "error": ""}
```

`status` 只有 `ok` / `error`；路径可用 `SEARCH_CALLS_LOG` 覆盖。该文件不应提交 git。

## 硬约束

1. 付费 API 必须有 key 才注册/调用；key 为空直接跳过。
2. 不可恢复错误走进程级禁用；429 走共享 cooldown；不得恢复“每实例独立重试”旧行为。
3. 不要在 `execute()` 里把反爬挑战页当正常结果返回；Baidu 已有“安全验证”检测。
4. 所有搜索工具必须返回统一 schema（title/url/body 或 error），否则 `format_result`、
   `call_log` 和未来评测脚本会坏。
5. 新加后端必须更新本文件状态表，并在 CN 服务器实测 4 条中英文查询后再注册。

## 探测命令（只测免费引擎，不消耗付费额度）

```bash
docker exec -w /app deep-research python - <<'PY'
import asyncio
from deep_research.tools.search import BingSearchTool, BaiduSearchTool

async def main():
    for tool in (BingSearchTool(), BaiduSearchTool()):
        raw = await tool.execute({"query": "DeepSeek V4 架构", "max_results": 3})
        print(tool.name, "->", raw[0] if raw and "error" in raw[0] else len(raw), "results")

asyncio.run(main())
PY
```

跑完研究后按 run 统计：

```bash
grep '"run_id": "<run_id>"' logs/search_calls.jsonl | \
  python3 -c 'import sys,json,collections; c=collections.Counter((json.loads(l)["tool"], json.loads(l)["status"]) for l in sys.stdin); print(c)'
```
