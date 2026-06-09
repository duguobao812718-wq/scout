"""
重试逻辑模块。

提供指数退避重试装饰器。
"""

from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger("scout.retry")


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """重试装饰器（异步函数）。

    Args:
        max_attempts: 最大重试次数。
        delay: 初始延迟秒数。
        backoff: 退避倍数。
        exceptions: 需要重试的异常类型。
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            "重试 %s (尝试 %d/%d): %s",
                            func.__name__,
                            attempt + 1,
                            max_attempts,
                            e,
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            "重试失败 %s (已尝试 %d 次): %s",
                            func.__name__,
                            max_attempts,
                            e,
                        )

            raise last_exception

        return wrapper

    return decorator
