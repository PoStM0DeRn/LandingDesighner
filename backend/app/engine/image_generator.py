import asyncio
import base64
import io
import logging
import random
from typing import TYPE_CHECKING

from app.config import settings
from app.core import progress as progress_tracker
from app.engine.images import get_hero_image, get_testimonial_avatar
from app.models.schemas import ImageRequest, Section, SectionType

if TYPE_CHECKING:
    from app.mcp.client import MCPClient

logger = logging.getLogger(__name__)


def _to_webp_data_uri(b64_png: str) -> str:
    """Convert base64 PNG to WebP data URI (much smaller HTML). Falls back to PNG."""
    try:
        from PIL import Image

        raw = base64.b64decode(b64_png)
        with Image.open(io.BytesIO(raw)) as img:
            img = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=settings.image_webp_quality, method=4)
        return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        logger.warning("WebP optimization failed, keeping original PNG: %s", e)
        return "data:image/png;base64," + b64_png


STYLE_PREFIXES = {
    "photo": "professional photography, sharp focus, high resolution, ",
    "illustration": "digital illustration, vibrant colors, clean lines, ",
    "3d_render": "3D render, octane render, realistic lighting, ",
    "watercolor": "watercolor painting, soft edges, artistic, ",
    "oil_painting": "oil painting, classical art, rich textures, ",
    "digital_art": "digital art, concept art, artstation, ",
}


def build_image_prompt(request: ImageRequest) -> str:
    prefix = STYLE_PREFIXES.get(request.style, "")
    return prefix + request.prompt


def collect_image_requests(sections: list[Section]) -> list[tuple[int, int, ImageRequest]]:
    requests = []
    for s_idx, section in enumerate(sections):
        for i_idx, req in enumerate(section.image_requests):
            requests.append((s_idx, i_idx, req))
    return requests


def apply_fallback_images(sections: list[Section]) -> None:
    for section in sections:
        if section.type == SectionType.hero and not section.image_url:
            section.image_url = get_hero_image(section.title or "abstract")
        if section.type == SectionType.testimonials:
            for item in section.items:
                if not item.get("image_url"):
                    name = item.get("title", "")
                    if name:
                        item["image_url"] = get_testimonial_avatar(name)


def ensure_image_requests(sections: list[Section], topic: str) -> None:
    """LLMs sometimes skip image_requests entirely. Guarantee coverage for
    hero/about by synthesizing requests from section content when missing."""
    for section in sections:
        if not section.image_requests and not section.image_url:
            if section.type == SectionType.hero:
                section.image_requests.append(ImageRequest(
                    section_type="hero",
                    prompt=f"{topic}. {section.title}. high quality, detailed, no text",
                    width=1024, height=576, style="photo", seed=-1,
                ))
            elif section.type == SectionType.about:
                section.image_requests.append(ImageRequest(
                    section_type="about",
                    prompt=f"{topic}. {section.title or section.description[:80]}. high quality, detailed, no text",
                    width=1024, height=576, style="photo", seed=-1,
                ))


async def generate_images_async(
    sections: list[Section],
    mcp_client: MCPClient | None = None,
    workflow_path: str | None = None,
) -> list[Section]:
    if not settings.image_generation_enabled:
        logger.info("Image generation disabled, using fallback URLs")
        apply_fallback_images(sections)
        return sections

    topic = next((s.title for s in sections if s.type == SectionType.hero), "") or "abstract background"
    ensure_image_requests(sections, topic)
    requests = collect_image_requests(sections)
    if not requests:
        apply_fallback_images(sections)
        return sections

    if mcp_client is None:
        try:
            from app.mcp.client import get_mcp_client
            mcp_client = await get_mcp_client()
        except Exception as e:
            logger.warning("Cannot connect to MCP client: %s, using fallback", e)
            apply_fallback_images(sections)
            return sections

    logger.info("Generating %d images via MCP/ComfyUI", len(requests))

    for s_idx, i_idx, req in requests:
        if req.seed < 0:
            req.seed = random.randint(0, 2**32 - 1)

        full_prompt = build_image_prompt(req)
        logger.info("Generating image: section=%s prompt=%.60s... %dx%d",
                     req.section_type, full_prompt, req.width, req.height)

        b64 = await mcp_client.generate_image(
            prompt=full_prompt,
            width=req.width,
            height=req.height,
            style=req.style,
            steps=settings.image_default_steps,
            seed=req.seed,
        )

        if b64:
            data_uri = _to_webp_data_uri(b64)
            section = sections[s_idx]
            if req.section_type in ("hero", "about") or i_idx == 0 and not section.image_url:
                section.image_url = data_uri
            if section.items and i_idx < len(section.items):
                section.items[i_idx]["image_url"] = data_uri
            logger.info("Image generated for section %s[%d]", req.section_type, i_idx)
        else:
            logger.warning("Image generation failed for section %s[%d], using fallback", req.section_type, i_idx)

    apply_fallback_images(sections)
    return sections


def generate_images_sync(
    sections: list[Section],
    workflow_path: str | None = None,
    steps: int | None = None,
    landing_id: str | None = None,
) -> list[Section]:
    steps_value = steps if steps is not None else settings.image_default_steps
    if not settings.image_generation_enabled:
        apply_fallback_images(sections)
        return sections

    topic = next((s.title for s in sections if s.type == SectionType.hero), "") or "abstract background"
    ensure_image_requests(sections, topic)
    requests = collect_image_requests(sections)
    if not requests:
        apply_fallback_images(sections)
        return sections

    if landing_id:
        progress_tracker.update(landing_id, stage="generate_images", images_total=len(requests), images_done=0)

    try:
        from app.mcp.comfyui_api import ComfyUIClient
        from app.mcp.workflow import build_txt2img_workflow

        client = ComfyUIClient()

        if not client.is_available_sync():
            logger.warning("ComfyUI not available, using fallback images")
            apply_fallback_images(sections)
            return sections

        for done, (s_idx, i_idx, req) in enumerate(requests, start=1):
            if landing_id:
                progress_tracker.update(landing_id, images_done=done, message=f"Изображение {done}/{len(requests)}")
            if req.seed < 0:
                req.seed = random.randint(0, 2**32 - 1)

            full_prompt = build_image_prompt(req)
            workflow = build_txt2img_workflow(
                prompt=full_prompt,
                width=req.width,
                height=req.height,
                steps=steps_value,
                seed=req.seed,
                style=req.style,
                workflow_path=workflow_path,
            )

            try:
                b64 = client.generate_sync(workflow)
                if b64:
                    data_uri = _to_webp_data_uri(b64)
                    section = sections[s_idx]
                    if req.section_type in ("hero", "about") or (i_idx == 0 and not section.image_url):
                        section.image_url = data_uri
                    if section.items and i_idx < len(section.items):
                        section.items[i_idx]["image_url"] = data_uri
                    logger.info("Generated image for %s[%d]", req.section_type, i_idx)
            except Exception as e:
                logger.warning("Failed to generate image for %s[%d]: %s", req.section_type, i_idx, e)

    except Exception as e:
        logger.warning("ComfyUI client init failed: %s, using fallback", e)

    apply_fallback_images(sections)
    return sections


def regenerate_single_image(
    req: ImageRequest,
    workflow_path: str | None = None,
    steps: int | None = None,
) -> str | None:
    """Regenerate one image request and return a WebP data URI (None on failure)."""
    try:
        from app.mcp.comfyui_api import ComfyUIClient
        from app.mcp.workflow import build_txt2img_workflow

        client = ComfyUIClient()
        if not client.is_available_sync():
            logger.warning("ComfyUI not available, cannot regenerate image")
            return None

        if req.seed < 0:
            req.seed = random.randint(0, 2**32 - 1)
        else:
            req.seed = random.randint(0, 2**32 - 1)  # new variation on every regenerate

        workflow = build_txt2img_workflow(
            prompt=build_image_prompt(req),
            width=req.width,
            height=req.height,
            steps=steps if steps is not None else settings.image_default_steps,
            seed=req.seed,
            style=req.style,
            workflow_path=workflow_path,
        )
        b64 = client.generate_sync(workflow)
        return _to_webp_data_uri(b64) if b64 else None
    except Exception as e:
        logger.warning("regenerate_single_image failed: %s", e)
        return None
