# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-06-09

### Added

**搜索引擎 (12 个)**
- Wikipedia — REST API，零反爬，知识类查询最佳
- Startpage — Google 隐私前端，curl_cffi 浏览器指纹
- Yandex — 俄语/中文内容覆盖好
- DuckDuckGo News — 新闻专项搜索
- Semantic Scholar — 学术论文 API，免费无 key
- arXiv — 预印本论文，Atom XML API
- Mojeek — 独立索引，无反爬措施
- SearXNG — 元搜索，多实例竞速

**MCP 工具 (13 个)**
- `summarize` — 搜索+抓取+要点提取+可信度评估一站式
- `image_search` — 图片搜索（SearXNG）
- `cache_search` — 搜索已缓存页面（FTS5）
- `semantic_search` — 语义搜索已索引页面（FAISS）
- `semantic_index_page` — 索引页面供语义搜索
- `extract_structured` — 提取结构化数据（JSON-LD/OG/Twitter Card）
- `read_doc` — 读取 PDF 文档
- `fetch_batch` — 批量抓取（最多 10 个 URL）

**MCP 资源 (3 个)**
- `cache://page/{url}` — 读取已缓存页面内容
- `cache://stats` — 缓存统计信息
- `engines://list` — 引擎列表及能力

**搜索质量**
- 结果质量评分：域名信誉、新鲜度、多引擎命中、页面质量信号
- 搜索建议：相关搜索提取、拼写纠错、查询改写
- 结果摘要：关键要点提取、可信度评估

**缓存**
- Redis 缓存后端（`pip install scout[redis]`）
- 缓存策略可配置（`SCOUT_CACHE_BACKEND=sqlite|redis`）

**安全**
- SSRF 重定向绕过防护
- PDF 流式下载防止内存耗尽
- FTS5 查询转义防注入
- Google URL scheme 验证
- arXiv HTTP→HTTPS
- aiohttp session 竞态修复

### Changed
- 重构引擎注册表，支持延迟加载
- RRF 合并集成质量评分
- 错误分类体系（blocked/transient/misconfigured）
- stale-while-revalidate 缓存策略

### Removed
- 清理死代码：deep.py, research.py, retry.py, browser.py

## [0.1.0] - 2026-06-09

### Added
- 初始版本
- MCP 服务器框架（FastMCP）
- 4 个搜索引擎：Bing, Brave, Google, DuckDuckGo
- 基础网页抓取（aiohttp + BeautifulSoup）
- SQLite 缓存 + FTS5
- RRF 结果合并
- 令牌桶限速器
- SSRF 防护
- 语义搜索（Sentence Transformers + FAISS）
- 106 个测试
