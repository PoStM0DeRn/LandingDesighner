"""SSRF guard for user-supplied service URLs (ComfyUI, LM Studio endpoints).

Visitors type their own service URLs. A public VDS must not become a scanner
for internal networks, so (unless explicitly allowed) URLs pointing at
loopback, private ranges, link-local (including cloud metadata), multicast
and unspecified addresses are rejected — the hostname is resolved and every
resolved IP is checked, not just the literal.
"""
import ipaddress
import logging
import socket
from urllib.parse import urlparse

from app.config import settings

logger = logging.getLogger(__name__)


class UrlNotAllowed(ValueError):
    """The URL is not allowed to be used as a user-supplied endpoint."""


def _validate(url: str) -> str:
    if not url or not url.strip():
        raise UrlNotAllowed("URL не указан")
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UrlNotAllowed("Поддерживаются только http:// и https://")
    host = parsed.hostname
    if not host:
        raise UrlNotAllowed("Не удалось разобрать URL")

    if settings.allow_private_endpoints:
        # dev / owner mode: anything goes (localhost ComfyUI/LM Studio work)
        return url

    # literal IP — check directly
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is not None:
        if _is_blocked(ip):
            raise UrlNotAllowed(
                f"Адрес {host} запрещён: приватные, локальные и служебные сети недоступны на публичном сервере"
            )
        return url

    # hostname — resolve and check EVERY returned address
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as e:
        raise UrlNotAllowed(f"Не удалось разрешить хост {host}: {e}")
    for info in infos:
        try:
            rip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _is_blocked(rip):
            raise UrlNotAllowed(
                f"Хост {host} указывает на запрещённую сеть ({rip})"
            )
    return url


def _is_blocked(ip) -> bool:
    return (
        ip.is_loopback            # 127/8, ::1
        or ip.is_private          # 10/8, 172.16/12, 192.168/16, fc00::/7
        or ip.is_link_local       # 169.254/16 (cloud metadata!), fe80::/10
        or ip.is_unspecified      # 0.0.0.0, ::
        or ip.is_multicast
        or ip.is_reserved
    )


def validate_url(url: str) -> str:
    return _validate(url)
