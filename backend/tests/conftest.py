import os
import sys
from pathlib import Path

import pytest

# The instance lock (real backend) must not block tests
os.environ.setdefault("LG_INSTANCE_GUARD", "0")

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402


@pytest.fixture()
def clean_storage(tmp_path, monkeypatch):
    """Point storage at a fresh temp dir for the duration of a test."""
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    return tmp_path


@pytest.fixture()
def no_custom_workflow(monkeypatch):
    """Disable the globally configured workflow path so tests are deterministic."""
    monkeypatch.setattr(settings, "comfyui_workflow_path", "")
