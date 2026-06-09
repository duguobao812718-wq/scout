# Scout

> AI Agent 全能搜索工具 — 完全免费，多引擎，完美适配 AI Agent

## ✨ 特性

- 🔍 **多引擎搜索** — Bing、Brave、Google、DuckDuckGo、Mojeek、SearXNG、Wikipedia、Startpage、Yandex、DuckDuckGo News、Semantic Scholar、arXiv
- 🧠 **语义搜索** — Sentence Transformers + FAISS 意义匹配
- 🖼️ **图片搜索** — SearXNG 图片分类搜索
- 🌐 **网页抓取** — HTML 解析、curl_cffi 浏览器指纹
- 📦 **完全免费** — 无 API key 要求，无使用限制
- 🤖 **AI Agent 适配** — MCP 协议，结构化输出
- ⚡ **高性能** — 并发搜索、SQLite 缓存、RRF 结果合并
- 🔧 **可扩展** — 模块化设计，易于添加新引擎
- 🛡️ **安全** — SSRF 防护、代理支持

## 🚀 快速开始

### 安装（3 步搞定）

```bash
# 1. 克隆仓库
git clone https://github.com/duguobao812718-wq/scout.git
cd scout

# 2. 安装依赖
pip install -e .

# 3. 注册到 Claude Code
claude mcp add -s user scout -- python -m src
```

安装完成后重启 Claude Code，即可使用 `search`、`fetch`、`research` 等 11 个工具。

### 可选：安装语义搜索

```bash
pip install -e .[all]
```

### 可选：配置代理（国内用户）

在项目目录下创建 `.env` 文件：

```env
SCOUT_PROXY=http://127.0.0.1:7897
```

### 可选：使用 Redis 缓存（多实例共享）

```bash
pip install -e .[redis]
```

在 `.env` 中配置：

```env
SCOUT_CACHE_BACKEND=redis
SCOUT_REDIS_URL=redis://localhost:6379/0
```

### 可选：配置 Claude Desktop

在 Claude Desktop 的配置文件中添加：

```json
{
  "mcpServers": {
    "scout": {
      "command": "python",
      "args": ["-m", "src"],
      "cwd": "/path/to/scout"
    }
  }
}
```

## 🛠️ MCP 工具

| 工具 | 功能 | 参数 |
|------|------|------|
| `search` | 多引擎搜索 | query, engines, max_results, freshness, include_domains, exclude_domains, format |
| `fetch` | 抓取单个 URL | url, format |
| `fetch_batch` | 批量抓取 | urls, format |
| `engines` | 列出可用引擎 | - |
| `cache_search` | 搜索已缓存页面 | query, limit, format |
| `semantic_search` | 语义搜索已索引页面 | query, top_k, format |
| `semantic_index_page` | 索引页面供语义搜索 | url, format |
| `image_search` | 图片搜索 | query, max_results, freshness, format |
| `research` | 搜索 + 抓取组合 | question, depth, freshness, format |
| `read_doc` | 读取 PDF 文档 | source, start, length, format |
| `extract_structured` | 提取结构化数据 | url, format |

## 🔒 安全特性

- SSRF 防护（DNS 解析 + IP 范围验证 + 云元数据拦截）
- XML 外部实体防护（defusedxml）
- PDF 下载大小限制 + 超时控制
- 令牌桶限速
- 缓存线程安全（双重检查锁定）

## 📦 MCP 资源

| 资源 URI | 功能 |
|----------|------|
| `cache://stats` | 缓存统计信息（条目数、TTL、路径） |
| `cache://page/{url}` | 读取已缓存的页面内容 |
| `engines://list` | 所有引擎及其能力列表 |

## 💡 MCP 提示词

| 提示词 | 功能 |
|--------|------|
| `research_prompt` | 深入研究提示词 |
| `factcheck_prompt` | 事实核查提示词 |
| `news_brief` | 新闻简报提示词 |
| `compare_sources` | 多源对比提示词 |

## 📁 项目结构

```
scout/
├── src/
│   ├── server.py            # MCP 服务器（7 工具 + 4 提示词）
│   ├── config.py            # 配置模块（pydantic-settings）
│   ├── cache.py             # SQLite 缓存 + FTS5 + stale-while-revalidate
│   ├── utils.py             # 公共工具函数（URL 归一化、标题相似度）
│   ├── ratelimit.py         # 令牌桶限速器
│   ├── formatting.py        # Markdown/JSON 格式化器
│   ├── errors.py            # 错误类型层级
│   ├── url_safety.py        # SSRF 防护
│   ├── semantic.py          # 语义搜索（实验性，可选依赖）
│   ├── structured.py        # 结构化数据提取
│   ├── prompts.py           # MCP 提示词模板
│   ├── engines/             # 搜索引擎
│   │   ├── bing.py          # Bing (RSS)
│   │   ├── brave.py         # Brave (curl_cffi)
│   │   ├── google.py        # Google (curl_cffi)
│   │   ├── duckduckgo.py    # DuckDuckGo (curl_cffi)
│   │   ├── mojeek.py        # Mojeek (独立索引)
│   │   ├── searxng.py       # SearXNG (元搜索，多实例竞速)
│   │   ├── wikipedia.py     # Wikipedia (REST API)
│   │   ├── startpage.py     # Startpage (Google 隐私前端)
│   │   ├── yandex.py        # Yandex (俄罗斯搜索引擎)
│   │   ├── ddg_news.py      # DuckDuckGo News (新闻搜索)
│   │   └── academic.py      # Semantic Scholar + arXiv (学术搜索)
│   └── fetchers/
│       ├── http.py          # HTTP 抓取（aiohttp + curl_cffi）
│       └── documents.py     # PDF 文档读取
├── tests/                   # 69 个测试
├── pyproject.toml
└── .env
```

## 🔧 技术栈

- **语言：** Python 3.10+
- **协议：** MCP (Model Context Protocol)
- **搜索引擎：** Bing (RSS)、Brave、Google、DuckDuckGo、Mojeek、SearXNG、Wikipedia、Startpage、Yandex、DuckDuckGo News、Semantic Scholar、arXiv
- **网页抓取：** aiohttp、curl_cffi、BeautifulSoup4
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
