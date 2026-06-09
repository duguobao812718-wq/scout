# Scout

<div align="center">

**AI Agent 全能搜索工具**

*完全免费 · 27 引擎 · 多模态 · MCP 协议*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-249-green.svg)](tests/)
[![MCP](https://img.shields.io/badge/MCP-compatible-orange.svg)](https://modelcontextprotocol.io/)

[快速开始](#-快速开始) · [功能特性](#-功能特性) · [搜索引擎](#-搜索引擎) · [MCP 工具](#️-mcp-工具) · [配置选项](#-配置选项)

</div>

---

## 🎯 为什么选择 Scout？

Scout 是专为 AI Agent 设计的全能搜索工具，通过 MCP 协议提供标准化的搜索接口。

| 特性 | Scout | Tavily | Exa | SerpAPI |
|------|-------|--------|-----|---------|
| **免费使用** | ✅ 完全免费 | ❌ 有限额 | ❌ 有限额 | ❌ 付费 |
| **无需 API Key** | ✅ | ❌ | ❌ | ❌ |
| **搜索引擎数量** | 26 | 1 | 1 | 1 |
| **多模态搜索** | ✅ 视频/图片/播客 | ❌ | ❌ | ❌ |
| **MCP 协议** | ✅ 原生支持 | ❌ | ❌ | ❌ |
| **本地缓存** | ✅ SQLite/Redis | ❌ | ❌ | ❌ |

---

## ✨ 功能特性

### 🔍 27 个搜索引擎

```
通用搜索 (8)    学术搜索 (4)    代码搜索 (2)
    ↓               ↓               ↓
社区搜索 (3)    包管理 (3)      知识搜索 (1)
    ↓               ↓               ↓
新闻搜索 (1)    多模态搜索 (4)   地图搜索 (1)
                    ↓               ↓
        YouTube · Bilibili ·     OpenStreetMap
        Unsplash · Podcast
```

### 🎬 多模态搜索

- **视频搜索** — YouTube、Bilibili 视频教程
- **图片搜索** — Unsplash 高质量图片
- **播客搜索** — Podcast 节目发现
- **地图搜索** — OpenStreetMap 地点查询

### ⚡ 高性能架构

- **并发搜索** — asyncio 异步并发，不阻塞
- **智能缓存** — SQLite + FTS5 全文搜索
- **结果合并** — RRF (Reciprocal Rank Fusion) 算法
- **熔断器** — 引擎连续失败自动暂停

### 🛡️ 安全防护

- **SSRF 防护** — DNS 解析 + IP 范围验证
- **并发限制** — Semaphore 控制最大并发数
- **重定向验证** — 每次重定向都检查安全性

---

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/duguobao812718-wq/scout.git
cd scout

# 安装依赖
pip install -e .

# 注册到 Claude Code
claude mcp add -s user scout -- python -m src
```

重启 Claude Code，即可使用 12 个搜索工具。

### 验证安装

```bash
# 列出可用引擎
python -m src --list-engines

# 运行测试
python -m pytest tests/ -v
```

---

## 🔍 搜索引擎

### 通用搜索

| 引擎 | 特点 | 适用场景 |
|------|------|----------|
| Google | 最全的搜索结果 | 通用搜索 |
| Bing | 微软搜索引擎 | 通用搜索 |
| Brave | 隐私保护 | 隐私搜索 |
| DuckDuckGo | 无追踪 | 隐私搜索 |
| Mojeek | 独立索引 | 替代选择 |
| Startpage | Google 隐私前端 | 隐私搜索 |
| Yandex | 俄罗斯搜索引擎 | 俄语内容 |
| SearXNG | 元搜索，多实例 | 自建实例 |

### 学术搜索

| 引擎 | 特点 | 适用场景 |
|------|------|----------|
| Semantic Scholar | AI 驱动的学术搜索 | 论文发现 |
| arXiv | 预印本论文 | 最新研究 |
| Google Scholar | 最全的学术搜索 | 论文引用 |
| PubMed | 生物医学文献 | 医学研究 |

### 代码搜索

| 引擎 | 特点 | 适用场景 |
|------|------|----------|
| GitHub | 代码仓库搜索 | 开源项目 |
| StackOverflow | 编程问答 | 问题解决 |

### 社区搜索

| 引擎 | 特点 | 适用场景 |
|------|------|----------|
| Reddit | 社区讨论 | 深度讨论 |
| HackerNews | 技术新闻 | 技术趋势 |
| Twitter/X | 社交媒体 | 实时动态 |

### 包管理搜索

| 引擎 | 特点 | 适用场景 |
|------|------|----------|
| npm | JS/TS 包 | 前端开发 |
| PyPI | Python 包 | Python 开发 |
| HuggingFace | AI 模型/数据集 | AI 开发 |

### 多模态搜索

| 引擎 | 特点 | 适用场景 |
|------|------|----------|
| YouTube | 视频搜索 | 视频教程 |
| Bilibili | 中文视频 | 技术分享 |
| Unsplash | 图片搜索 | 高质量图片 |
| Podcast | 播客搜索 | 音频内容 |

### 地图搜索

| 引擎 | 特点 | 适用场景 |
|------|------|----------|
| OpenStreetMap | 免费地图 API | 地点查询、地址搜索、POI 搜索 |

---

## 🛠️ MCP 工具

| 工具 | 功能 | 示例 |
|------|------|------|
| `search` | 多引擎搜索 | `search("Python tutorial")` |
| `fetch` | 抓取页面 | `fetch("https://python.org")` |
| `fetch_batch` | 批量抓取 | `fetch_batch([url1, url2])` |
| `research` | 深度研究 | `research("What is ML?")` |
| `summarize` | 搜索+摘要 | `summarize("latest AI news")` |
| `read_doc` | 读取 PDF | `read_doc("paper.pdf")` |
| `engines` | 列出引擎 | `engines()` |
| `cache_search` | 搜索缓存 | `cache_search("Python")` |
| `semantic_search` | 语义搜索 | `semantic_search("machine learning")` |
| `extract_structured` | 提取结构化数据 | `extract_structured(url)` |

---

## ⚙️ 配置选项

### 环境变量

在项目目录下创建 `.env` 文件：

```env
# 代理配置（国内用户）
SCOUT_PROXY=http://127.0.0.1:7897

# 缓存后端
SCOUT_CACHE_BACKEND=sqlite  # 或 redis
SCOUT_REDIS_URL=redis://localhost:6379/0

# 速率限制
SCOUT_RATE_LIMIT_PER_MINUTE=60

# 安全搜索
SCOUT_SAFESEARCH=moderate  # off / moderate / strict
```

### 高级配置

```env
# 请求超时
SCOUT_REQUEST_TIMEOUT=15

# 最大结果数
SCOUT_MAX_RESULTS=10

# 缓存 TTL
SCOUT_CACHE_TTL_SECONDS=604800  # 7 天
```

---

## 📊 性能指标

| 指标 | 值 |
|------|-----|
| 搜索引擎数量 | 26 |
| MCP 工具数量 | 12 |
| 测试用例数量 | 243 |
| 代码行数 | ~8500 |
| 平均搜索延迟 | < 2s |
| 缓存命中延迟 | < 10ms |

---

## 🏗️ 项目结构

```
scout/
├── src/
│   ├── server.py           # MCP 服务器入口
│   ├── config.py           # 配置管理
│   ├── cache.py            # SQLite 缓存
│   ├── cache_redis.py      # Redis 缓存
│   ├── scoring.py          # 结果评分
│   ├── suggestions.py      # 搜索建议
│   ├── summary.py          # 结果摘要
│   ├── ratelimit.py        # 限速 + 熔断器
│   ├── engines/            # 26 个搜索引擎
│   │   ├── __init__.py     # 引擎基类 + 注册表
│   │   ├── google.py       # 通用搜索
│   │   ├── youtube.py      # 视频搜索
│   │   └── ...
│   └── fetchers/           # 内容抓取
│       ├── http.py         # HTTP 抓取
│       └── documents.py    # PDF 解析
├── tests/                  # 测试用例
├── pyproject.toml          # 项目配置
└── README.md               # 本文件
```

---

## 🤝 贡献指南

欢迎贡献新的搜索引擎！添加新引擎只需 3 步：

```python
# 1. 创建 src/engines/myengine.py
from . import JsonApiEngine, register_engine

class MyEngine(JsonApiEngine):
    name = "myengine"
    
    def build_url(self, query, max_results, filters=None):
        return f"https://api.example.com/search?q={query}"
    
    def parse(self, data):
        # 解析返回结果
        return [SearchResult(...)]

# 2. 注册引擎
register_engine(MyEngine())

# 3. 在 __init__.py 中导入
from . import myengine
```

运行测试验证：

```bash
python -m pytest tests/ -v
```

---

## 📚 参考项目

- [free-search-mcp](https://github.com/ymylive/free-search-mcp) — 免费搜索 MCP
- [mcp-smart-searcher](https://github.com/PXSR/mcp-smart-searcher) — 多引擎搜索
- [exa-mcp-server](https://github.com/exa-labs/exa-mcp-server) — 语义搜索
- [Agent-Reach](https://github.com/Panniantong/Agent-Reach) — 多平台抓取

---

## 📄 许可证

[MIT License](LICENSE)

---

<div align="center">

**Scout** — 让 AI Agent 看得更远，搜得更广

[GitHub](https://github.com/duguobao812718-wq/scout) · [Issues](https://github.com/duguobao812718-wq/scout/issues) · [License](LICENSE)

</div>
