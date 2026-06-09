# Scout 项目配置

> AI Agent 全能搜索工具 — MCP 协议，12 引擎，完全免费

## 项目结构

```
src/
├── server.py          # MCP 服务器（12 工具 + 3 资源 + 4 提示词）
├── config.py          # pydantic-settings 配置
├── cache.py           # SQLite 缓存 + FTS5
├── cache_redis.py     # Redis 缓存后端（可选）
├── scoring.py         # 结果质量评分
├── suggestions.py     # 搜索建议（相关搜索/纠错/改写）
├── summary.py         # 结果摘要 + 可信度评估
├── utils.py           # URL 归一化/标题相似度
├── formatting.py      # Markdown/JSON 格式化
├── url_safety.py      # SSRF 防护
├── ratelimit.py       # 令牌桶限速
├── semantic.py        # 语义搜索（FAISS）
├── structured.py      # 结构化数据提取
├── prompts.py         # MCP 提示词模板
├── errors.py          # 错误类型层级
├── engines/           # 12 个搜索引擎
└── fetchers/          # HTTP 抓取 + PDF 文档
tests/                 # 201 个测试
```

## 常用命令

```bash
# 运行测试
python -m pytest tests/ -v

# lint 检查
ruff check src/ tests/

# 安装
pip install -e .

# 注册 MCP
claude mcp add -s user scout -- python -m src
```

## 代码规范

- Python 3.10+，使用 `from __future__ import annotations`
- 类型注解：参数和返回值都要有
- 异步优先：IO 操作用 async/await
- 测试：新功能必须有测试，保持 201+ 通过
- ruff lint：提交前跑 `ruff check`
- 安全：用户输入必须验证，URL 必须过 SSRF 检查
