"""Compiles Tailwind CSS for a generated landing, replacing the Play CDN.

The generated HTML uses Tailwind utility classes with an inline CDN script.
When node/npm is available we compile a real, minimal styles.css so the
delivered ZIP is production-ready and works offline.
"""
import json
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.config import settings
from app.models.schemas import DesignTokens
from app.storage.local import get_landing_dir

logger = logging.getLogger(__name__)

TAILWIND_VERSION = "tailwindcss@3.4"

CDN_SCRIPT_RE = re.compile(r'<script src="https://cdn\.tailwindcss\.com"></script>', re.IGNORECASE)
CONFIG_SCRIPT_RE = re.compile(r"<script>\s*tailwind\.config\s*=.*?</script>", re.DOTALL)

_npm_checked = False
_npm_available = False


def _npx_path() -> str | None:
    return shutil.which("npx.cmd") or shutil.which("npx")


def is_npm_available() -> bool:
    global _npm_checked, _npm_available
    if not _npm_checked:
        _npm_checked = True
        _npm_available = _npx_path() is not None
    return _npm_available


def generate_config(tokens: DesignTokens, surface_alt: str) -> tuple[str, str]:
    config = {
        "content": ["./index.html"],
        "theme": {
            "extend": {
                "colors": {
                    "primary": tokens.primary_color,
                    "secondary": tokens.secondary_color,
                    "accent": tokens.accent_color,
                    "surface": tokens.bg_color,
                    "surface-alt": surface_alt,
                },
                "fontFamily": {
                    "heading": [tokens.heading_font, "sans-serif"],
                    "body": [tokens.body_font, "sans-serif"],
                },
                "borderRadius": {
                    "DEFAULT": tokens.border_radius,
                },
            },
        },
    }
    config_js = "module.exports = " + json.dumps(config, indent=2) + "\n"
    input_css = "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n"
    return config_js, input_css


def patch_html(html: str) -> str:
    """Replace CDN script + inline config with a link to the compiled stylesheet."""
    html = CDN_SCRIPT_RE.sub('<link rel="stylesheet" href="styles.css">', html)
    html = CONFIG_SCRIPT_RE.sub("", html)
    return html


def _run_tailwind(cwd: Path, timeout: int = 180) -> bool:
    npx = _npx_path()
    if not npx:
        return False
    # --yes: never block on npx's "Ok to proceed?" install prompt.
    # DEVNULL pipes: if we have to kill the process tree, no grandchild can hold
    # pipe handles open and hang the wait (classic Windows subprocess trap).
    cmd = [
        npx, "--yes", TAILWIND_VERSION,
        "-c", "tailwind.config.js", "-i", "input.css", "-o", "styles.css", "--minify",
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except OSError as e:
        logger.warning("Tailwind build could not start: %s", e)
        return False
    try:
        rc = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning("Tailwind build timed out after %ss — killing process tree", timeout)
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        return False
    if rc != 0:
        logger.warning("Tailwind build exited with code %s", rc)
        return False
    return (cwd / "styles.css").exists()


def build_tailwind_css(landing_id: str, html: str, tokens: DesignTokens, surface_alt: str) -> tuple[str, bool]:
    """Compile styles.css for the landing. Returns (patched_html, ok).

    On any failure the original CDN-based HTML is returned unchanged.
    """
    if not settings.tailwind_build_enabled:
        return html, False
    if not is_npm_available():
        logger.info("npx not available — keeping Tailwind CDN for %s", landing_id)
        return html, False

    d = get_landing_dir(landing_id)
    config_js, input_css = generate_config(tokens, surface_alt)
    (d / "tailwind.config.js").write_text(config_js, encoding="utf-8")
    (d / "input.css").write_text(input_css, encoding="utf-8")
    # Tailwind scans index.html for used utilities — write the original (CDN) markup
    # before compiling; the caller saves the patched version afterwards.
    (d / "index.html").write_text(html, encoding="utf-8")

    if not _run_tailwind(d):
        logger.warning("Tailwind build failed for %s — keeping CDN version", landing_id)
        return html, False

    logger.info("Tailwind CSS compiled for %s (%d bytes)", landing_id, (d / "styles.css").stat().st_size)
    return patch_html(html), True


def prewarm() -> None:
    """Run one dummy build at startup to warm the npm cache."""
    if not settings.tailwind_build_enabled or not is_npm_available():
        return
    try:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "index.html").write_text('<html><body class="p-4 text-primary"></body></html>', encoding="utf-8")
            (d / "tailwind.config.js").write_text(
                'module.exports = { content: ["./index.html"], theme: { extend: { colors: { primary: "#6366f1" } } } }',
                encoding="utf-8",
            )
            (d / "input.css").write_text("@tailwind base;\n@tailwind components;\n@tailwind utilities;\n", encoding="utf-8")
            if _run_tailwind(d, timeout=300):
                logger.info("Tailwind prewarm complete — npm cache warm")
            else:
                logger.warning("Tailwind prewarm build failed")
    except Exception as e:
        logger.warning("Tailwind prewarm error: %s", e)
