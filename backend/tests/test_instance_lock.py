import platform
import socket

from app.config import settings
from app.core import instance_lock
from app.core.instance_lock import acquire_instance_lock


def test_bypass_when_disabled(monkeypatch):
    monkeypatch.setenv("LG_INSTANCE_GUARD", "0")
    assert acquire_instance_lock() is None


def test_second_bind_fails(monkeypatch):
    monkeypatch.setenv("LG_INSTANCE_GUARD", "1")
    monkeypatch.setattr(settings, "instance_lock_port", 8799)
    s = acquire_instance_lock()
    assert s is not None
    try:
        # a second socket must not be able to bind the same lock port,
        # even with uvicorn-style reuse options
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if platform.system() == "Windows":
            s2.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            s2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s2.bind(("127.0.0.1", 8799))
        except OSError:
            pass
        else:
            raise AssertionError("second bind to lock port should fail")
        finally:
            s2.close()
        # idempotent: repeated startup in the same process reuses the lock
        assert acquire_instance_lock() is s
    finally:
        s.close()
        instance_lock._lock_socket = None


def test_lock_port_from_settings(monkeypatch):
    monkeypatch.setenv("LG_INSTANCE_GUARD", "1")
    monkeypatch.setattr(settings, "instance_lock_port", 8798)
    s = acquire_instance_lock()
    try:
        assert s is not None
        assert instance_lock._lock_socket is s
    finally:
        s.close()
        instance_lock._lock_socket = None
