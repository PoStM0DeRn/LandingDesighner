import asyncio
import json
import logging
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings

logger = logging.getLogger(__name__)

SERVER_SCRIPT = str(Path(__file__).parent / "server.py")


class MCPClient:
    def __init__(self):
        self._session: ClientSession | None = None
        self._read_stream = None
        self._write_stream = None
        self._transport_ctx = None
        self._session_ctx = None
        self._connected = False

    async def connect(self) -> bool:
        try:
            server_params = StdioServerParameters(
                command=sys.executable,
                args=[SERVER_SCRIPT],
                env=None,
            )
            self._transport_ctx = stdio_client(server_params)
            streams = await self._transport_ctx.__aenter__()
            self._read_stream, self._write_stream = streams
            self._session = ClientSession(self._read_stream, self._write_stream)
            self._session_ctx = self._session
            await self._session_ctx.__aenter__()
            await self._session.initialize()
            self._connected = True
            logger.info("MCP client connected to ComfyUI server")
            return True
        except Exception as e:
            logger.warning("Failed to connect MCP client: %s", e)
            self._connected = False
            return False

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        style: str = "photo",
        steps: int = 20,
        seed: int = -1,
    ) -> str | None:
        if not self._connected or not self._session:
            return None
        try:
            result = await self._session.call_tool("generate_image", {
                "prompt": prompt,
                "width": width,
                "height": height,
                "style": style,
                "steps": steps,
                "seed": seed,
            })
            if hasattr(result, "content") and result.content:
                for content in result.content:
                    if hasattr(content, "text"):
                        data = json.loads(content.text)
                        if data.get("status") == "success":
                            return data.get("image_base64")
                        else:
                            logger.warning("Image generation error: %s", data.get("error"))
                            return None
        except Exception as e:
            logger.warning("MCP generate_image failed: %s", e)
            return None
        return None

    async def list_checkpoints(self) -> list[str]:
        if not self._connected or not self._session:
            return []
        try:
            result = await self._session.call_tool("list_checkpoints", {})
            if hasattr(result, "content") and result.content:
                for content in result.content:
                    if hasattr(content, "text"):
                        data = json.loads(content.text)
                        if data.get("status") == "success":
                            return data.get("checkpoints", [])
        except Exception as e:
            logger.warning("MCP list_checkpoints failed: %s", e)
        return []

    async def close(self):
        if self._session_ctx:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception:
                pass
        if self._transport_ctx:
            try:
                await self._transport_ctx.__aexit__(None, None, None)
            except Exception:
                pass
        self._connected = False
        self._session = None
        self._session_ctx = None
        self._transport_ctx = None


_mcp_client: MCPClient | None = None


async def get_mcp_client() -> MCPClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
        await _mcp_client.connect()
    return _mcp_client


async def close_mcp_client():
    global _mcp_client
    if _mcp_client:
        await _mcp_client.close()
        _mcp_client = None
