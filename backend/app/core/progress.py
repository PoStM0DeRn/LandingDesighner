"""In-memory generation progress shared between pipeline threads and SSE."""
import threading
import time

_lock = threading.Lock()
_state: dict[str, dict] = {}

STAGE_LABELS = {
    "queued": "В очереди",
    "parse_intent": "Анализ промпта",
    "generate_content": "Генерация контента",
    "generate_design": "Подбор дизайна",
    "generate_images": "Генерация изображений",
    "generate_markup": "Генерация разметки",
    "assemble": "Сборка HTML",
    "finalize": "Финализация",
}


def start(landing_id: str) -> None:
    with _lock:
        _state[landing_id] = {
            "stage": "queued",
            "message": "В очереди",
            "images_done": 0,
            "images_total": 0,
            "started": time.time(),
        }


def update(
    landing_id: str,
    stage: str | None = None,
    message: str | None = None,
    images_done: int | None = None,
    images_total: int | None = None,
) -> None:
    with _lock:
        p = _state.get(landing_id)
        if p is None:
            return
        if stage is not None:
            p["stage"] = stage
            p["message"] = STAGE_LABELS.get(stage, stage)
        if message is not None:
            p["message"] = message
        if images_done is not None:
            p["images_done"] = images_done
        if images_total is not None:
            p["images_total"] = images_total


def finish(landing_id: str, status: str, error: str | None = None) -> None:
    with _lock:
        p = _state.get(landing_id)
        if p is None:
            return
        p["done"] = True
        p["status"] = status
        p["error"] = error
        p["stage"] = "done"


def get(landing_id: str) -> dict | None:
    with _lock:
        p = _state.get(landing_id)
        return dict(p) if p else None


def pop(landing_id: str) -> None:
    with _lock:
        _state.pop(landing_id, None)
