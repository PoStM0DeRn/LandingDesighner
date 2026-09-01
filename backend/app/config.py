from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    lm_studio_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "llama-3"
    openai_api_key: str = ""
    storage_dir: str = str(Path(__file__).parent.parent.parent / "storage")
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_model: str = ""
    comfyui_workflow_path: str = str(Path(__file__).parent.parent.parent / "templates" / "workflows" / "txt2img.json")
    comfyui_workflows_root: str = str(Path(__file__).parent.parent.parent / "templates" / "workflows")
    comfyui_timeout: int = 120
    image_generation_enabled: bool = True
    image_default_steps: int = 20
    image_webp_quality: int = 82
    generation_queue_timeout: int = 900
    image_default_cfg: float = 7.0
    image_negative_prompt: str = "blurry, low quality, distorted, deformed, ugly, bad anatomy, watermark, text, logo"

    tailwind_build_enabled: bool = True
    # false on a public VDS: user-supplied service URLs must not point at
    # internal networks (SSRF protection). true for local dev.
    allow_private_endpoints: bool = True

    serve_frontend: bool = True
    frontend_dist_dir: str = str(Path(__file__).parent.parent.parent / "frontend" / "dist")

    # Anti-phantom guard: a second backend instance fails loudly on this port
    instance_lock_port: int = 8701

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def landings_dir(self) -> Path:
        p = Path(self.storage_dir) / "landings"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def workflows_dir(self) -> Path:
        return Path(__file__).parent.parent.parent / "templates" / "workflows"


settings = Settings()
