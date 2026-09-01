from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestPersistState:
    def test_includes_provider_model_markup_flag(self, clean_storage):
        from app.core.orchestrator import _persist_state
        from app.models.schemas import DesignTokens, Intent, Section, SectionType, Skill
        from app.storage.local import get_state

        state = {
            "landing_id": "pst1",
            "title": "T",
            "prompt": "P",
            "intent": Intent(topic="t", style="minimalist", tone="professional"),
            "sections": [Section(type=SectionType.hero, title="H")],
            "design_tokens": DesignTokens(),
            "skills": [Skill(id="s1", name="SEO skill", prompt_addition="ALWAYS add meta tags")],
            "provider": "local",
            "model": "test-model-7b",
            "use_llm_markup": True,
            "comfyui_workflow_path": "C:/wf.json",
            "image_steps": 8,
        }
        _persist_state(state, "T")
        s = get_state("pst1")
        assert s["provider"] == "local"
        assert s["model"] == "test-model-7b"
        assert s["use_llm_markup"] is True
        assert s["skills"][0]["prompt_addition"] == "ALWAYS add meta tags"


class TestCreateLandingMeta:
    def test_stores_provider_and_model(self, clean_storage):
        from app.models.schemas import LandingStatus
        from app.storage.local import create_landing, get_meta

        create_landing("pm1", "T", "D", "P", [], provider="openai", model="gpt-4o")
        meta = get_meta("pm1")
        assert meta.provider == "openai"
        assert meta.model == "gpt-4o"

    def test_old_meta_without_model_parses(self, clean_storage):
        # old meta.json files have no provider/model — must parse with None
        import json
        from pathlib import Path

        from app.models.schemas import LandingStatus
        from app.storage.local import create_landing, get_meta

        create_landing("old1", "T", "D", "P", [])
        p = Path(clean_storage) / "landings" / "old1" / "meta.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        for key in ("provider", "model"):
            data.pop(key, None)
        p.write_text(json.dumps(data), encoding="utf-8")

        meta = get_meta("old1")
        assert meta.model is None and meta.provider is None
        assert meta.status == LandingStatus.generating


class TestGenerationEndpoint:
    def test_404(self, clean_storage):
        assert client.get("/api/landings/nope/generation").status_code == 404

    def test_available_false_without_state(self, clean_storage):
        from app.storage.local import create_landing

        create_landing("g1", "T", "D", "The prompt", [], provider="local", model="m1", published=True)
        data = client.get("/api/landings/g1/generation").json()
        assert data["available"] is False
        assert data["prompt"] == "The prompt"
        assert data["model"] == "m1"
        assert data["skills"] == []

    def test_full_info_with_skills(self, clean_storage):
        from app.storage.local import create_landing, save_state

        create_landing("g2", "T", "D", "Prompt text", [], provider="local", model="gemma-9b", published=True)
        save_state("g2", {
            "title": "T",
            "provider": "local",
            "model": "gemma-9b",
            "use_llm_markup": True,
            "image_steps": 12,
            "comfyui_workflow_path": "C:/wf.json",
            "intent": {"topic": "coffee", "style": "minimalist", "tone": "friendly"},
            "tokens": {"primary_color": "#ff0000", "bg_color": "#ffffff"},
            "skills": [
                {"id": "s1", "name": "SEO", "description": "d", "prompt_addition": "FULL SKILL TEXT", "built_in": True},
            ],
        })
        data = client.get("/api/landings/g2/generation").json()
        assert data["available"] is True
        assert data["model"] == "gemma-9b"
        assert data["use_llm_markup"] is True
        assert data["image_steps"] == 12
        assert data["intent"]["topic"] == "coffee"
        assert data["tokens"]["primary_color"] == "#ff0000"
        assert data["skills"][0]["prompt_addition"] == "FULL SKILL TEXT"

    def test_skills_with_broken_entries_skipped(self, clean_storage):
        from app.storage.local import create_landing, save_state

        create_landing("g3", "T", "D", "P", [], published=True)
        save_state("g3", {"title": "T", "skills": [{"oops": True}, None]})
        data = client.get("/api/landings/g3/generation").json()
        assert data["available"] is True
        assert data["skills"] == []
