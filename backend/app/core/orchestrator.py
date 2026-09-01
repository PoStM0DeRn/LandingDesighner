import logging
import threading
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.core import progress as progress_tracker
from app.core.gpu_lock import generation_slot
from app.engine.nlp_parser import parse_intent
from app.engine.content import generate_content, generate_section_markup
from app.engine.design import generate_design
from app.engine.image_generator import generate_images_sync
from app.engine.assembler import assemble_html
from app.engine.validator import validate_html
from app.models.schemas import (
    DesignTokens,
    Intent,
    LandingStatus,
    Section,
    Skill,
)
from app.storage.local import (
    save_html,
    save_state,
    update_landing_status,
)

logger = logging.getLogger(__name__)


def _persist_state(state: LandingState, title: str) -> None:
    """Store intent/sections/tokens/skills so sections and images can be regenerated later."""
    sections_data = []
    for s in state.get("sections") or []:
        d = s.model_dump()
        d["image_url"] = ""  # base64 blobs live in the assembled HTML only
        for item in d.get("items", []):
            item.pop("image_url", None)
        sections_data.append(d)
    save_state(state["landing_id"], {
        "title": title,
        "provider": state.get("provider"),
        "model": state.get("model"),
        "use_llm_markup": state.get("use_llm_markup", False),
        "intent": state["intent"].model_dump() if state.get("intent") else None,
        "sections": sections_data,
        "tokens": state["design_tokens"].model_dump() if state.get("design_tokens") else None,
        "skills": [s.model_dump() for s in state.get("skills", [])],
        "comfyui_workflow_path": state.get("comfyui_workflow_path"),
        "image_steps": state.get("image_steps", settings.image_default_steps),
    })


class LandingState(TypedDict):
    landing_id: str
    prompt: str
    title: str
    tags: list[str]
    brandbook_colors: dict | None

    provider: str
    model: str
    api_endpoint: str | None
    api_key: str | None
    skills: list[Skill]

    comfyui_workflow_path: str | None
    image_steps: int
    use_llm_markup: bool

    intent: Intent | None
    sections: list[Section] | None
    sections_markup: list[str | None] | None
    design_tokens: DesignTokens | None
    html: str | None
    status: str
    error: str | None


def node_parse_intent(state: LandingState) -> dict:
    if state.get("error"):
        return {}
    progress_tracker.update(state["landing_id"], stage="parse_intent")
    try:
        intent = parse_intent(
            state["prompt"],
            provider=state["provider"],
            model=state["model"],
            api_endpoint=state.get("api_endpoint"),
            api_key=state.get("api_key"),
            skills=state.get("skills", []),
        )
        logger.info("Parsed intent for %s: topic=%s style=%s", state["landing_id"], intent.topic, intent.style)
        return {"intent": intent}
    except Exception as e:
        logger.error("NLP parser failed for %s: %s", state["landing_id"], e)
        return {"error": str(e), "status": "error"}


def node_generate_content(state: LandingState) -> dict:
    if state.get("error"):
        return {}
    progress_tracker.update(state["landing_id"], stage="generate_content")
    intent = state["intent"]
    try:
        sections = generate_content(
            intent,
            provider=state["provider"],
            model=state["model"],
            api_endpoint=state.get("api_endpoint"),
            api_key=state.get("api_key"),
            skills=state.get("skills", []),
        )
        logger.info("Generated %d sections for %s", len(sections), state["landing_id"])
        return {"sections": sections}
    except Exception as e:
        logger.error("Content engine failed for %s: %s", state["landing_id"], e)
        return {"error": str(e), "status": "error"}


def node_generate_design(state: LandingState) -> dict:
    if state.get("error"):
        return {}
    progress_tracker.update(state["landing_id"], stage="generate_design")
    intent = state["intent"]
    try:
        tokens = generate_design(
            intent,
            state.get("brandbook_colors"),
            provider=state["provider"],
            model=state["model"],
            api_endpoint=state.get("api_endpoint"),
            api_key=state.get("api_key"),
            skills=state.get("skills", []),
        )
        logger.info("Generated design tokens for %s", state["landing_id"])
        return {"design_tokens": tokens}
    except Exception as e:
        logger.error("Design engine failed for %s: %s", state["landing_id"], e)
        return {"error": str(e), "status": "error"}


def node_generate_images(state: LandingState) -> dict:
    if state.get("error"):
        return {}
    try:
        sections = state["sections"]
        if not sections:
            return {"error": "No sections to generate images for", "status": "error"}
        total_requests = sum(len(s.image_requests) for s in sections)
        if total_requests == 0:
            logger.info("No image requests for %s, skipping", state["landing_id"])
            return {}
        logger.info("Generating %d images for %s via ComfyUI", total_requests, state["landing_id"])
        workflow_path = state.get("comfyui_workflow_path")
        image_steps = state.get("image_steps", 20)
        sections = generate_images_sync(
            sections, workflow_path=workflow_path, steps=image_steps, landing_id=state["landing_id"],
        )
        return {"sections": sections}
    except Exception as e:
        logger.error("Image generation failed for %s: %s", state["landing_id"], e)
        return {}


def node_generate_markup(state: LandingState) -> dict:
    if state.get("error") or not state.get("use_llm_markup"):
        return {}
    sections = state["sections"]
    tokens = state["design_tokens"]
    if not sections or tokens is None:
        return {}
    progress_tracker.update(state["landing_id"], stage="generate_markup")
    markup: list[str | None] = []
    total = len(sections)
    for idx, section in enumerate(sections):
        progress_tracker.update(state["landing_id"], message=f"Разметка секций {idx + 1}/{total}")
        try:
            html = generate_section_markup(
                section, tokens, state.get("intent"),
                provider=state["provider"],
                model=state["model"],
                api_endpoint=state.get("api_endpoint"),
                api_key=state.get("api_key"),
                skills=state.get("skills", []),
            )
        except Exception as e:
            logger.warning("LLM markup failed for %s[%s]: %s", state["landing_id"], section.type.value, e)
            html = None
        markup.append(html)
    generated = sum(1 for m in markup if m)
    logger.info("LLM markup generated for %d/%d sections (%s)", generated, total, state["landing_id"])
    return {"sections_markup": markup}


def node_assemble(state: LandingState) -> dict:
    if state.get("error"):
        return {}
    progress_tracker.update(state["landing_id"], stage="assemble")
    try:
        title = state["title"] or (state["intent"].topic if state.get("intent") else state["prompt"][:50])
        html = assemble_html(
            title, state["sections"], state["design_tokens"],
            sections_html=state.get("sections_markup"),
        )
        # Replace Tailwind CDN with a compiled stylesheet when tooling allows
        if state.get("design_tokens") is not None:
            try:
                from app.engine.tailwind_builder import build_tailwind_css
                from app.engine.assembler import compute_surface_alt

                html, _ = build_tailwind_css(
                    state["landing_id"],
                    html,
                    state["design_tokens"],
                    compute_surface_alt(state["design_tokens"].bg_color),
                )
            except Exception as e:
                logger.warning("Tailwind build step failed for %s: %s", state["landing_id"], e)
        validation = validate_html(html, state["sections"])
        if not validation.valid:
            logger.warning("Validation failed for %s: %s", state["landing_id"], validation.errors)
            return {"error": f"Validation: {'; '.join(validation.errors)}", "status": "error"}
        if validation.warnings:
            logger.info("Validation warnings for %s: %s", state["landing_id"], validation.warnings)
        save_html(state["landing_id"], html)
        try:
            _persist_state(state, title)
        except Exception as e:
            logger.warning("State persistence failed for %s: %s", state["landing_id"], e)
        logger.info("Assembled HTML for %s (%d bytes)", state["landing_id"], len(html))
        return {"html": html, "status": "ready"}
    except Exception as e:
        logger.error("Assembler failed for %s: %s", state["landing_id"], e)
        return {"error": str(e), "status": "error"}


def node_finalize(state: LandingState) -> dict:
    landing_id = state["landing_id"]
    if state.get("error"):
        update_landing_status(landing_id, LandingStatus.error, error_message=str(state["error"]))
        progress_tracker.finish(landing_id, "error", error=str(state["error"]))
        logger.error("Generation failed for %s: %s", landing_id, state["error"])
    else:
        update_landing_status(landing_id, LandingStatus.ready)
        progress_tracker.finish(landing_id, "ready")
        logger.info("Generation complete for %s", landing_id)
        threading.Thread(target=_make_thumbnail, args=(landing_id,), daemon=True).start()
    return {}


def _make_thumbnail(landing_id: str) -> None:
    try:
        from app.engine.thumbnails import generate_thumbnail
        generate_thumbnail(landing_id)
    except Exception as e:
        logger.warning("Thumbnail task failed for %s: %s", landing_id, e)


def _should_continue(state: LandingState) -> str:
    if state.get("error"):
        return "finalize"
    return "continue"


graph = StateGraph(LandingState)

graph.add_node("parse_intent", node_parse_intent)
graph.add_node("generate_content", node_generate_content)
graph.add_node("generate_design", node_generate_design)
graph.add_node("generate_images", node_generate_images)
graph.add_node("generate_markup", node_generate_markup)
graph.add_node("assemble", node_assemble)
graph.add_node("finalize", node_finalize)

graph.add_conditional_edges(START, _should_continue, {"continue": "parse_intent", "finalize": "finalize"})
graph.add_conditional_edges("parse_intent", _should_continue, {"continue": "generate_content", "finalize": "finalize"})
graph.add_conditional_edges("generate_content", _should_continue, {"continue": "generate_design", "finalize": "finalize"})
graph.add_conditional_edges("generate_design", _should_continue, {"continue": "generate_images", "finalize": "finalize"})
graph.add_conditional_edges("generate_images", _should_continue, {"continue": "generate_markup", "finalize": "finalize"})
graph.add_conditional_edges("generate_markup", _should_continue, {"continue": "assemble", "finalize": "finalize"})
graph.add_conditional_edges("assemble", _should_continue, {"continue": "finalize", "finalize": "finalize"})
graph.add_edge("finalize", END)

workflow = graph.compile()


def run_generation(
    landing_id: str,
    prompt: str,
    title: str,
    tags: list[str],
    brandbook_colors: dict | None = None,
    provider: str = "local",
    model: str = "llama-3",
    api_endpoint: str | None = None,
    api_key: str | None = None,
    skills: list[Skill] | None = None,
    comfyui_workflow_path: str | None = None,
    image_steps: int = 20,
    use_llm_markup: bool = False,
) -> None:
    initial_state: LandingState = {
        "landing_id": landing_id,
        "prompt": prompt,
        "title": title,
        "tags": tags,
        "brandbook_colors": brandbook_colors,
        "provider": provider,
        "model": model,
        "api_endpoint": api_endpoint,
        "api_key": api_key,
        "skills": skills or [],
        "comfyui_workflow_path": comfyui_workflow_path,
        "image_steps": image_steps,
        "use_llm_markup": use_llm_markup,
        "intent": None,
        "sections": None,
        "sections_markup": None,
        "design_tokens": None,
        "html": None,
        "status": "generating",
        "error": None,
    }
    try:
        progress_tracker.start(landing_id)
        wait_started = time.time()
        with generation_slot(timeout=settings.generation_queue_timeout) as acquired:
            if not acquired:
                msg = f"GPU busy: queued longer than {settings.generation_queue_timeout}s, generation cancelled"
                logger.error("%s (landing %s)", msg, landing_id)
                update_landing_status(landing_id, LandingStatus.error, error_message=msg)
                progress_tracker.finish(landing_id, "error", error=msg)
                return
            waited = time.time() - wait_started
            if waited > 1:
                logger.warning("Landing %s waited %.0fs in GPU queue", landing_id, waited)
            workflow.invoke(initial_state)
    except Exception as e:
        logger.error("Orchestrator failed for %s: %s", landing_id, e)
        update_landing_status(landing_id, LandingStatus.error, error_message=str(e))
        progress_tracker.finish(landing_id, "error", error=str(e))
