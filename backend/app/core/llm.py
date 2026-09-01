import json
import logging
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)


def _build_client(provider: str, api_endpoint: str | None, api_key: str | None) -> tuple[OpenAI, str]:
    if provider == "openai" and api_key:
        return OpenAI(api_key=api_key), _resolve_model(provider, None)
    endpoint = api_endpoint or settings.lm_studio_url
    return OpenAI(base_url=endpoint, api_key="lm-studio"), _resolve_model(provider, None)


def _resolve_model(provider: str, model: str | None) -> str:
    if model:
        return model
    if provider == "openai":
        return settings.openai_api_key and "gpt-4o" or "gpt-4o"
    return settings.lm_studio_model


def chat_completion(
    messages: list[dict],
    temperature: float = 0.7,
    json_mode: bool = False,
    provider: str = "local",
    model: str | None = None,
    api_endpoint: str | None = None,
    api_key: str | None = None,
) -> str:
    client, resolved_model = _build_client(provider, api_endpoint, api_key)
    if model:
        resolved_model = model

    kwargs = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode and provider == "openai":
        kwargs["response_format"] = {"type": "json_object"}
    if json_mode and provider == "local":
        messages = list(messages)
        messages.append({
            "role": "system",
            "content": "Return ONLY valid JSON. No markdown, no explanation, no extra text.",
        })
        kwargs["messages"] = messages

    try:
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""
    except Exception as e:
        if provider == "local":
            logger.warning("Local LLM failed (%s): %s, trying cloud fallback", resolved_model, e)
            cloud_key = api_key or settings.openai_api_key
            if not cloud_key or cloud_key.startswith("sk-..."):
                raise RuntimeError(f"Local LLM failed and no OpenAI key configured: {e}")
            cloud = OpenAI(api_key=cloud_key)
            kwargs["model"] = "gpt-4o"
            response = cloud.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        raise RuntimeError(f"OpenAI API failed ({resolved_model}): {e}")


def chat_json(
    messages: list[dict],
    temperature: float = 0.3,
    provider: str = "local",
    model: str | None = None,
    api_endpoint: str | None = None,
    api_key: str | None = None,
) -> dict:
    raw = chat_completion(
        messages, temperature=temperature, json_mode=True,
        provider=provider, model=model, api_endpoint=api_endpoint, api_key=api_key,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        raise
