import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api", tags=["models"])


class ModelInfo(BaseModel):
    id: str
    name: str


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    active_model: str


@router.get("/models")
async def list_models(url: str = ""):
    endpoint = (url or settings.lm_studio_url).rstrip("/")
    models_url = f"{endpoint}/models"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(models_url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"Cannot connect to LM Studio at {models_url}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"LM Studio returned {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    raw_models = data.get("data", [])
    models = []
    for m in raw_models:
        mid = m.get("id", "")
        models.append(ModelInfo(id=mid, name=mid))

    return ModelsResponse(
        models=models,
        active_model=settings.lm_studio_model,
    )
