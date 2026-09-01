import asyncio
import json
import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from app.auth import optional_user, require_user
from app.core import progress as progress_tracker
from app.engine.assembler import assemble_html
from app.engine.content import regenerate_section_content
from app.engine.image_generator import regenerate_single_image
from app.models.schemas import (
    DesignTokens,
    GenerationInfo,
    GenerationSkillInfo,
    ImageRequest,
    Intent,
    LandingMeta,
    LandingStatus,
    PaginatedResponse,
    PublishRequest,
    Section,
    Skill,
)
from app.storage.local import (
    delete_landing,
    download_zip,
    get_html,
    get_meta,
    get_state,
    get_thumbnail_path,
    list_landings,
    save_html,
    save_state,
    set_published,
    update_landing_meta,
)

router = APIRouter(prefix="/api/landings", tags=["landings"])


class UpdateLandingRequest(BaseModel):
    title: str | None = None
    tags: list[str] | None = None


class RegenerateImageBody(BaseModel):
    section_type: str
    item_index: int | None = None


class RegenerateSectionBody(BaseModel):
    section_type: str


def _ensure_can_modify(meta: LandingMeta, user: str) -> None:
    # ownerless (legacy) landings may be managed by any logged-in user
    if meta.owner_nickname and meta.owner_nickname != user:
        raise HTTPException(status_code=403, detail="Это работа другого автора")


def _ensure_viewable(meta: LandingMeta, user: str | None) -> None:
    # Drafts are visible to their owner only. 404 (not 403) — don't reveal existence.
    if meta.published is False and (user is None or meta.owner_nickname != user):
        raise HTTPException(status_code=404, detail="Landing not found")


def _load_meta_or_404(landing_id: str, user: str | None) -> LandingMeta:
    meta = get_meta(landing_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Landing not found")
    _ensure_viewable(meta, user)
    return meta


def _maybe_backfill(meta: LandingMeta, landing_id: str) -> None:
    if meta.status == LandingStatus.ready and not meta.thumbnail_url:
        from app.engine.thumbnails import backfill_missing_thumbnails
        backfill_missing_thumbnails([landing_id])


@router.get("", response_model=PaginatedResponse)
def list_all(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    search: str = Query(""),
    mine: bool = Query(False),
    user: str | None = Depends(optional_user),
):
    if mine and user is None:
        raise HTTPException(status_code=401, detail="Требуется вход")
    items, total = list_landings(page, page_size, search, owner_nickname=user if mine else None)
    # Auto-backfill thumbnails for ready landings that don't have one yet
    missing = [i.id for i in items if i.status == LandingStatus.ready and not i.thumbnail_url]
    if missing:
        from app.engine.thumbnails import backfill_missing_thumbnails
        backfill_missing_thumbnails(missing)
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=total // page_size + (1 if total % page_size else 0),
    )


@router.get("/{landing_id}", response_model=LandingMeta)
def get_one(landing_id: str, user: str | None = Depends(optional_user)):
    meta = _load_meta_or_404(landing_id, user)
    _maybe_backfill(meta, landing_id)
    return meta


@router.post("/{landing_id}/publish", response_model=LandingMeta)
def publish_one(landing_id: str, body: PublishRequest, user: str = Depends(require_user)):
    meta = get_meta(landing_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Landing not found")
    _ensure_can_modify(meta, user)
    meta = set_published(landing_id, body.published)
    if meta is None:
        raise HTTPException(status_code=404, detail="Landing not found")
    return meta


@router.put("/{landing_id}", response_model=LandingMeta)
def update_one(landing_id: str, body: UpdateLandingRequest, user: str = Depends(require_user)):
    meta = get_meta(landing_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Landing not found")
    _ensure_can_modify(meta, user)
    meta = update_landing_meta(landing_id, title=body.title, tags=body.tags)
    if meta is None:
        raise HTTPException(status_code=404, detail="Landing not found")
    return meta


@router.delete("/{landing_id}", status_code=204)
def delete_one(landing_id: str, user: str = Depends(require_user)):
    meta = get_meta(landing_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Landing not found")
    _ensure_can_modify(meta, user)
    if not delete_landing(landing_id):
        raise HTTPException(status_code=404, detail="Landing not found")


@router.get("/{landing_id}/html")
def get_html_content(landing_id: str, user: str | None = Depends(optional_user)):
    _load_meta_or_404(landing_id, user)
    html = get_html(landing_id)
    if html is None:
        raise HTTPException(status_code=404, detail="HTML not found")
    return HTMLResponse(content=html)


@router.get("/{landing_id}/css")
def get_css_content(landing_id: str, user: str | None = Depends(optional_user)):
    from app.config import settings
    from pathlib import Path

    _load_meta_or_404(landing_id, user)
    p = Path(settings.storage_dir) / "landings" / landing_id / "styles.css"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Compiled CSS not found (CDN fallback)")
    return FileResponse(p, media_type="text/css")


@router.get("/{landing_id}/download")
def download(landing_id: str, user: str | None = Depends(optional_user)):
    _load_meta_or_404(landing_id, user)
    buf = download_zip(landing_id)
    if buf is None:
        raise HTTPException(status_code=404, detail="Landing not found")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={landing_id}.zip"},
    )


# ---------------------------------------------------------------------------
# Progress (SSE)
# ---------------------------------------------------------------------------

@router.get("/{landing_id}/events")
async def progress_events(landing_id: str, user: str | None = Depends(optional_user)):
    _load_meta_or_404(landing_id, user)

    async def event_stream():
        last_sent = None
        while True:
            meta = get_meta(landing_id)
            if meta is None:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                return
            payload = {
                "status": meta.status.value,
                "progress": progress_tracker.get(landing_id) or {},
            }
            data = json.dumps(payload, ensure_ascii=False)
            if data != last_sent:
                yield f"data: {data}\n\n"
                last_sent = data
            if meta.status.value != "generating":
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Thumbnail
# ---------------------------------------------------------------------------

@router.get("/{landing_id}/thumbnail")
def thumbnail(landing_id: str, user: str | None = Depends(optional_user)):
    _load_meta_or_404(landing_id, user)
    p = get_thumbnail_path(landing_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    mime = {".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg"}.get(p.suffix, "image/png")
    return FileResponse(p, media_type=mime)


# ---------------------------------------------------------------------------
# Sections overview + regeneration
# ---------------------------------------------------------------------------

@router.get("/{landing_id}/generation", response_model=GenerationInfo)
def generation_info(landing_id: str, user: str | None = Depends(optional_user)):
    """Full generation details: model, prompt, skills with their full texts."""
    meta = _load_meta_or_404(landing_id, user)
    state = get_state(landing_id)
    if state is None:
        # old landing without persisted state — meta-level info only
        return GenerationInfo(
            available=False,
            provider=meta.provider,
            model=meta.model,
            prompt=meta.prompt,
        )
    try:
        skills = [GenerationSkillInfo(**s) for s in state.get("skills") or []]
    except Exception:
        skills = []
    return GenerationInfo(
        available=True,
        provider=state.get("provider") or meta.provider,
        model=state.get("model") or meta.model,
        prompt=meta.prompt,
        use_llm_markup=bool(state.get("use_llm_markup", False)),
        image_steps=state.get("image_steps"),
        comfyui_workflow_path=state.get("comfyui_workflow_path"),
        intent=state.get("intent"),
        tokens=state.get("tokens"),
        skills=skills,
    )


@router.get("/{landing_id}/sections")
def sections_summary(landing_id: str, user: str | None = Depends(optional_user)):
    _load_meta_or_404(landing_id, user)
    state = get_state(landing_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Landing state not found")
    result = []
    for i, s in enumerate(state.get("sections") or []):
        result.append({
            "index": i,
            "type": s.get("type"),
            "title": s.get("title"),
            "items": len(s.get("items") or []),
            "item_titles": [str(item.get("title") or f"#{n + 1}") for n, item in enumerate(s.get("items") or [])],
            "has_image": bool(s.get("image_requests")),
        })
    return result


def _load_sections(state: dict) -> list[Section]:
    return [Section(**s) for s in state.get("sections") or []]


def _reassemble(landing_id: str, state: dict) -> None:
    sections = _load_sections(state)
    tokens = DesignTokens(**(state.get("tokens") or {}))
    html = assemble_html(state.get("title") or "Landing", sections, tokens)
    save_html(landing_id, html)
    threading.Thread(
        target=_refresh_thumbnail, args=(landing_id,), daemon=True,
    ).start()


def _refresh_thumbnail(landing_id: str) -> None:
    try:
        from app.engine.thumbnails import generate_thumbnail
        generate_thumbnail(landing_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Thumbnail refresh failed for %s: %s", landing_id, e)


@router.post("/{landing_id}/regenerate-image")
def regenerate_image(
    landing_id: str,
    body: RegenerateImageBody,
    user: str = Depends(require_user),
):
    meta = _load_meta_or_404(landing_id, user)
    _ensure_can_modify(meta, user)
    state = get_state(landing_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Landing state not found")
    sections_data = state.get("sections") or []
    section = next((s for s in sections_data if s.get("type") == body.section_type), None)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")

    requests = section.get("image_requests") or []
    req: ImageRequest | None = None
    synthesized = False

    if body.item_index is None:
        if requests:
            req = ImageRequest(**requests[0])
        else:
            req = ImageRequest(
                section_type=body.section_type,
                prompt=f"{section.get('title', '')}. high quality, detailed, no text",
                width=1024, height=576, style="photo",
            )
            synthesized = True
    else:
        if body.item_index < len(requests):
            req = ImageRequest(**requests[body.item_index])
        else:
            items = section.get("items") or []
            item_title = items[body.item_index].get("title", "") if body.item_index < len(items) else ""
            req = ImageRequest(
                section_type=body.section_type,
                section_index=body.item_index,
                prompt=f"{item_title}. high quality, detailed, no text",
                width=768, height=512, style="illustration",
            )
            synthesized = True

    data_uri = regenerate_single_image(
        req,
        workflow_path=state.get("comfyui_workflow_path"),
        steps=state.get("image_steps"),
    )
    if data_uri is None:
        raise HTTPException(status_code=502, detail="ComfyUI unavailable or generation failed")

    if synthesized:
        requests.append(req.model_dump())
        section["image_requests"] = requests

    if body.item_index is None:
        section["image_url"] = data_uri
    else:
        items = section.get("items") or []
        if body.item_index < len(items):
            items[body.item_index]["image_url"] = data_uri
        else:
            section["image_url"] = data_uri

    save_state(landing_id, state)
    _reassemble(landing_id, state)
    return {"ok": True, "section_type": body.section_type, "item_index": body.item_index}


@router.post("/{landing_id}/regenerate-section")
def regenerate_section(
    landing_id: str,
    body: RegenerateSectionBody,
    user: str = Depends(require_user),
):
    meta = _load_meta_or_404(landing_id, user)
    _ensure_can_modify(meta, user)
    state = get_state(landing_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Landing state not found")
    sections_data = state.get("sections") or []
    index = next((i for i, s in enumerate(sections_data) if s.get("type") == body.section_type), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Section not found")

    try:
        intent = Intent(**(state.get("intent") or {}))
        skills = [Skill(**s) for s in state.get("skills") or []]
        new_section = regenerate_section_content(intent, body.section_type, skills=skills)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM failed: {e}")

    old = sections_data[index]
    new_section.image_url = old.get("image_url", "")
    new_section.image_requests = [ImageRequest(**r) for r in old.get("image_requests") or []]
    sections_data[index] = new_section.model_dump()
    state["sections"] = sections_data

    save_state(landing_id, state)
    _reassemble(landing_id, state)
    return {"ok": True, "section": new_section.model_dump()}
