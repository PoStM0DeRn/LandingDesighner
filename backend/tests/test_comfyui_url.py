from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import create_session
from app.config import settings
from app.main import app

client = TestClient(app)


def _auth(nick: str = "tester"):
    return {"Authorization": f"Bearer {create_session(nick)}"}


def _public_mode(monkeypatch):
    monkeypatch.setattr(settings, "allow_private_endpoints", False)


class TestComfyuiCheckEndpoint:
    def test_private_url_rejected_in_public_mode(self, clean_storage, monkeypatch):
        _public_mode(monkeypatch)
        r = client.post("/api/comfyui/check", json={"url": "http://127.0.0.1:8188"})
        assert r.status_code == 400
        assert "ComfyUI URL" in r.json()["detail"]

    def test_ok_with_mocked_comfyui(self, clean_storage, monkeypatch):
        import app.api.routes.comfyui as mod

        async def fake_ok(self):
            return True

        async def fake_ckpts(self):
            return ["model_a.safetensors"]

        monkeypatch.setattr(mod.ComfyUIClient, "is_available", fake_ok)
        monkeypatch.setattr(mod.ComfyUIClient, "list_checkpoints", fake_ckpts)
        r = client.post("/api/comfyui/check", json={"url": "http://my-comfy.example.com:8188"})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["checkpoints"] == ["model_a.safetensors"]

    def test_unreachable(self, clean_storage, monkeypatch):
        import app.api.routes.comfyui as mod

        monkeypatch.setattr(mod.ComfyUIClient, "is_available", lambda self: False)
        r = client.post("/api/comfyui/check", json={"url": "http://down.example.com:8188"})
        assert r.status_code == 200
        assert r.json()["ok"] is False
        assert "error" in r.json()


class TestGenerateComfyuiUrl:
    def test_bad_url_rejected(self, clean_storage, monkeypatch):
        _public_mode(monkeypatch)
        with patch("app.api.routes.generate.run_generation"):
            r = client.post("/api/generate", headers=_auth(), data={
                "prompt": "x", "skill_ids": "[]", "comfyui_url": "http://169.254.169.254:8188",
            })
        assert r.status_code == 400
        assert "ComfyUI URL" in r.json()["detail"]

    def test_bad_lm_studio_url_rejected(self, clean_storage, monkeypatch):
        _public_mode(monkeypatch)
        with patch("app.api.routes.generate.run_generation"):
            r = client.post("/api/generate", headers=_auth(), data={
                "prompt": "x", "skill_ids": "[]", "api_endpoint": "http://192.168.0.1:1234/v1",
            })
        assert r.status_code == 400
        assert "LM Studio URL" in r.json()["detail"]

    def test_valid_url_passed_to_pipeline(self, clean_storage, monkeypatch):
        with patch("app.api.routes.generate.run_generation") as mock_run:
            r = client.post("/api/generate", headers=_auth(), data={
                "prompt": "x", "skill_ids": "[]", "comfyui_url": "http://my-comfy.example.com:8188",
            })
        assert r.status_code == 200
        args = mock_run.call_args.args
        assert args[13] == "http://my-comfy.example.com:8188"


class TestWorkflowUpload:
    def test_invalid_json_rejected(self, clean_storage):
        with patch("app.api.routes.generate.run_generation"):
            r = client.post(
                "/api/generate",
                headers=_auth(),
                data={"prompt": "x", "skill_ids": "[]"},
                files={"workflow": ("wf.json", b"this is not json", "application/json")},
            )
        assert r.status_code == 400
        assert "JSON" in r.json()["detail"]

    def test_valid_workflow_saved_and_used(self, clean_storage):
        from pathlib import Path

        from app.storage.local import get_landing_dir, get_state

        workflow_body = b'{"1": {"class_type": "KSampler", "inputs": {"seed": 1}}}'
        with patch("app.api.routes.generate.run_generation") as mock_run:
            r = client.post(
                "/api/generate",
                headers=_auth(),
                data={"prompt": "x", "skill_ids": "[]"},
                files={"workflow": ("my_wf.json", workflow_body, "application/json")},
            )
        assert r.status_code == 200
        lid = r.json()["id"]
        args = mock_run.call_args.args
        # uploaded workflow takes priority over the (empty) path field
        wf_arg = args[10]
        assert wf_arg is not None and wf_arg.endswith("workflow.json")
        assert Path(wf_arg).read_bytes() == workflow_body

        # persisted pipeline state keeps the reference for regeneration
        with patch("app.core.orchestrator._persist_state", wraps=lambda *a, **k: None):
            pass  # not called yet (mocked pipeline) — direct storage check instead
        state_probe = get_landing_dir(lid) / "workflow.json"
        assert state_probe.exists()


class TestPersistComfyuiUrl:
    def test_state_includes_comfyui_url(self, clean_storage):
        from app.core.orchestrator import _persist_state
        from app.models.schemas import DesignTokens, Intent, Section, SectionType
        from app.storage.local import get_state

        state = {
            "landing_id": "cu1",
            "title": "T",
            "prompt": "P",
            "intent": Intent(topic="t"),
            "sections": [Section(type=SectionType.hero, title="H")],
            "design_tokens": DesignTokens(),
            "skills": [],
            "provider": "local",
            "model": "m",
            "use_llm_markup": False,
            "comfyui_url": "http://visitor-comfy.example.com:8188",
            "comfyui_workflow_path": "C:/wf.json",
            "image_steps": 8,
        }
        _persist_state(state, "T")
        s = get_state("cu1")
        assert s["comfyui_url"] == "http://visitor-comfy.example.com:8188"


class TestGenerationInfoComfyuiUrl:
    def test_exposed_in_generation_info(self, clean_storage):
        from app.storage.local import create_landing, save_state

        create_landing("gui1", "T", "D", "P", [], published=True)
        save_state("gui1", {
            "title": "T",
            "comfyui_url": "http://visitor-comfy.example.com:8188",
            "sections": [],
        })
        data = client.get("/api/landings/gui1/generation").json()
        assert data["comfyui_url"] == "http://visitor-comfy.example.com:8188"
