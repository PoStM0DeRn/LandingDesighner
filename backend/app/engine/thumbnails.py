import base64
import logging
import re
import threading
from pathlib import Path

from app.storage.local import get_html_path, get_meta, set_thumbnail_url

logger = logging.getLogger(__name__)

THUMB_FILES = ("thumbnail.png", "thumbnail.webp", "thumbnail.jpg")

_HERO_IMG_RE = re.compile(
    r'<img[^>]+src="data:image/(png|webp|jpeg|jpg);base64,([^"]+)"',
    re.IGNORECASE,
)
_EXT = {"png": "png", "webp": "webp", "jpeg": "jpg", "jpg": "jpg"}

_REMOTE_IMG_RE = re.compile(r'<img[^>]+src="(https?://[^"]+)"', re.IGNORECASE)

_backfill_inflight: set[str] = set()
_backfill_lock = threading.Lock()
_backfill_semaphore = threading.Semaphore(3)


def generate_thumbnail(landing_id: str) -> bool:
    """Thumbnail = headless screenshot; falls back to first embedded image."""
    meta = get_meta(landing_id)
    html_path = get_html_path(landing_id)
    if meta is None or html_path is None:
        return False

    for name in THUMB_FILES:  # clear stale variants before writing a fresh one
        (html_path.parent / name).unlink(missing_ok=True)

    if _screenshot(html_path):
        set_thumbnail_url(landing_id, f"/api/landings/{landing_id}/thumbnail")
        logger.info("Thumbnail (screenshot) for %s", landing_id)
        return True
    if _extract_hero_image(html_path):
        set_thumbnail_url(landing_id, f"/api/landings/{landing_id}/thumbnail")
        logger.info("Thumbnail (hero image) for %s", landing_id)
        return True
    logger.warning("No thumbnail for %s: screenshot and hero extraction both failed", landing_id)
    return False


def _screenshot(html_path: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright is not installed — screenshot skipped")
        return False
    try:
        out_path = html_path.parent / "thumbnail.png"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                # 'load' instead of 'networkidle': Tailwind CDN / Google Fonts keep
                # sockets open and networkidle never fires within the timeout.
                page.goto(html_path.as_uri(), wait_until="load", timeout=45000)
                page.wait_for_timeout(2500)  # let Tailwind JIT + fonts settle
                page.screenshot(path=str(out_path))
            finally:
                browser.close()
        return out_path.exists()
    except Exception as e:
        logger.warning("Screenshot failed for %s: %s", html_path.parent.name, e)
        return False


def _extract_hero_image(html_path: Path) -> bool:
    """Fallback: first embedded base64 image, or first remote image, becomes the thumbnail."""
    try:
        html = html_path.read_text(encoding="utf-8")
    except Exception:
        return False

    m = _HERO_IMG_RE.search(html)
    if m:
        ext = _EXT.get(m.group(1).lower())
        if ext:
            try:
                raw = base64.b64decode(m.group(2))
            except Exception:
                raw = b""
            if len(raw) >= 100:
                (html_path.parent / f"thumbnail.{ext}").write_bytes(raw)
                return True

    # Last resort: download the first remote image (picsum/pravatar era landings)
    for m in _REMOTE_IMG_RE.finditer(html):
        url = m.group(1)
        try:
            import httpx

            r = httpx.get(url, timeout=10, follow_redirects=True)
            ctype = r.headers.get("content-type", "")
            if r.status_code == 200 and len(r.content) > 1000:
                ext = "png" if "png" in ctype else "webp" if "webp" in ctype else "jpg"
                (html_path.parent / f"thumbnail.{ext}").write_bytes(r.content)
                return True
        except Exception as e:
            logger.debug("Remote image fetch failed (%s): %s", url[:60], e)
            continue
    return False


def backfill_missing_thumbnails(landing_ids: list[str]) -> None:
    """Spawn bounded background thumbnail generation for landings without one."""
    targets: list[str] = []
    with _backfill_lock:
        for lid in landing_ids:
            if lid in _backfill_inflight:
                continue
            _backfill_inflight.add(lid)
            targets.append(lid)

    for lid in targets:
        def _run(landing_id: str = lid) -> None:
            with _backfill_semaphore:
                try:
                    generate_thumbnail(landing_id)
                except Exception as e:
                    logger.warning("Backfill thumbnail failed for %s: %s", landing_id, e)
                finally:
                    with _backfill_lock:
                        _backfill_inflight.discard(landing_id)
        threading.Thread(target=_run, daemon=True).start()
