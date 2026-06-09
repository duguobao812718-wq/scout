"""
Scout 错误类型层级。

参考：opensearch-mcp 的错误类型设计。
不同错误类型触发不同的重试/降级策略。
"""

from __future__ import annotations

from typing import Literal


class ScoutError(Exception):
    """Scout 基础异常。"""


class SearchEngineError(ScoutError):
    """搜索引擎错误。

    Attributes:
        engine: 引擎名称。
        kind: 错误类型。
        status: HTTP 状态码（可选）。
    """

    def __init__(
        self,
        message: str,
        engine: str,
        kind: Literal["blocked", "misconfigured", "no-results", "transient"] = "transient",
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.engine = engine
        self.kind = kind
        self.status = status


class SSRFBlockedError(ScoutError):
    """SSRF 防护阻止访问。"""


class RateLimitError(ScoutError):
    """速率限制错误。"""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ContentTooLargeError(ScoutError):
    """内容超过大小限制。"""

    def __init__(self, message: str, size: int, limit: int) -> None:
        super().__init__(message)
        self.size = size
        self.limit = limit


class EngineNotFoundError(ScoutError):
    """引擎不存在。"""


class CacheError(ScoutError):
    """缓存操作错误。"""
