from unittest.mock import patch

import pytest

from app.core.ssrf import is_safe_webhook_url


def test_https_url_accepted():
    with patch("app.core.ssrf._is_public_host", return_value=True):
        assert is_safe_webhook_url("https://api.example.com/webhook")


def test_http_scheme_rejected():
    assert not is_safe_webhook_url("http://api.example.com/webhook")


def test_ftp_scheme_rejected():
    assert not is_safe_webhook_url("ftp://api.example.com/webhook")


def test_empty_and_too_long_rejected():
    assert not is_safe_webhook_url("")
    assert not is_safe_webhook_url("https://example.com/" + "a" * 2100)


def test_userinfo_rejected():
    assert not is_safe_webhook_url("https://user:pass@api.example.com/webhook")


def test_missing_host_rejected():
    assert not is_safe_webhook_url("https:///webhook")


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "127.0.0.1",
        "10.0.0.5",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "::1",
    ],
)
def test_non_public_hosts_rejected(host):
    assert not is_safe_webhook_url(f"https://{host}/webhook")


def test_public_host_accepted():
    with patch("app.core.ssrf._is_public_host", return_value=True):
        assert is_safe_webhook_url("https://8.8.8.8/webhook")
