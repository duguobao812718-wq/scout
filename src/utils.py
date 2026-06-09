"""公共工具函数。"""

from __future__ import annotations

import urllib.parse
from urllib.parse import urlparse

# 追踪参数集合（用于 URL 归一化）
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source", "spm", "from", "suid",
    "spm_id", "vd_source", "share_source", "track", "spm_id_from",
})


def normalize_url(url: str) -> str:
    """归一化 URL 用于去重比较。

    去除追踪参数、www 前缀、尾部斜杠。
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    qs = urllib.parse.parse_qs(parsed.query)
    filtered = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_PARAMS}
    clean_query = urllib.parse.urlencode(filtered, doseq=True)
    path = parsed.path.rstrip("/") or "/"
    return f"{host}{path}{'?' + clean_query if clean_query else ''}"


def title_similarity(a: str, b: str) -> float:
    """计算两个标题的 token 重叠比率（0.0-1.0）。"""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = len(tokens_a & tokens_b)
    return overlap / min(len(tokens_a), len(tokens_b))


def unwrap_google_url(url: str) -> str:
    """解包 Google 重定向 URL。

    Google 将外部链接包装为 /url?q=<target>&...
    """
    if not url:
        return ""
    if url.startswith("/url?"):
        parsed = urlparse(f"https://www.google.com{url}")
        qs = urllib.parse.parse_qs(parsed.query)
        if "q" in qs:
            target = qs["q"][0]
            # 验证目标 URL 的 scheme，防止 javascript: / data: 等危险协议
            if target.startswith(("http://", "https://")):
                return target
            return url
    if url.startswith("http"):
        return url
    return url
