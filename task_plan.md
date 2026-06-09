# Scout 增强计划

## 总览

7 个阶段全部完成 ✅

## 阶段 1：Docker 部署 ⭐ — 暂缓
- 推出公开版本时再做

## 阶段 2：更多搜索引擎 ⭐ ✅
- [x] Wikipedia 引擎（REST API，零反爬）
- [x] Startpage 引擎（HTML 解析，curl_cffi）
- [x] Yandex 引擎（HTML 解析）
- [x] DuckDuckGo News 引擎（HTML 解析，curl_cffi）

## 阶段 3：MCP Resources ⭐⭐ ✅
- [x] cache://page/{url} — Agent 可直接读取已缓存页面
- [x] cache://stats — 缓存统计信息
- [x] engines://list — 引擎列表资源

## 阶段 4：结果质量优化 ⭐⭐ ✅
- [x] 域名信誉评分（白名单/黑名单）
- [x] 新鲜度加权（越新越高分）
- [x] 多引擎命中加权
- [x] 页面质量信号（标题/摘要/URL 结构）

## 阶段 5：搜索建议 ⭐⭐⭐ ✅
- [x] 相关搜索提取（Google/Bing/Brave/DDG）
- [x] 拼写纠错建议
- [x] 查询改写（引号/空格/缩短）

## 阶段 6：结果摘要 ⭐⭐⭐ ✅
- [x] 关键要点提取（数字/定义/因果/重要性启发式）
- [x] 可信度评估（来源数/多样性/域名信誉/多引擎验证）
- [x] summarize MCP 工具

## 阶段 7：分布式缓存 ⭐⭐ ✅
- [x] Redis 缓存后端（RedisCache）
- [x] 缓存策略可配置（SCOUT_CACHE_BACKEND=sqlite|redis）
- [x] 多实例共享缓存

## 最终统计

| 维度 | 数量 |
|------|------|
| MCP 工具 | 13 个 |
| MCP 资源 | 3 个 |
| MCP 提示词 | 4 个 |
| 搜索引擎 | 12 个 |
| 测试 | 201 个 |
| 模块 | 15 个 |
