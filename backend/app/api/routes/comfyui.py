from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.url_guard import validate_url, UrlNotAllowed
from app.mcp.comfyui_api import ComfyUIClient

router = APIRouter(prefix="/api/comfyui", tags=["comfyui"])


class ComfyCheckRequest(BaseModel):
    url: str


@router.post("/check")
async def check(body: ComfyCheckRequest):
    """Ping a visitor-supplied ComfyUI and list its checkpoints."""
    try:
        url = validate_url(body.url)
    except UrlNotAllowed as e:
        raise HTTPException(status_code=400, detail=f"ComfyUI URL: {e}")

    client = ComfyUIClient(base_url=url)
    try:
        ok = await client.is_available()
    except Exception:
        ok = False

    if not ok:
        return {
            "ok": False,
            "error": "ComfyUI недоступен с сервера. Проверь, что он запущен и открыт извне "
                     "(проброс порта, cloudflared tunnel, Tailscale Funnel).",
        }
    try:
        checkpoints = await client.list_checkpoints()
    except Exception:
        checkpoints = []
    return {"ok": True, "checkpoints": checkpoints}
