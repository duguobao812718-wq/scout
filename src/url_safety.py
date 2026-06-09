"""
SSRF (Server-Side Request Forgery) 防护模块。

参考：free-search-mcp 的 url_safety.py 实现。
- 协议检查：只允许 http/https
- DNS 解析：解析所有 A/AAAA 记录
- IP 范围验证：拒绝私有/保留/链路本地地址
- 防止 DNS rebinding：解析后再次验证
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    """URL 未通过安全检查。"""


async def assert_url_allowed(url: str) -> None:
    """检查 URL 是否安全可访问。

    检查项：
    1. 协议必须是 http 或 https
    2. 主机名不能为空
    3. DNS 解析所有地址
    4. 所有地址必须在允许范围内

    Raises:
        UnsafeURLError: URL 未通过安全检查。
    """
    from .config import settings

    # 解析 URL
    parsed = urlparse(url)

    # 协议检查
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"不支持的协议: {parsed.scheme}")

    # 主机名检查
    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL 缺少主机名")

    # 如果允许私有主机，跳过 IP 检查
    if settings.allow_private_hosts:
        return

    # DNS 解析
    try:
        addresses = await _resolve_hostname(hostname)
    except socket.gaierror as e:
        raise UnsafeURLError(f"DNS 解析失败: {hostname} ({e})")

    # 验证所有解析到的地址
    for addr in addresses:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue  # 跳过无效地址

        if _ip_is_blocked(ip):
            raise UnsafeURLError(
                f"IP 地址在禁止范围内: {addr} (主机: {hostname})"
            )


def assert_ip_allowed(ip_str: str) -> None:
    """检查 IP 地址是否允许访问（用于重定向验证）。

    Raises:
        UnsafeURLError: IP 地址在禁止范围内。
    """
    from .config import settings

    if settings.allow_private_hosts:
        return

    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        raise UnsafeURLError(f"无效的 IP 地址: {ip_str}")

    if _ip_is_blocked(ip):
        raise UnsafeURLError(f"IP 地址在禁止范围内: {ip_str}")


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """检查 IP 是否在黑名单中。

    黑名单范围：
    - loopback (127.0.0.0/8, ::1)
    - link-local (169.254.0.0/16, fe80::/10)
    - private (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)
    - reserved
    - multicast
    - unspecified
    """
    # IPv4-mapped IPv6 转换
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    # 检查各种禁止范围
    blocked_networks = [
        # Loopback
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("::1/128"),
        # Link-local
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("fe80::/10"),
        # Private
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("fc00::/7"),
        # 云元数据服务
        ipaddress.ip_network("169.254.169.254/32"),  # AWS/GCP/Azure
    ]

    for network in blocked_networks:
        if ip in network:
            return True

    # 检查是否是保留/未指定/多播地址
    if ip.is_reserved or ip.is_unspecified or ip.is_multicast:
        return True

    return False


async def _resolve_hostname(hostname: str) -> list[str]:
    """异步解析主机名，返回所有 IP 地址。"""
    import asyncio

    # 使用 asyncio 的 DNS 解析
    loop = asyncio.get_event_loop()
    try:
        # getaddrinfo 返回所有地址（IPv4 和 IPv6）
        infos = await loop.getaddrinfo(
            hostname,
            None,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
        addresses = []
        for family, _, _, _, sockaddr in infos:
            addr = sockaddr[0]
            if addr not in addresses:
                addresses.append(addr)
        return addresses
    except socket.gaierror:
        raise
