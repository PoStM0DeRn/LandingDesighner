import logging
from app.core.llm import chat_json
from app.models.schemas import Intent, Skill

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an NLP parser. Analyze the user's prompt and extract landing page intent.
Return JSON with these fields:
- topic: main topic of the landing page (string)
- style: visual style (one of: minimalist, modern, corporate, creative, playful, luxury)
- tone: communication tone (one of: professional, friendly, bold, elegant, casual)
- target_audience: who is the target audience (string)
- keywords: relevant keywords (list of strings)
- color_preferences: any color preferences mentioned (list of strings, hex or names)
- sections: which sections to include (list from: hero, features, about, services, testimonials, pricing, faq, cta, footer)

Always include hero, cta, and footer by default. Only include other sections if the prompt suggests them.
Return ONLY valid JSON, no extra text."""


def _build_system_prompt(skills: list[Skill] | None) -> str:
    extra = ""
    if skills:
        extra = "\n\nAdditional instructions from selected skills:\n" + "\n".join(f"- {s.prompt_addition}" for s in skills)
    return SYSTEM_PROMPT + extra


def parse_intent(
    prompt: str,
    provider: str = "local",
    model: str | None = None,
    api_endpoint: str | None = None,
    api_key: str | None = None,
    skills: list[Skill] | None = None,
) -> Intent:
    messages = [
        {"role": "system", "content": _build_system_prompt(skills)},
        {"role": "user", "content": prompt},
    ]
    data = chat_json(
        messages, temperature=0.3,
        provider=provider, model=model, api_endpoint=api_endpoint, api_key=api_key,
    )
    try:
        return Intent(**data)
    except Exception as e:
        logger.warning("Failed to parse intent: %s, using defaults", e)
        return Intent(topic=prompt[:100])
