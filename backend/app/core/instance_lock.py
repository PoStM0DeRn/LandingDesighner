import logging
import os
import platform
import socket

from app.config import settings

logger = logging.getLogger(__name__)

_lock_socket: socket.socket | None = None


def acquire_instance_lock() -> socket.socket | None:
    """Bind an exclusive lock socket so a second backend instance fails loudly.

    On Windows two processes can silently bind the same service port
    (SO_REUSEADDR), producing phantom duplicate servers with unpredictable
    connection routing. A dedicated lock port with SO_EXCLUSIVEADDRUSE makes
    any second startup fail immediately with a clear error.

    Set LG_INSTANCE_GUARD=0 to disable (used by tests).
    """
    if os.environ.get("LG_INSTANCE_GUARD") == "0":
        return None
    global _lock_socket
    if _lock_socket is not None:
        # idempotent: repeated startup in the same process reuses the lock
        return _lock_socket

    port = settings.instance_lock_port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if platform.system() == "Windows":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(("127.0.0.1", port))
        s.listen(1)
    except OSError as e:
        s.close()
        raise RuntimeError(
            f"Instance lock port {port} is already taken - another backend instance "
            f"is running. Stop it first (stop-backend.ps1) instead of starting a duplicate."
        ) from e
    _lock_socket = s
    logger.info("Instance lock acquired on 127.0.0.1:%d", port)
    return s
