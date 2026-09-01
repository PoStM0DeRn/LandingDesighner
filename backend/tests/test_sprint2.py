from fastapi.testclient import TestClient

from app.core import progress as progress_tracker
from app.main import app

client = TestClient(app)


def _tiny_png_b64() -> str:
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class TestThumbnailFallback:
    def test_hero_extraction_webp(self, clean_storage):
        from app.engine.thumbnails import _extract_hero_image
        from app.storage.local import create_landing, get_html_path, get_thumbnail_path, save_html

        create_landing("thumb1", "T", "D", "P", [])
        save_html("thumb1", f'<html><body><img src="data:image/webp;base64,{_tiny_png_b64()}" alt="x"></body></html>')
        assert _extract_hero_image(get_html_path("thumb1")) is True
        p = get_thumbnail_path("thumb1")
        assert p is not None and p.name == "thumbnail.webp"

    def test_hero_extraction_no_images(self, clean_storage):
        from app.engine.thumbnails import _extract_hero_image
        from app.storage.local import create_landing, get_html_path, save_html

        create_landing("thumb2", "T", "D", "P", [])
        save_html("thumb2", "<html><body><p>no images here</p></body></html>")
        assert _extract_hero_image(get_html_path("thumb2")) is False

    def test_generate_thumbnail_falls_back_to_hero(self, clean_storage, monkeypatch):
        from app.engine import thumbnails
        from app.storage.local import create_landing, get_meta, save_html

        monkeypatch.setattr(thumbnails, "_screenshot", lambda hp: False)
        create_landing("thumb3", "T", "D", "P", [])
        save_html("thumb3", f'<img src="data:image/png;base64,{_tiny_png_b64()}">')

        assert thumbnails.generate_thumbnail("thumb3") is True
        meta = get_meta("thumb3")
        assert meta.thumbnail_url == "/api/landings/thumb3/thumbnail"

    def test_stale_variants_cleared(self, clean_storage, monkeypatch):
        import base64
        from pathlib import Path

        from app.engine import thumbnails
        from app.storage.local import create_landing, get_html_path, save_html

        monkeypatch.setattr(thumbnails, "_screenshot", lambda hp: False)
        create_landing("thumb4", "T", "D", "P", [])
        save_html("thumb4", f'<img src="data:image/webp;base64,{_tiny_png_b64()}">')
        hp = get_html_path("thumb4")
        (hp.parent / "thumbnail.png").write_bytes(b"stale")  # stale png

        assert thumbnails.generate_thumbnail("thumb4") is True
        assert not (hp.parent / "thumbnail.png").exists() or Path(hp.parent / "thumbnail.png").read_bytes() != b"stale"
        assert (hp.parent / "thumbnail.webp").exists()


class TestBackfill:
    def test_spawns_threads_with_inflight_guard(self, clean_storage, monkeypatch):
        import time

        from app.engine import thumbnails
        from app.storage.local import create_landing

        calls = []

        def fake_gen(lid):
            calls.append(lid)
            time.sleep(0.3)  # slow enough to stay in-flight during the second call
            return True

        monkeypatch.setattr(thumbnails, "generate_thumbnail", fake_gen)

        create_landing("b1", "T", "D", "P", [])
        create_landing("b2", "T", "D", "P", [])

        thumbnails.backfill_missing_thumbnails(["b1", "b2"])
        thumbnails.backfill_missing_thumbnails(["b1", "b2"])  # still in-flight — no duplicates
        time.sleep(1.0)

        assert sorted(calls) == ["b1", "b2"]


class TestProgress:
    def test_lifecycle(self):
        progress_tracker.start("t1")
        p = progress_tracker.get("t1")
        assert p is not None and p["stage"] == "queued"

        progress_tracker.update("t1", stage="generate_images", images_total=5, images_done=2, message="x")
        p = progress_tracker.get("t1")
        assert p["stage"] == "generate_images"
        assert p["message"] == "x"
        assert p["images_done"] == 2 and p["images_total"] == 5

        # notice survives stage changes
        progress_tracker.update("t1", notice="ComfyUI недоступен", stage="assemble")
        p = progress_tracker.get("t1")
        assert p["notice"] == "ComfyUI недоступен"
        assert p["message"] == "Сборка HTML"

        progress_tracker.finish("t1", "ready")
        p = progress_tracker.get("t1")
        assert p["done"] is True and p["status"] == "ready" and p["stage"] == "done"

        progress_tracker.pop("t1")
        assert progress_tracker.get("t1") is None

    def test_unknown_id_is_safe(self):
        progress_tracker.update("ghost", stage="assemble")
        assert progress_tracker.get("ghost") is None
        progress_tracker.finish("ghost", "ready")
        progress_tracker.pop("ghost")


class TestStatePersistence:
    def test_roundtrip(self, clean_storage):
        from app.storage.local import get_state, save_state

        save_state("abc", {"title": "T", "sections": [{"type": "hero", "title": "H"}]})
        state = get_state("abc")
        assert state["title"] == "T"
        assert state["sections"][0]["type"] == "hero"

    def test_missing_state(self, clean_storage):
        from app.storage.local import get_state
        assert get_state("nope") is None


class TestSprint2Endpoints:
    def _headers(self) -> dict:
        from app.auth import create_session
        return {"Authorization": f"Bearer {create_session('tester')}"}

    def test_regenerate_404_without_state(self, clean_storage):
        h = self._headers()
        r = client.post("/api/landings/nope/regenerate-image", json={"section_type": "hero"}, headers=h)
        assert r.status_code == 404
        r = client.post("/api/landings/nope/regenerate-section", json={"section_type": "hero"}, headers=h)
        assert r.status_code == 404

    def test_regenerate_requires_auth(self, clean_storage):
        assert client.post("/api/landings/whatever/regenerate-image", json={"section_type": "hero"}).status_code == 401
        assert client.post("/api/landings/whatever/regenerate-section", json={"section_type": "hero"}).status_code == 401

    def test_regenerate_section_missing_type(self, clean_storage):
        from app.storage.local import create_landing, save_state

        create_landing("abc", "T", "D", "P", [], owner_nickname="tester")
        save_state("abc", {"title": "T", "sections": [{"type": "hero", "title": "H"}]})
        r = client.post("/api/landings/abc/regenerate-section", json={"section_type": "pricing"}, headers=self._headers())
        assert r.status_code == 404

    def test_regenerate_image_missing_type(self, clean_storage):
        from app.storage.local import create_landing, save_state

        create_landing("abc", "T", "D", "P", [], owner_nickname="tester")
        save_state("abc", {"title": "T", "sections": [{"type": "hero", "title": "H"}]})
        r = client.post("/api/landings/abc/regenerate-image", json={"section_type": "faq"}, headers=self._headers())
        assert r.status_code == 404

    def test_regenerate_section_success(self, clean_storage, monkeypatch):
        from app.models.schemas import Section, SectionType
        from app.storage.local import create_landing, get_state, save_state

        def fake_regen(intent, section_type, skills=None):
            return Section(type=SectionType(section_type), title="New title", description="New text")

        monkeypatch.setattr("app.api.routes.landings.regenerate_section_content", fake_regen)

        create_landing("abc", "T", "D", "P", [], owner_nickname="tester")
        save_state("abc", {
            "title": "T",
            "intent": {"topic": "T"},
            "sections": [{"type": "hero", "title": "H"}],
            "tokens": {},
            "skills": [],
        })
        r = client.post("/api/landings/abc/regenerate-section", json={"section_type": "hero"}, headers=self._headers())
        assert r.status_code == 200
        assert r.json()["ok"] is True

        state = get_state("abc")
        assert state["sections"][0]["title"] == "New title"

    def test_thumbnail_404_when_missing(self, clean_storage):
        from app.storage.local import create_landing

        create_landing("abc", "T", "D", "P", [])
        assert client.get("/api/landings/abc/thumbnail").status_code == 404

    def test_sections_summary_shape(self, clean_storage):
        from app.storage.local import create_landing, save_state

        create_landing("abc", "T", "D", "P", [], owner_nickname="tester")
        save_state("abc", {
            "title": "T",
            "sections": [
                {"type": "hero", "title": "H", "image_requests": [{"prompt": "x"}]},
                {"type": "cta", "title": "C"},
            ],
        })
        data = client.get("/api/landings/abc/sections", headers=self._headers()).json()
        assert len(data) == 2
        assert data[0]["type"] == "hero" and data[0]["has_image"] is True
        assert data[1]["type"] == "cta" and data[1]["has_image"] is False
