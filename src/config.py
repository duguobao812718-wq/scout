"""
Scout 配置模块 — 基于 pydantic-settings，支持环境变量和 .env 文件。

所有配置项以 SCOUT_ 为前缀，例如：
  SCOUT_CACHE_TTL_SECONDS=3600
  SCOUT_DEFAULT_ENGINES=duckduckgo,bing
  SCOUT_PROXY=http://127.0.0.1:7897
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Scout 运行时配置，从环境变量或 .env 文件加载。"""

    model_config = SettingsConfigDict(
        env_prefix="SCOUT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 缓存 ──────────────────────────────────────────────
    cache_dir: Path = Path.home() / ".cache" / "scout"
    cache_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 天
    cache_backend: str = "sqlite"  # "sqlite" 或 "redis"
    redis_url: str = "redis://localhost:6379/0"

    # ── 引擎 ──────────────────────────────────────────────
    default_engines: list[str] = ["duckduckgo", "bing"]
    max_results_per_engine: int = 10

    # ── 限速 ──────────────────────────────────────────────
    rate_limit_per_minute: int = 30

    # ── HTTP ──────────────────────────────────────────────
    request_timeout: float = 15.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    accept_language: str = "en-US,en;q=0.9"

    # ── 搜索行为 ──────────────────────────────────────────
    safesearch: Literal["strict", "moderate", "off"] = "moderate"
    region: str = "us-en"

    # ── 代理 ──────────────────────────────────────────────
    proxy: str | None = None
    proxy_engines: list[str] = []  # 仅这些引擎使用代理，空列表 = 全部
    no_proxy_engines: list[str] = []  # 这些引擎跳过代理（国内引擎）

    # ── SearXNG ─────────────────────────────────────────
    searxng_instances: list[str] = []  # 自定义实例列表，空列表使用默认

    # ── 安全 ──────────────────────────────────────────────
    allow_private_hosts: bool = False
    max_response_bytes: int = 25_000_000  # 25 MB
    max_content_chars: int = 50_000
    max_pdf_pages: int = 100

    # ── 日志 ──────────────────────────────────────────────
    log_level: str = "INFO"

    # ── 路径辅助 ──────────────────────────────────────────
    def cache_path(self) -> Path:
        """返回 SQLite 缓存文件路径，自动创建目录。"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / "cache.sqlite"


# 全局单例
settings = Settings()
