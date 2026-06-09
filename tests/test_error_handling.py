"""错误分类和错误提示测试。"""

import pytest

from src.engines import _classify_error
from src.formatting import errors_to_hint


class TestClassifyError:
    """错误分类测试。"""

    def test_timeout_is_transient(self):
        """超时错误应分类为 transient。"""
        e = TimeoutError("connection timed out")
        assert _classify_error(e) == "transient"

    def test_connection_error_is_transient(self):
        """连接错误应分类为 transient。"""
        e = ConnectionError("connection refused")
        assert _classify_error(e) == "transient"

    def test_dns_error_is_misconfigured(self):
        """DNS 错误应分类为 misconfigured。"""
        e = OSError("getaddrinfo failed")
        assert _classify_error(e) == "misconfigured"

    def test_captcha_message_is_blocked(self):
        """包含 captcha 的错误应分类为 blocked。"""
        e = Exception("CAPTCHA challenge detected")
        assert _classify_error(e) == "blocked"

    def test_403_is_blocked(self):
        """403 错误应分类为 blocked。"""
        # 模拟有 status 属性的异常
        class HttpError(Exception):
            status = 403
        e = HttpError("forbidden")
        assert _classify_error(e) == "blocked"

    def test_429_is_blocked(self):
        """429 限速应分类为 blocked。"""
        class HttpError(Exception):
            status = 429
        e = HttpError("too many requests")
        assert _classify_error(e) == "blocked"

    def test_500_is_transient(self):
        """500 服务器错误应分类为 transient。"""
        class HttpError(Exception):
            status = 500
        e = HttpError("internal server error")
        assert _classify_error(e) == "transient"

    def test_unknown_is_transient(self):
        """未知错误默认分类为 transient（可重试）。"""
        e = ValueError("something went wrong")
        assert _classify_error(e) == "transient"


class TestErrorsToHint:
    """错误提示测试。"""

    def test_empty_errors(self):
        """空错误返回空字符串。"""
        assert errors_to_hint({}) == ""
        assert errors_to_hint(None) == ""

    def test_blocked_hint(self):
        """blocked 错误提示应建议换引擎。"""
        errors = {
            "brave": {"error": "429 Too Many Requests", "error_kind": "blocked"},
        }
        hint = errors_to_hint(errors)
        assert "被封禁" in hint
        assert "brave" in hint
        assert "其他引擎" in hint or "重试" in hint

    def test_transient_hint(self):
        """transient 错误提示应建议重试。"""
        errors = {
            "google": {"error": "connection timeout", "error_kind": "transient"},
        }
        hint = errors_to_hint(errors)
        assert "临时错误" in hint
        assert "google" in hint
        assert "重试" in hint

    def test_misconfigured_hint(self):
        """misconfigured 错误提示应建议检查配置。"""
        errors = {
            "bing": {"error": "DNS resolution failed", "error_kind": "misconfigured"},
        }
        hint = errors_to_hint(errors)
        assert "配置问题" in hint
        assert "bing" in hint

    def test_mixed_errors(self):
        """多种错误类型同时出现。"""
        errors = {
            "brave": {"error": "429", "error_kind": "blocked"},
            "google": {"error": "timeout", "error_kind": "transient"},
            "bing": {"error": "DNS", "error_kind": "misconfigured"},
        }
        hint = errors_to_hint(errors)
        assert "被封禁" in hint
        assert "临时错误" in hint
        assert "配置问题" in hint

    def test_all_key(self):
        """'all' 错误键应被特殊处理。"""
        errors = {"all": "无可用引擎"}
        hint = errors_to_hint(errors)
        assert "无可用引擎" in hint

    def test_backward_compat_string_errors(self):
        """兼容旧的字符串格式错误。"""
        errors = {"brave": "some error string"}
        hint = errors_to_hint(errors)
        # 字符串错误默认为 transient
        assert "临时错误" in hint
        assert "brave" in hint
