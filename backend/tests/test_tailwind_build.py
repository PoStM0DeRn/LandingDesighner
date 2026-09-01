import json
from pathlib import Path

import pytest

from app.config import settings
from app.engine.assembler import compute_surface_alt
from app.engine.tailwind_builder import (
    build_tailwind_css,
    generate_config,
    is_npm_available,
    patch_html,
)
from app.models.schemas import DesignTokens

SAMPLE_CDN_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>T</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: { extend: { colors: { primary: '#6366f1' } } },
    }
  </script>
</head>
<body class="bg-surface text-primary"><h1 class="font-heading">Hello</h1></body>
</html>"""


class TestGenerateConfig:
    def test_config_from_tokens(self):
        tokens = DesignTokens(primary_color="#ff0000", heading_font="Roboto", border_radius="1rem")
        config_js, input_css = generate_config(tokens, "#f8f9fa")
        config = json.loads(config_js.replace("module.exports = ", ""))
        assert config["content"] == ["./index.html"]
        assert config["theme"]["extend"]["colors"]["primary"] == "#ff0000"
        assert config["theme"]["extend"]["colors"]["surface-alt"] == "#f8f9fa"
        assert config["theme"]["extend"]["fontFamily"]["heading"] == ["Roboto", "sans-serif"]
        assert config["theme"]["extend"]["borderRadius"]["DEFAULT"] == "1rem"
        assert "@tailwind utilities" in input_css


class TestPatchHtml:
    def test_replaces_cdn_with_link(self):
        patched = patch_html(SAMPLE_CDN_HTML)
        assert "cdn.tailwindcss.com" not in patched
        assert 'tailwind.config' not in patched
        assert '<link rel="stylesheet" href="styles.css">' in patched
        assert "font-heading" in patched  # content untouched

    def test_noop_without_cdn(self):
        html = "<html><body>x</body></html>"
        assert patch_html(html) == html


class TestSurfaceAlt:
    def test_light_bg(self):
        assert compute_surface_alt("#ffffff") == "#f8f9fa"

    def test_dark_bg(self):
        assert compute_surface_alt("#0f172a") == "#1a1a2e"


class TestBuildFallbacks:
    def test_disabled_flag(self, clean_storage, monkeypatch):
        monkeypatch.setattr(settings, "tailwind_build_enabled", False)
        html, ok = build_tailwind_css("x1", SAMPLE_CDN_HTML, DesignTokens(), "#f8f9fa")
        assert ok is False
        assert html == SAMPLE_CDN_HTML

    def test_npm_missing(self, clean_storage, monkeypatch):
        import app.engine.tailwind_builder as tb
        monkeypatch.setattr(tb, "is_npm_available", lambda: False)
        html, ok = build_tailwind_css("x2", SAMPLE_CDN_HTML, DesignTokens(), "#f8f9fa")
        assert ok is False
        assert html == SAMPLE_CDN_HTML

    def test_no_landing_dir_does_not_crash(self, clean_storage, monkeypatch):
        # landing id unknown -> dir is created; npx missing so graceful exit anyway
        import app.engine.tailwind_builder as tb
        monkeypatch.setattr(tb, "is_npm_available", lambda: False)
        html, ok = build_tailwind_css("ghost", SAMPLE_CDN_HTML, DesignTokens(), "#f8f9fa")
        assert ok is False


@pytest.mark.skipif(not is_npm_available(), reason="npx not installed")
class TestRealBuild:
    def test_full_build_produces_css_and_patches_html(self, clean_storage):
        import base64
        import re

        from PIL import Image
        import io

        from app.storage.local import create_landing, get_landing_dir, get_thumbnail_path

        # Build a realistic landing body with utilities + custom colors + an image
        buf = io.BytesIO()
        Image.new("RGB", (32, 32), (40, 90, 160)).save(buf, "PNG")
        img_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

        body = (
            '<section id="hero" class="relative min-h-[50vh] flex items-center bg-surface-alt">'
            f'<img src="{img_uri}" class="absolute inset-0 w-full h-full object-cover">'
            '<h1 class="font-heading text-4xl font-bold text-primary">Title</h1>'
            '<a class="rounded bg-primary px-6 py-3 text-white" href="#">Go</a></section>'
        )
        html = SAMPLE_CDN_HTML.replace('<h1 class="font-heading">Hello</h1>', body)

        create_landing("tw1", "T", "D", "P", [])
        patched, ok = build_tailwind_css("tw1", html, DesignTokens(), "#f8f9fa")
        assert ok is True

        d = get_landing_dir("tw1")
        css = (d / "styles.css").read_text(encoding="utf-8")
        assert ".bg-primary" in css
        assert ".font-heading" in css
        assert ".rounded" in css
        assert len(css) < 100_000  # minified, way smaller than the CDN bundle

        assert "cdn.tailwindcss.com" not in patched
        assert '<link rel="stylesheet" href="styles.css">' in patched
        assert "tailwind.config" not in patched
