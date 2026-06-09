"""URL 安全模块单元测试。"""

import ipaddress

import pytest

from src.url_safety import (
    UnsafeURLError,
    _ip_is_blocked,
    assert_ip_allowed,
)


def test_ip_is_blocked_private():
    """测试私有 IP 检测。"""
    assert _ip_is_blocked(ipaddress.ip_address("10.0.0.1")) is True
    assert _ip_is_blocked(ipaddress.ip_address("172.16.0.1")) is True
    assert _ip_is_blocked(ipaddress.ip_address("192.168.1.1")) is True


def test_ip_is_blocked_loopback():
    """测试回环地址检测。"""
    assert _ip_is_blocked(ipaddress.ip_address("127.0.0.1")) is True
    assert _ip_is_blocked(ipaddress.ip_address("127.0.0.2")) is True


def test_ip_is_blocked_link_local():
    """测试链路本地地址检测。"""
    assert _ip_is_blocked(ipaddress.ip_address("169.254.1.1")) is True


def test_ip_is_blocked_public():
    """测试公网 IP 检测。"""
    assert _ip_is_blocked(ipaddress.ip_address("8.8.8.8")) is False
    assert _ip_is_blocked(ipaddress.ip_address("1.1.1.1")) is False


def test_assert_ip_allowed_public():
    """测试公网 IP 允许访问。"""
    assert_ip_allowed("8.8.8.8")  # 不应抛出异常


def test_assert_ip_allowed_private():
    """测试私有 IP 禁止访问。"""
    with pytest.raises(UnsafeURLError):
        assert_ip_allowed("127.0.0.1")


def test_assert_ip_allowed_metadata():
    """测试云元数据服务 IP 禁止访问。"""
    with pytest.raises(UnsafeURLError):
        assert_ip_allowed("169.254.169.254")
