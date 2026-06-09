# Scout

> AI Agent 全能搜索工具 — 完全免费，多引擎，完美适配 AI Agent

## 特性

- 🔍 **多引擎搜索** — DuckDuckGo、Bing、Brave、Google 等
- 🧠 **语义搜索** — 基于 Sentence Transformers + FAISS
- 🌐 **网页抓取** — HTML、PDF、JS 渲染（Playwright）
- 📦 **完全免费** — 无 API key 要求，无限制
- 🤖 **AI Agent 适配** — MCP 协议，结构化输出
- ⚡ **高性能** — 并发搜索，SQLite 缓存
- 🔧 **可扩展** — 模块化设计，易于添加新引擎

## 项目结构

```
scout/
├── src/
│   ├── engines/        # 搜索引擎
│   ├── fetchers/       # 网页抓取
│   ├── search/         # 搜索逻辑
│   ├── cache/          # 缓存
│   └── utils/          # 工具函数
├── docs/               # 文档
├── tests/              # 测试
└── reference/          # 参考项目源码
```

## 参考项目

- [opensearch-mcp](https://github.com/minpeter/opensearch-mcp) — 零配置搜索 MCP
- [exa-mcp-server](https://github.com/exa-labs/exa-mcp-server) — 语义搜索 MCP
- [Agent-Reach](https://github.com/Panniantong/Agent-Reach) — 多平台内容抓取
- [free-search-mcp](https://github.com/ymylive/free-search-mcp) — 免费搜索 MCP
- [ferris-search](https://github.com/lispking/ferris-search) — 14 引擎搜索
- [mcp-smart-searcher](https://github.com/PXSR/mcp-smart-searcher) — 8 引擎并发搜索
- [Tavily](https://tavily.com) — AI 优化搜索 API
- [MindSearch](https://github.com/InternLM/MindSearch) — 类 Perplexity 搜索引擎
- [DeepResearch](https://github.com/alibaba-nlp/webagent) — 阿里通义深度研究
- [OpenSeeker](https://github.com/PolarSeeker/OpenSeeker) — 开源搜索 Agent

## 快速开始

```bash
# 安装
pip install -e .

# 添加到 Claude Code
claude mcp add -s user scout -- scout

# 测试
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | scout
```

## 许可证

MIT License
