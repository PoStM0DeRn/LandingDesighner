import asyncio
import json
import logging
import sys

from mcp.server.mcpserver import MCPServer
from mcp.types import TextContent

from app.mcp.comfyui_api import ComfyUIClient
from app.mcp.workflow import build_txt2img_workflow

logger = logging.getLogger(__name__)

server = MCPServer(name="comfyui")
comfyui = ComfyUIClient()


@server.tool()
async def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    style: str = "photo",
    steps: int = 20,
    seed: int = -1,
) -> str:
    """Generate an image using local ComfyUI (Stable Diffusion). Returns base64-encoded PNG image."""
    try:
        workflow = build_txt2img_workflow(
            prompt=prompt,
            width=width,
            height=height,
            steps=steps,
            seed=seed,
            style=style,
        )
        b64_image = await comfyui.generate(workflow)
        return json.dumps({
            "status": "success",
            "image_base64": b64_image,
            "format": "png",
            "width": width,
            "height": height,
        })
    except Exception as e:
        logger.error("Image generation failed: %s", e)
        return json.dumps({"status": "error", "error": str(e)})


@server.tool()
async def list_checkpoints() -> str:
    """List available Stable Diffusion model checkpoints in ComfyUI."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{comfyui.base_url}/object_info/CheckpointLoaderSimple")
            r.raise_for_status()
            data = r.json()
            ckpts = (
                data.get("CheckpointLoaderSimple", {})
                .get("input", {})
                .get("required", {})
                .get("ckpt_name", [[]])[0]
            )
            return json.dumps({"status": "success", "checkpoints": ckpts})
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


async def main():
    await server.run_stdio_async()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
