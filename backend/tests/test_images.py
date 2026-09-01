import base64
import io

from PIL import Image

from app.engine.image_generator import (
    MAX_REQUESTS_PER_SECTION,
    _to_webp_data_uri,
    apply_fallback_images,
    ensure_image_requests,
)
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


class TestEnsureTopUp:
    def test_features_top_up_to_item_count(self):
        section = Section(
            type=SectionType.features, title="F",
            items=[{"title": "A"}, {"title": "B"}, {"title": "C"}],
            image_requests=[ImageRequest(section_type="features", prompt="x", width=768, height=512)],
        )
        ensure_image_requests([section], "gym club")
        assert len(section.image_requests) == 3
        assert section.image_requests[1].section_index == 1
        assert section.image_requests[2].section_index == 2
        assert section.image_requests[1].width == 768 and section.image_requests[1].height == 512
        assert "B" in section.image_requests[1].prompt

    def test_testimonials_top_up_headshots(self):
        section = Section(
            type=SectionType.testimonials, title="T",
            items=[{"title": "Ann"}, {"title": "Bob"}, {"title": "Cara"}],
        )
        ensure_image_requests([section], "topic")
        assert len(section.image_requests) == 3
        assert all(r.width == 256 and r.height == 256 for r in section.image_requests)
        assert all(r.style == "photo" for r in section.image_requests)

    def test_cap_limits_total(self):
        items = [{"title": f"card {i}"} for i in range(10)]
        section = Section(type=SectionType.features, title="F", items=items)
        ensure_image_requests([section], "topic")
        assert len(section.image_requests) == MAX_REQUESTS_PER_SECTION

    def test_existing_full_coverage_not_touched(self):
        reqs = [ImageRequest(section_type="features", prompt=f"p{i}", width=768, height=512) for i in range(3)]
        section = Section(
            type=SectionType.features, title="F",
            items=[{"title": "A"}, {"title": "B"}, {"title": "C"}],
            image_requests=list(reqs),
        )
        ensure_image_requests([section], "topic")
        assert section.image_requests == reqs


class TestCardFallback:
    def test_features_items_get_stock_when_missing(self):
        section = Section(type=SectionType.features, title="F", items=[{"title": "A"}, {"title": "B"}])
        apply_fallback_images([section])
        for item in section.items:
            assert item["image_url"].startswith("https://picsum")

    def test_real_images_not_overwritten(self):
        section = Section(type=SectionType.features, title="F", items=[
            {"title": "A", "image_url": "data:image/webp;base64,REAL"},
            {"title": "B"},
        ])
        apply_fallback_images([section])
        assert section.items[0]["image_url"].startswith("data:image")
        assert section.items[1]["image_url"].startswith("https://picsum")

    def test_services_items_get_stock(self):
        section = Section(type=SectionType.services, title="S", items=[{"title": "X"}])
        apply_fallback_images([section])
        assert section.items[0]["image_url"].startswith("https://picsum")
