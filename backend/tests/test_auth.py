import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import (
    authenticate,
    create_session,
    register,
    revoke_token,
    validate_token,
)
from app.config import settings
from app.main import app

client = TestClient(app)


def _auth(token: str):
    return {"Authorization": f"Bearer {token}"}


class TestAuthCore:
    def test_register_and_authenticate(self, clean_storage):
        user = register("valer", "secret1")
        assert user["nickname"] == "valer"
        assert user["created_at"] is not None

        token = authenticate("valer", "secret1")
        assert token == "valer"
        session = create_session("valer")
        assert validate_token(session) == "valer"

        assert authenticate("valer", "wrong-pass") is None
        assert authenticate("ghost", "secret1") is None

    def test_duplicate_nickname(self, clean_storage):
        register("valer", "secret1")
        with pytest.raises(ValueError, match="занят"):
            register("valer", "other-pass")

    def test_nickname_rules(self, clean_storage):
        for bad in ["ab", "this-nickname-is-way-too-long-here", "has space", "кириллица", ""]:
            with pytest.raises(ValueError):
                register(bad, "secret1")

    def test_password_rules(self, clean_storage):
        with pytest.raises(ValueError):
            register("valer", "12345")

    def test_token_lifecycle(self, clean_storage):
        register("valer", "secret1")
        token = create_session("valer")
        assert validate_token(token) == "valer"
        revoke_token(token)
        assert validate_token(token) is None

    def test_expired_session_rejected(self, clean_storage):
        register("valer", "secret1")
        token = create_session("valer")
        sp = Path(settings.storage_dir) / "sessions.json"
        sessions = json.loads(sp.read_text(encoding="utf-8"))
        sessions[token]["expires_at"] = time.time() - 10
        sp.write_text(json.dumps(sessions), encoding="utf-8")
        assert validate_token(token) is None

    def test_password_never_stored_plain(self, clean_storage):
        register("valer", "secret1")
        raw = (Path(settings.storage_dir) / "users.json").read_text(encoding="utf-8")
        assert "secret1" not in raw
        assert "password_hash" in raw


class TestAuthAPI:
    def test_register_login_me_logout(self, clean_storage):
        r = client.post("/api/auth/register", json={"nickname": "valer", "password": "secret1"})
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["nickname"] == "valer"
        assert len(body["token"]) >= 32

        # me requires the token
        assert client.get("/api/auth/me").status_code == 401
        r = client.get("/api/auth/me", headers=_auth(body["token"]))
        assert r.status_code == 200
        assert r.json()["nickname"] == "valer"

        # wrong password
        r = client.post("/api/auth/login", json={"nickname": "valer", "password": "wrong"})
        assert r.status_code == 401

        # duplicate registration
        r = client.post("/api/auth/register", json={"nickname": "valer", "password": "secret2"})
        assert r.status_code == 409

        # logout revokes the token
        assert client.post("/api/auth/logout", headers=_auth(body["token"])).status_code == 204
        assert client.get("/api/auth/me", headers=_auth(body["token"])).status_code == 401

    def test_login_after_register(self, clean_storage):
        client.post("/api/auth/register", json={"nickname": "second", "password": "secret1"})
        r = client.post("/api/auth/login", json={"nickname": "second", "password": "secret1"})
        assert r.status_code == 200
        token = r.json()["token"]
        assert validate_token(token) == "second"

    def test_login_unknown_user_401(self, clean_storage):
        assert client.post("/api/auth/login", json={"nickname": "ghost", "password": "whatever"}).status_code == 401


class TestOwnership:
    def test_generate_requires_auth(self, clean_storage):
        assert client.post("/api/generate", data={"prompt": "x"}).status_code == 401

    def test_generate_sets_owner(self, clean_storage):
        from unittest.mock import patch

        from app.storage.local import get_meta

        headers = _auth(create_session("author1"))
        with patch("app.api.routes.generate.run_generation"):
            r = client.post("/api/generate", headers=headers, data={
                "prompt": "Landing",
                "title": "T",
                "skill_ids": "[]",
            })
        assert r.status_code == 200
        meta = get_meta(r.json()["id"])
        assert meta.owner_nickname == "author1"

    def test_foreign_delete_403_own_204(self, clean_storage):
        from app.storage.local import create_landing

        create_landing("own1", "T", "D", "P", [], owner_nickname="author1")

        stranger = _auth(create_session("author2"))
        assert client.delete("/api/landings/own1", headers=stranger).status_code == 403

        owner = _auth(create_session("author1"))
        assert client.delete("/api/landings/own1", headers=owner).status_code == 204

    def test_ownerless_any_authed_user_can_delete(self, clean_storage):
        from app.storage.local import create_landing

        create_landing("legacy1", "T", "D", "P", [], owner_nickname=None)
        somebody = _auth(create_session("somebody"))
        assert client.delete("/api/landings/legacy1", headers=somebody).status_code == 204

    def test_delete_and_update_require_auth(self, clean_storage):
        from app.storage.local import create_landing

        create_landing("own2", "T", "D", "P", [], owner_nickname="author1")
        assert client.delete("/api/landings/own2").status_code == 401
        assert client.put("/api/landings/own2", json={"title": "X"}).status_code == 401

    def test_read_endpoints_stay_public(self, clean_storage):
        from app.storage.local import create_landing

        create_landing("pub1", "T", "D", "P", [], owner_nickname="author1", published=True)
        assert client.get("/api/landings").status_code == 200
        assert client.get("/api/landings/pub1").status_code == 200
        assert client.get("/api/landings/pub1/generation").status_code == 200
