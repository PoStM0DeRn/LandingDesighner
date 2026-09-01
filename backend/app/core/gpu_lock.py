"""Global GPU serialization.

On a single V100 the text LLM (LM Studio) and ComfyUI share the same 16 GB of
VRAM. Running a landing generation pipeline and an image generation at the
same time causes OOM / extreme slowdowns, so only one generation pipeline may
run at any given moment. Everything else waits in the queue.
"""
import threading
from contextlib import contextmanager

_generation_lock = threading.Lock()


@contextmanager
def generation_slot(timeout: float | None = None):
    """Acquire the exclusive generation slot.

    Yields True if the slot was acquired, False on timeout. Release happens
    automatically when the context exits.
    """
    acquired = _generation_lock.acquire(timeout=timeout) if timeout is not None else _generation_lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            _generation_lock.release()
