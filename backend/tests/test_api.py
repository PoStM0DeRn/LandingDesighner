import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import create_session
from app.main import app

client = TestClient(app)


def _auth(token: str):
    return {"Authorization": f"Bearer {token}"}


class TestHealth:
    def test_health(self):
        assert client.get("/api/health").json()["status"] == "ok"


class TestLandingsAPI:
    def test_crud_lifecycle(self, clean_storage):
        from app.storage.local import create_landing

        headers = _auth(create_session("tester"))
        create_landing("abc123", "Title", "Desc", "Prompt", ["tag1"], published=True)

        r = client.get("/api/landings")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "abc123"

        r = client.get("/api/landings/abc123")
        assert r.status_code == 200
        assert r.json()["title"] == "Title"
        assert r.json()["status"] == "generating"

        r = client.put("/api/landings/abc123", json={"title": "Renamed", "tags": ["x"]}, headers=headers)
        assert r.status_code == 200
        assert r.json()["title"] == "Renamed"

        assert client.delete("/api/landings/abc123", headers=headers).status_code == 204
        assert client.get("/api/landings/abc123").status_code == 404
        assert client.delete("/api/landings/abc123", headers=headers).status_code == 404

    def test_404s(self, clean_storage):
        assert client.get("/api/landings/nope").status_code == 404
        assert client.get("/api/landings/nope/html").status_code == 404
        assert client.get("/api/landings/nope/download").status_code == 404

    def test_pagination_and_search(self, clean_storage):
        from app.storage.local import create_landing

        for i in range(3):
            create_landing(f"id{i}", f"Landing {i}", "d", f"prompt {i}", [], published=True)

        data = client.get("/api/landings", params={"page": 1, "page_size": 2}).json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["pages"] == 2

        data = client.get("/api/landings", params={"search": "Landing 2"}).json()
        assert data["total"] == 1

    def test_error_message_roundtrip(self, clean_storage):
        from app.models.schemas import LandingStatus
        from app.storage.local import create_landing, get_meta, update_landing_status

        create_landing("err1", "T", "D", "P", [])
        update_landing_status("err1", LandingStatus.error, error_message="LLM timed out")
        meta = get_meta("err1")
        assert meta.status == LandingStatus.error
        assert meta.error_message == "LLM timed out"

        # ready clears the error message
        update_landing_status("err1", LandingStatus.ready)
        assert get_meta("err1").error_message is None


class TestSkillsAPI:
    def test_writes_require_auth(self, clean_storage):
        assert client.post("/api/skills", json={
            "name": "X", "description": "", "prompt_addition": "Y",
        }).status_code == 401
        assert client.delete("/api/skills/whatever").status_code == 401

    def test_crud_lifecycle(self, clean_storage):
        headers = _auth(create_session("tester"))
        r = client.post("/api/skills", headers=headers, json={
            "name": "Test skill", "description": "d", "prompt_addition": "Always do X",
        })
        assert r.status_code == 201
        sid = r.json()["id"]

        assert client.get(f"/api/skills/{sid}").json()["name"] == "Test skill"

        r = client.put(f"/api/skills/{sid}", headers=headers, json={
            "name": "Renamed", "description": "", "prompt_addition": "Y",
        })
        assert r.status_code == 200
        assert r.json()["name"] == "Renamed"

        assert client.delete(f"/api/skills/{sid}", headers=headers).status_code == 204
        assert client.get(f"/api/skills/{sid}").status_code == 404

    def test_404s(self, clean_storage):
        headers = _auth(create_session("tester"))
        assert client.get("/api/skills/ghost").status_code == 404
        assert client.delete("/api/skills/ghost", headers=headers).status_code == 404


class TestGenerateEndpoint:
    def test_requires_auth(self, clean_storage):
        r = client.post("/api/generate", data={"prompt": "x"})
        assert r.status_code == 401

    def test_starts_generation(self, clean_storage):
        headers = _auth(create_session("tester"))
        with patch("app.api.routes.generate.run_generation") as mock_run:
            r = client.post("/api/generate", headers=headers, data={
                "prompt": "A coffee shop landing",
                "title": "Coffee",
                "tags": '["a"]',
                "skill_ids": "[]",
                "comfyui_workflow_path": "C:/fake/wf.json",
                "image_steps": "8",
            })
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "generating"
            assert len(data["id"]) == 12

            # thread starts the orchestrator with parsed args
            for _ in range(40):
                if mock_run.called:
                    break
                time.sleep(0.05)
            assert mock_run.called
            args = mock_run.call_args.args
            assert args[0] == data["id"]
            assert args[1] == "A coffee shop landing"
            assert args[2] == "Coffee"
            # "C:/fake/wf.json" is outside the workflows whitelist → rejected
            assert args[10] is None
            assert args[11] == 8

        # meta persisted even before pipeline runs (draft visible to its owner)
        assert client.get(f"/api/landings/{data['id']}", headers=headers).json()["status"] == "generating"


class TestWorkflowPathWhitelist:
    def test_inside_root_allowed(self, clean_storage):
        from pathlib import Path

        from app.api.routes.generate import _validated_workflow_path
        from app.config import settings

        inside = str(Path(settings.comfyui_workflows_root) / "my.json")
        assert _validated_workflow_path(inside) is not None

    def test_outside_root_rejected(self, clean_storage):
        from app.api.routes.generate import _validated_workflow_path

        assert _validated_workflow_path("C:/Users/somebody/Desktop/evil.json") is None
        assert _validated_workflow_path("../../../etc/passwd") is None
        assert _validated_workflow_path("") is None
        assert _validated_workflow_path(None) is None
