import socket
from unittest.mock import patch

import pytest

from app.config import settings
from app.core.url_guard import UrlNotAllowed, validate_url


def _addrinfo(ip: str):
    if ":" in ip:
        return [(socket.AF_INET6, None, None, "", (ip, 0, 0, 0))]
    return [(socket.AF_INET, None, None, "", (ip, 0))]


@pytest.fixture()
def public_mode(monkeypatch):
    monkeypatch.setattr(settings, "allow_private_endpoints", False)


class TestLiteralIPs:
    def test_loopback_blocked_in_public_mode(self, public_mode):
        with pytest.raises(UrlNotAllowed):
            validate_url("http://127.0.0.1:8188")

    def test_rfc1918_blocked(self, public_mode):
        for ip in ("10.0.0.5", "172.16.0.9", "192.168.1.10"):
            with pytest.raises(UrlNotAllowed):
                validate_url(f"http://{ip}:8188")

    def test_metadata_ip_blocked(self, public_mode):
        with pytest.raises(UrlNotAllowed):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_public_ip_allowed(self, public_mode):
        assert validate_url("http://93.184.216.34:8188") == "http://93.184.216.34:8188"

    def test_loopback_allowed_in_dev_mode(self):
        # default settings: allow_private_endpoints=True
        assert validate_url("http://127.0.0.1:8188") == "http://127.0.0.1:8188"


class TestHostnames:
    def test_hostname_resolving_to_private_blocked(self, public_mode):
        with patch("app.core.url_guard.socket.getaddrinfo", return_value=_addrinfo("10.1.2.3")):
            with pytest.raises(UrlNotAllowed):
                validate_url("http://internal.example.com:8188")

    def test_hostname_resolving_to_metadata_blocked(self, public_mode):
        with patch("app.core.url_guard.socket.getaddrinfo", return_value=_addrinfo("169.254.169.254")):
            with pytest.raises(UrlNotAllowed):
                validate_url("http://evil.example.com")

    def test_hostname_resolving_to_public_ok(self, public_mode):
        with patch("app.core.url_guard.socket.getaddrinfo", return_value=_addrinfo("93.184.216.34")):
            assert validate_url("http://my-comfy.example.com:8188")

    def test_unresolvable_rejected(self, public_mode):
        with patch("app.core.url_guard.socket.getaddrinfo", side_effect=OSError("dns fail")):
            with pytest.raises(UrlNotAllowed):
                validate_url("http://ghost.example.com")

    def test_localhost_hostname_blocked_in_public_mode(self, public_mode):
        with patch("app.core.url_guard.socket.getaddrinfo", return_value=_addrinfo("127.0.0.1")):
            with pytest.raises(UrlNotAllowed):
                validate_url("http://localhost:1234/v1")


class TestSchemes:
    def test_bad_scheme(self, public_mode):
        for url in ("ftp://example.com", "file:///etc/passwd", "gopher://x", "example.com:8188"):
            with pytest.raises(UrlNotAllowed):
                validate_url(url)

    def test_empty(self, public_mode):
        with pytest.raises(UrlNotAllowed):
            validate_url("")
