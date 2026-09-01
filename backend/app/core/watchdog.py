"""Startup watchdog: recover landings orphaned by a server restart.

If the backend dies mid-generation, the landing stays in status "generating"
forever — the frontend spinner never ends. At startup no generation threads
exist yet, so any landing still marked "generating" is orphaned by definition.
"""
import logging

from app.models.schemas import LandingStatus
from app.storage.local import list_landings, update_landing_status

logger = logging.getLogger(__name__)

ORPHAN_MESSAGE = "Генерация прервана перезапуском сервера. Запустите генерацию заново."


def mark_orphaned_generations() -> int:
    """Mark all landings stuck in 'generating' as failed. Returns count fixed."""
    items, _total = list_landings(page=1, page_size=10_000)
    fixed = 0
    for meta in items:
        if meta.status == LandingStatus.generating:
            update_landing_status(meta.id, LandingStatus.error, error_message=ORPHAN_MESSAGE)
            fixed += 1
            logger.warning("Orphaned generation detected: %s (%s) — marked as error", meta.id, meta.title)
    return fixed
