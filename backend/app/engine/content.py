import json
import logging
import re

from app.core.llm import chat_completion, chat_json
from app.engine.sanitize import sanitize_html
from app.models.schemas import DesignTokens, ImageRequest, Intent, Section, SectionType, Skill

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a content generator for landing pages. Given the intent, generate rich content for each section.

Return JSON with "sections" array. Each section has:
- type: section type (hero, features, about, services, testimonials, pricing, faq, cta, footer)
- title: section heading (string)
- subtitle: sub-heading if applicable (string)
- description: main text content (string)
- items: for features/services/testimonials/pricing - array of objects with title, description, icon (emoji), and optionally price/button_text
- button_text: CTA button text (string)
- button_url: "#" (string)
- image_requests: array of image generation requests (see below)

IMAGE GENERATION RULES:
For sections that need images, add "image_requests" array. Each entry:
{
  "section_type": "hero|features|about|testimonials",
  "section_index": 0,
  "prompt": "detailed English description of the image to generate",
  "width": 1024,
  "height": 576,
  "style": "photo|illustration|3d_render|watercolor|digital_art",
  "seed": -1
}

DO NOT include "steps" or "cfg_scale" — they are model-specific and configured elsewhere.

WHO NEEDS IMAGES:
- hero: 1 image, background banner. width=1024, height=576. style=photo or illustration.
- features: 1 image per feature card. width=768, height=512. style=illustration or 3d_render.
- about: 1 image. width=1024, height=576.
- testimonials: 1 avatar per testimonial item. width=256, height=256. style=photo.

RESOLUTION RULE: width and height MUST be multiples of 64 (e.g. 1024x576, 768x512, 256x256).

WHO DOES NOT NEED IMAGES:
- faq, cta, footer, pricing: do NOT add image_requests.

PROMPT RULES:
- Write prompts in ENGLISH regardless of content language.
- Be specific and descriptive: "modern office workspace with natural lighting, minimalist design, people collaborating"
- For avatars: "professional headshot portrait of a [gender] in their 30s, neutral background"
- Set seed=-1 for random generation.
- Write compelling, concise copy in the SAME LANGUAGE as the original prompt.
- For hero: strong headline, brief subtitle.
- For features: 3-6 items with emoji icons.
Return ONLY valid JSON."""


def _build_system_prompt(skills: list[Skill] | None) -> str:
    extra = ""
    if skills:
        extra = "\n\nAdditional instructions from selected skills:\n" + "\n".join(f"- {s.prompt_addition}" for s in skills)
    return SYSTEM_PROMPT + extra


SECTION_REGENERATE_PROMPT = """You regenerate ONE section of an existing landing page.

Return JSON with a single "section" object:
- type: section type (must match the requested type)
- title: section heading (string)
- subtitle: sub-heading if applicable (string)
- description: main text content (string)
- items: for features/services/testimonials/pricing - array of objects with title, description, icon (emoji), and optionally price/button_text
- button_text: CTA button text (string)
- button_url: "#" (string)

Content should be in the SAME LANGUAGE as the topic.
Write compelling, concise copy. Use short paragraphs.
Return ONLY valid JSON."""


def _build_regen_prompt(skills: list[Skill] | None) -> str:
    extra = ""
    if skills:
        extra = "\n\nAdditional instructions from selected skills:\n" + "\n".join(f"- {s.prompt_addition}" for s in skills)
    return SECTION_REGENERATE_PROMPT + extra


def regenerate_section_content(
    intent: Intent,
    section_type: str,
    provider: str = "local",
    model: str | None = None,
    api_endpoint: str | None = None,
    api_key: str | None = None,
    skills: list[Skill] | None = None,
) -> Section:
    """Regenerate content for a single section (used by the regenerate API)."""
    messages = [
        {"role": "system", "content": _build_regen_prompt(skills)},
        {"role": "user", "content": f"""
Topic: {intent.topic}
Style: {intent.style}
Tone: {intent.tone}
Target audience: {intent.target_audience}
Keywords: {', '.join(intent.keywords)}
Section to generate: {section_type}
"""},
    ]
    data = chat_json(
        messages, temperature=0.8,
        provider=provider, model=model, api_endpoint=api_endpoint, api_key=api_key,
    )
    s = data.get("section") if isinstance(data, dict) else None
    if not isinstance(s, dict):
        s = data if isinstance(data, dict) else {}
    try:
        st = SectionType(s.get("type", section_type))
    except ValueError:
        st = SectionType(section_type)
    return Section(
        type=st,
        title=s.get("title") or "",
        subtitle=s.get("subtitle") or "",
        description=s.get("description") or "",
        items=s.get("items") or [],
        button_text=s.get("button_text") or "",
        button_url=s.get("button_url") or "#",
    )
def _parse_image_requests(raw_requests: list[dict] | None, section_type: str, section_index: int) -> list[ImageRequest]:
    if not raw_requests:
        return []
    result = []
    for req in raw_requests:
        try:
            result.append(ImageRequest(
                section_type=req.get("section_type", section_type),
                section_index=req.get("section_index", section_index),
                prompt=req.get("prompt", ""),
                width=req.get("width", 1024),
                height=req.get("height", 1024),
                style=req.get("style", "photo"),
                seed=req.get("seed", -1),
            ))
        except Exception as e:
            logger.warning("Failed to parse image request: %s", e)
    return result


def generate_content(
    intent: Intent,
    provider: str = "local",
    model: str | None = None,
    api_endpoint: str | None = None,
    api_key: str | None = None,
    skills: list[Skill] | None = None,
) -> list[Section]:
    section_types = [s.value for s in intent.sections]
    messages = [
        {"role": "system", "content": _build_system_prompt(skills)},
        {"role": "user", "content": f"""
Topic: {intent.topic}
Style: {intent.style}
Tone: {intent.tone}
Target audience: {intent.target_audience}
Keywords: {', '.join(intent.keywords)}
Sections needed: {', '.join(section_types)}
"""},
    ]
    data = chat_json(
        messages, temperature=0.7,
        provider=provider, model=model, api_endpoint=api_endpoint, api_key=api_key,
    )
    try:
        sections_data = data.get("sections", [])
        sections = []
        for i, s in enumerate(sections_data):
            sec_type = s.get("type", "hero")
            try:
                st = SectionType(sec_type)
            except ValueError:
                st = SectionType.hero
            image_requests = _parse_image_requests(s.get("image_requests"), sec_type, i)
            sections.append(Section(
                type=st,
                title=s.get("title") or "",
                subtitle=s.get("subtitle") or "",
                description=s.get("description") or "",
                items=s.get("items") or [],
                button_text=s.get("button_text") or "",
                button_url=s.get("button_url") or "#",
                image_requests=image_requests,
            ))
        total_images = sum(len(s.image_requests) for s in sections)
        if total_images:
            logger.info("LLM requested %d images across %d sections", total_images, len(sections))
        return sections
    except Exception as e:
        logger.warning("Failed to generate content: %s", e)
        return [
            Section(type=SectionType.hero, title=intent.topic, description=intent.topic),
            Section(type=SectionType.features, title="Features", items=[
                {"title": "Quality", "description": "High quality solution", "icon": "✨"},
                {"title": "Speed", "description": "Fast delivery", "icon": "⚡"},
                {"title": "Support", "description": "24/7 support", "icon": "💬"},
            ]),
            Section(type=SectionType.cta, title="Get Started", button_text="Contact Us"),
            Section(type=SectionType.footer, title="Footer"),
        ]


SECTION_MARKUP_PROMPT = """You are an expert landing page designer. Write ONE landing page section as raw HTML using ONLY Tailwind CSS utility classes.

STRICT RULES:
- Output ONLY the <section>...</section> HTML fragment. No markdown fences, no explanations, no <html>/<head>/<body>.
- Design tokens are available as Tailwind classes: bg-primary, text-primary, bg-secondary, text-secondary, bg-accent, text-accent, bg-surface, bg-surface-alt, font-heading, font-body, rounded (border radius). Arbitrary values like bg-[#0f172a] are allowed.
- Do NOT use style="" attributes. Do NOT use <script>, <style>, <iframe>, or any event handlers.
- Do NOT invent image URLs. If the section content provides an "image" placeholder __IMAGE__, you MUST include it as an <img src="__IMAGE__"> (for hero backgrounds use class="absolute inset-0 w-full h-full object-cover"). For item images use src="__ITEM_IMAGE_0__", "__ITEM_IMAGE_1__" and so on. If a placeholder is not provided for an item, use gradients or icon shapes instead of external images.
- Keep it accessible: meaningful alt attributes, aria-labels on icon-only buttons.
- Make the design polished: proper spacing (py-16/20/24, max-w-*, px-6), responsive grids (grid-cols-1 sm:grid-cols-2 lg:grid-cols-3), hover states (hover:...), transitions.
- Text content must be taken from the provided section JSON. Do not invent new copy beyond tiny UI labels.
Return ONLY the raw HTML fragment."""


def _build_markup_prompt(skills: list[Skill] | None) -> str:
    extra = ""
    if skills:
        extra = "\n\nAdditional instructions from selected skills:\n" + "\n".join(f"- {s.prompt_addition}" for s in skills)
    return SECTION_MARKUP_PROMPT + extra


def generate_section_markup(
    section: Section,
    tokens: DesignTokens,
    intent: Intent | None = None,
    provider: str = "local",
    model: str | None = None,
    api_endpoint: str | None = None,
    api_key: str | None = None,
    skills: list[Skill] | None = None,
) -> str | None:
    """LLM writes one section as raw Tailwind HTML.

    Returns sanitized, placeholder-substituted markup or None (caller falls
    back to the built-in section renderer).
    """
    items_payload = []
    for i, item in enumerate(section.items):
        payload = {}
        for k, v in item.items():
            if k == "image_url":
                payload[k] = f"__ITEM_IMAGE_{i}__" if v else None
            else:
                payload[k] = v
        items_payload.append(payload)

    section_payload = {
        "type": section.type.value,
        "title": section.title,
        "subtitle": section.subtitle,
        "description": section.description,
        "button_text": section.button_text,
        "button_url": section.button_url,
        "image": "__IMAGE__" if section.image_url else None,
        "items": items_payload,
    }
    design_payload = {
        "colors": {
            "primary": tokens.primary_color,
            "secondary": tokens.secondary_color,
            "accent": tokens.accent_color,
            "surface": tokens.bg_color,
        },
        "fonts": {"heading": tokens.heading_font, "body": tokens.body_font},
        "border_radius": tokens.border_radius,
        "semantic_classes": [
            "bg-primary", "text-primary", "bg-secondary", "text-secondary",
            "bg-accent", "text-accent", "bg-surface", "bg-surface-alt",
            "font-heading", "font-body", "rounded",
        ],
    }
    context = {"topic": intent.topic, "style": intent.style, "tone": intent.tone} if intent else {}

    messages = [
        {"role": "system", "content": _build_markup_prompt(skills)},
        {"role": "user", "content": json.dumps(
            {"context": context, "design": design_payload, "section": section_payload},
            ensure_ascii=False,
        )},
    ]
    raw = chat_completion(
        messages, temperature=0.4,
        provider=provider, model=model, api_endpoint=api_endpoint, api_key=api_key,
    )
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    if "<section" not in raw.lower() or len(raw) > 100_000:
        logger.warning("LLM markup rejected for section %s (no <section> or too long)", section.type.value)
        return None

    cleaned = sanitize_html(raw)
    if len(cleaned) < 50:
        logger.warning("LLM markup empty after sanitizing for section %s", section.type.value)
        return None

    # Substitute image placeholders with the real (possibly base64) URLs
    cleaned = cleaned.replace("__IMAGE__", section.image_url)
    for i, item in enumerate(section.items):
        cleaned = cleaned.replace(f"__ITEM_IMAGE_{i}__", str(item.get("image_url", "")))
    return cleaned
