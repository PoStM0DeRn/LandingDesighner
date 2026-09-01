import logging
from app.core.llm import chat_json
from app.models.schemas import Intent, DesignTokens, Skill

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a design tokens generator for landing pages. Given the intent and optional brandbook colors, generate Tailwind-compatible design tokens.

Return JSON with:
- primary_color: hex color for primary buttons/accents
- secondary_color: hex color for secondary elements
- accent_color: hex color for highlights/links
- bg_color: page background color
- text_color: main text color
- heading_font: Google Font name for headings
- body_font: Google Font name for body text
- border_radius: CSS border-radius value (e.g. "0.75rem", "9999px")

Color rules:
- Ensure good contrast between text and background
- Use harmonious color combinations
- If brandbook colors are provided, use them
- Style guidance: minimalist=neutral, modern=bold, corporate=blue, creative=vibrant, playful=bright, luxury=dark+gold
Return ONLY valid JSON."""


def _build_system_prompt(skills: list[Skill] | None) -> str:
    extra = ""
    if skills:
        extra = "\n\nAdditional instructions from selected skills:\n" + "\n".join(f"- {s.prompt_addition}" for s in skills)
    return SYSTEM_PROMPT + extra


def generate_design(
    intent: Intent,
    brandbook_colors: dict | None = None,
    provider: str = "local",
    model: str | None = None,
    api_endpoint: str | None = None,
    api_key: str | None = None,
    skills: list[Skill] | None = None,
) -> DesignTokens:
    color_info = ""
    if brandbook_colors:
        color_info = f"\nBrandbook colors: {brandbook_colors}"

    messages = [
        {"role": "system", "content": _build_system_prompt(skills)},
        {"role": "user", "content": f"""
Topic: {intent.topic}
Style: {intent.style}
Tone: {intent.tone}
Color preferences: {', '.join(intent.color_preferences) if intent.color_preferences else 'none'}
{color_info}
"""},
    ]
    data = chat_json(
        messages, temperature=0.4,
        provider=provider, model=model, api_endpoint=api_endpoint, api_key=api_key,
    )
    try:
        return DesignTokens(**{k: v for k, v in data.items() if k in DesignTokens.model_fields})
    except Exception as e:
        logger.warning("Failed to generate design tokens: %s, using defaults", e)
        return DesignTokens()
