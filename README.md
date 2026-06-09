# Scout

> AI Agent 全能搜索工具 — 完全免费，多引擎，完美适配 AI Agent

## ✨ 特性

- 🔍 **多引擎搜索** — Bing (RSS)、Brave、Google、DuckDuckGo
- 🧠 **语义搜索** — 基于 Sentence Transformers + FAISS
- 🌐 **网页抓取** — HTML 解析、Playwright 浏览器渲染
- 📦 **完全免费** — 无 API key 要求，无使用限制
- 🤖 **AI Agent 适配** — MCP 协议，结构化输出
- ⚡ **高性能** — 并发搜索、SQLite 缓存、RRF 结果合并
- 🔧 **可扩展** — 模块化设计，易于添加新引擎
- 🛡️ **安全** — SSRF 防护、代理支持

## 🚀 快速开始

### 安装

```bash
# 基础安装
pip install -e .

# 安装所有可选依赖（语义搜索、浏览器）
pip install -e .[all]
```

### 注册为 MCP 服务器

```bash
# 注册到 Claude Code
claude mcp add -s user scout -- python -m src

# 测试
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python -m src
```

### 配置

创建 `.env` 文件：

```env
# 代理配置（可选）
SCOUT_PROXY=http://127.0.0.1:7897

# 搜索引擎
SCOUT_DEFAULT_ENGINES=bing,brave

# 缓存（7 天）
SCOUT_CACHE_TTL_SECONDS=604800

# 日志
SCOUT_LOG_LEVEL=INFO
```

## 🛠️ MCP 工具

| 工具 | 功能 | 参数 |
|------|------|------|
| `search` | 多引擎搜索 | query, engines, max_results, format |
| `fetch` | 抓取单个 URL | url, format |
| `engines` | 列出可用引擎 | - |
| `research` | 搜索 + 抓取组合 | question, depth, format |
| `extract_structured` | 提取结构化数据 | url, format |

## 💡 MCP 提示词

| 提示词 | 功能 |
|--------|------|
| `research_prompt` | 深入研究提示词 |
| `factcheck_prompt` | 事实核查提示词 |
| `news_brief` | 新闻简报提示词 |

## 📁 项目结构

```
scout/
├── src/
│   ├── server.py            # MCP 服务器（5 工具 + 3 提示词）
│   ├── config.py            # 配置模块（pydantic-settings）
│   ├── cache.py             # SQLite 缓存 + FTS5
│   ├── ratelimit.py         # 令牌桶限速器
│   ├── formatting.py        # Markdown/JSON 格式化器
│   ├── errors.py            # 错误类型层级
│   ├── url_safety.py        # SSRF 防护
│   ├── semantic.py          # 语义搜索（Sentence Transformers + FAISS）
│   ├── deep.py              # 深度搜索（多轮搜索）
│   ├── structured.py        # 结构化数据提取
│   ├── prompts.py           # MCP 提示词模板
│   ├── engines/             # 搜索引擎
│   │   ├── bing.py          # Bing (RSS)
│   │   ├── brave.py         # Brave
│   │   ├── google.py        # Google
│   │   └── duckduckgo.py    # DuckDuckGo
│   └── fetchers/            # 抓取器
│       ├── http.py          # HTTP 抓取
│       └── browser.py       # Playwright 浏览器
├── pyproject.toml
└── .env
```

## 🔧 技术栈

- **语言：** Python 3.10+
- **协议：** MCP (Model Context Protocol)
- **搜索引擎：** Bing (RSS)、Brave、Google、DuckDuckGo
- **网页抓取：** aiohttp、BeautifulSoup4、Playwright
- **缓存：** SQLite + FTS5
- **语义搜索：** Sentence Transformers + FAISS
- **并发：** asyncio

## 📝 使用示例

### 搜索

```python
from src.server import search

result = await search("Python tutorial", engines=["bing"], max_results=5, format="markdown")
```

### 抓取页面

```python
from src.server import fetch

result = await fetch("https://www.python.org/", format="markdown")
```

### 研究

```python
from src.server import research

result = await research("What is Python?", depth=3, format="json")
```

### 提取结构化数据

```python
from src.server import extract_structured

result = await extract_structured("https://www.python.org/", format="json")
```

## 📚 参考项目

- [free-search-mcp](https://github.com/ymylive/free-search-mcp) — 免费搜索 MCP（最高参考价值）
- [mcp-smart-searcher](https://github.com/PXSR/mcp-smart-searcher) — 8 引擎并发搜索
- [opensearch-mcp](https://github.com/minpeter/opensearch-mcp) — 零配置搜索 MCP
- [exa-mcp-server](https://github.com/exa-labs/exa-mcp-server) — 语义搜索 MCP
- [ferris-search](https://github.com/lispking/ferris-search) — 14 引擎搜索
- [Agent-Reach](https://github.com/Panniantong/Agent-Reach) — 多平台内容抓取
- [MindSearch](https://github.com/InternLM/MindSearch) — 类 Perplexity 搜索引擎
- [DeepResearch](https://github.com/alibaba-nlp/webagent) — 阿里通义深度研究
- [OpenSeeker](https://github.com/PolarSeeker/OpenSeeker) — 开源搜索 Agent

## 📄 许可证

MIT License
