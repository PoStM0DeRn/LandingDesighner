import json
import logging
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import require_user
from app.brandbook.parser import parse_brandbook
from app.core.url_guard import validate_url, UrlNotAllowed
from app.core.orchestrator import run_generation
from app.models.schemas import GenerateResponse, LandingStatus
from app.storage.local import create_landing
from app.storage.skills import get_skills_by_ids

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["generate"])


def _validated_workflow_path(raw: str | None) -> str | None:
    """Restrict user-supplied workflow paths to the configured whitelist root."""
    if not raw:
        return None
    from pathlib import Path as _Path

    from app.config import settings

    try:
        resolved = _Path(raw).resolve()
        root = _Path(settings.comfyui_workflows_root).resolve()
    except OSError:
        return None
    if root not in resolved.parents and resolved != root:
        logger.warning("Workflow path outside whitelist rejected: %s", raw)
        return None
    return str(resolved)


MAX_WORKFLOW_BYTES = 1_000_000


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    user: str = Depends(require_user),
    prompt: str = Form(...),
    title: str = Form(""),
    tags: str = Form("[]"),
    provider: str = Form("local"),
    model: str = Form("llama-3"),
    api_endpoint: str = Form(""),
    api_key: str = Form(""),
    skill_ids: str = Form("[]"),
    comfyui_workflow_path: str = Form(""),
    comfyui_url: str = Form(""),
    image_steps: int = Form(20),
    use_llm_markup: str = Form("false"),
    brandbook: UploadFile | None = File(None),
    workflow: UploadFile | None = File(None),
):
    landing_id = uuid.uuid4().hex[:12]
    parsed_tags = json.loads(tags) if tags else []
    parsed_skill_ids = json.loads(skill_ids) if skill_ids else []
    display_title = title or prompt[:50]

    # --- user-supplied service URLs: SSRF guard ---------------------------
    try:
        comfy_url = validate_url(comfyui_url) if comfyui_url else None
    except UrlNotAllowed as e:
        raise HTTPException(status_code=400, detail=f"ComfyUI URL: {e}")
    try:
        llm_endpoint = validate_url(api_endpoint) if api_endpoint else None
    except UrlNotAllowed as e:
        raise HTTPException(status_code=400, detail=f"LM Studio URL: {e}")

    create_landing(
        landing_id=landing_id,
        title=display_title,
        description=prompt[:200],
        prompt=prompt,
        tags=parsed_tags,
        provider=provider,
        model=model,
        owner_nickname=user,
    )

    skills = get_skills_by_ids(parsed_skill_ids) if parsed_skill_ids else []

    # --- visitor-supplied workflow file (takes priority over the path) ----
    uploaded_workflow: str | None = None
    if workflow and workflow.filename:
        content = await workflow.read()
        if len(content) > MAX_WORKFLOW_BYTES:
            raise HTTPException(status_code=400, detail="Workflow слишком большой (максимум 1 МБ)")
        try:
            json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise HTTPException(status_code=400, detail=f"Workflow должен быть валидным JSON: {e}")
        from app.storage.local import get_landing_dir
        wf_path = get_landing_dir(landing_id) / "workflow.json"
        wf_path.write_bytes(content)
        uploaded_workflow = str(wf_path)
        logger.info("Uploaded workflow for %s (%d bytes)", landing_id, len(content))

    brandbook_colors = None
    if brandbook and brandbook.filename:
        try:
            suffix = Path(brandbook.filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await brandbook.read()
                tmp.write(content)
                tmp_path = tmp.name
            brandbook_colors = parse_brandbook(tmp_path)
            Path(tmp_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning("Failed to parse brandbook: %s", e)

    thread = threading.Thread(
        target=run_generation,
        args=(
            landing_id, prompt, display_title, parsed_tags, brandbook_colors,
            provider, model,
            llm_endpoint,
            api_key or None,
            skills,
            uploaded_workflow or _validated_workflow_path(comfyui_workflow_path),
            image_steps,
            use_llm_markup.lower() in ("true", "1", "yes"),
            comfy_url,
        ),
        daemon=True,
    )
    thread.start()

    skill_names = [s.name for s in skills]
    msg = f"Generation started with {provider} ({model})"
    if skill_names:
        msg += f" + skills: {', '.join(skill_names)}"

    return GenerateResponse(
        id=landing_id,
        status=LandingStatus.generating,
        message=msg,
    )
