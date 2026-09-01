import asyncio
import base64
import json
import logging
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class ComfyUIClient:
    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        self.base_url = (base_url or settings.comfyui_url).rstrip("/")
        self.timeout = timeout or settings.comfyui_timeout

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/system_stats")
                return r.status_code == 200
        except Exception:
            return False

    def is_available_sync(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                r = client.get(f"{self.base_url}/system_stats")
                return r.status_code == 200
        except Exception:
            return False

    async def queue_prompt(self, workflow: dict) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            payload = {"prompt": workflow}
            r = await client.post(f"{self.base_url}/prompt", json=payload)
            r.raise_for_status()
            data = r.json()
            prompt_id = data.get("prompt_id")
            if not prompt_id:
                raise RuntimeError(f"No prompt_id in response: {data}")
            logger.info("Queued ComfyUI prompt: %s", prompt_id)
            return prompt_id

    async def wait_for_completion(self, prompt_id: str) -> dict:
        deadline = asyncio.get_event_loop().time() + self.timeout
        async with httpx.AsyncClient(timeout=10) as client:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await client.get(f"{self.base_url}/history/{prompt_id}")
                    if r.status_code == 200:
                        data = r.json()
                        if prompt_id in data:
                            entry = data[prompt_id]
                            status = entry.get("status", {})
                            if status.get("completed", False) or status.get("status_str") == "success":
                                return entry
                            if status.get("status_str") == "error":
                                raise RuntimeError(f"ComfyUI generation failed: {entry}")
                except httpx.ConnectError:
                    logger.warning("ComfyUI connection lost, retrying...")
                await asyncio.sleep(1)
        raise TimeoutError(f"ComfyUI generation timed out after {self.timeout}s")

    async def get_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{self.base_url}/view", params=params)
            r.raise_for_status()
            return r.content

    async def generate(self, workflow: dict) -> str:
        prompt_id = await self.queue_prompt(workflow)
        result = await self.wait_for_completion(prompt_id)
        images = result.get("outputs", {})
        for node_id, node_output in images.items():
            images_list = node_output.get("images", [])
            for img_info in images_list:
                img_bytes = await self.get_image(
                    img_info["filename"],
                    img_info.get("subfolder", ""),
                    img_info.get("type", "output"),
                )
                return base64.b64encode(img_bytes).decode("utf-8")
        raise RuntimeError("No images found in ComfyUI output")

    def generate_sync(self, workflow: dict) -> str:
        import httpx as sync_httpx
        with sync_httpx.Client(timeout=30) as client:
            r = client.post(f"{self.base_url}/prompt", json={"prompt": workflow})
            r.raise_for_status()
            prompt_id = r.json().get("prompt_id")
            if not prompt_id:
                raise RuntimeError(f"No prompt_id in response")

        import time
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                with sync_httpx.Client(timeout=10) as client:
                    r = client.get(f"{self.base_url}/history/{prompt_id}")
                    if r.status_code == 200:
                        data = r.json()
                        if prompt_id in data:
                            entry = data[prompt_id]
                            status = entry.get("status", {})
                            if status.get("completed", False) or status.get("status_str") == "success":
                                images = entry.get("outputs", {})
                                for node_id, node_output in images.items():
                                    for img_info in node_output.get("images", []):
                                        with sync_httpx.Client(timeout=30) as c:
                                            r2 = c.get(f"{self.base_url}/view", params={
                                                "filename": img_info["filename"],
                                                "subfolder": img_info.get("subfolder", ""),
                                                "type": img_info.get("type", "output"),
                                            })
                                            r2.raise_for_status()
                                            return base64.b64encode(r2.content).decode("utf-8")
                            if status.get("status_str") == "error":
                                raise RuntimeError(f"ComfyUI generation failed: {entry}")
            except sync_httpx.ConnectError:
                pass
            time.sleep(1)
        raise TimeoutError(f"ComfyUI generation timed out after {self.timeout}s")
