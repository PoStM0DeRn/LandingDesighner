import base64
import io

from PIL import Image

from app.engine.image_generator import _to_webp_data_uri, ensure_image_requests
from app.models.schemas import ImageRequest, Section, SectionType


def _png_b64(mode: str = "RGB", size: tuple = (64, 64)) -> str:
    img = Image.new(mode, size, (180, 60, 60))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def test_converts_png_to_webp():
    uri = _to_webp_data_uri(_png_b64())
    assert uri.startswith("data:image/webp;base64,")
    raw = base64.b64decode(uri.split(",", 1)[1])
    with Image.open(io.BytesIO(raw)) as img:
        assert img.format == "WEBP"


def test_rgba_input_handled():
    uri = _to_webp_data_uri(_png_b64(mode="RGBA"))
    assert uri.startswith("data:image/webp;base64,")


def test_fallback_on_garbage():
    uri = _to_webp_data_uri("!!!garbage-not-base64!!!")
    assert uri.startswith("data:image/png;base64,")


def test_webp_is_smaller_than_png():
    png_b64 = _png_b64(size=(256, 256))
    webp_len = len(_to_webp_data_uri(png_b64).split(",", 1)[1])
    assert webp_len < len(png_b64)


class TestEnsureImageRequests:
    def test_synthesizes_hero_request_when_llm_skipped(self):
        sections = [Section(type=SectionType.hero, title="Eco Bottle")]
        ensure_image_requests(sections, "eco bottle brand")
        assert len(sections[0].image_requests) == 1
        req = sections[0].image_requests[0]
        assert req.width == 1024 and req.height == 576
        assert "Eco Bottle" in req.prompt

    def test_synthesizes_about_request(self):
        sections = [Section(type=SectionType.about, title="Our story")]
        ensure_image_requests(sections, "topic")
        assert sections[0].image_requests[0].section_type == "about"

    def test_skips_when_llm_already_requested(self):
        existing = ImageRequest(section_type="hero", prompt="custom art", width=512, height=512)
        sections = [Section(type=SectionType.hero, title="T", image_requests=[existing])]
        ensure_image_requests(sections, "topic")
        assert len(sections[0].image_requests) == 1
        assert sections[0].image_requests[0].prompt == "custom art"

    def test_ignores_sections_without_images(self):
        sections = [Section(type=SectionType.cta, title="Go")]
        ensure_image_requests(sections, "topic")
        assert sections[0].image_requests == []
