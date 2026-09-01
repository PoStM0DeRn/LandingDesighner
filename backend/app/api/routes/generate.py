import json
import logging
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, UploadFile, File

from app.auth import require_user
from app.brandbook.parser import parse_brandbook
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
    image_steps: int = Form(20),
    use_llm_markup: str = Form("false"),
    brandbook: UploadFile | None = File(None),
):
    landing_id = uuid.uuid4().hex[:12]
    parsed_tags = json.loads(tags) if tags else []
    parsed_skill_ids = json.loads(skill_ids) if skill_ids else []
    display_title = title or prompt[:50]

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
            api_endpoint or None,
            api_key or None,
            skills,
            _validated_workflow_path(comfyui_workflow_path),
            image_steps,
            use_llm_markup.lower() in ("true", "1", "yes"),
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
