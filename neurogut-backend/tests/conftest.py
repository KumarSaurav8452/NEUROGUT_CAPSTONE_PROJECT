"""pytest fixtures: the real FastAPI app on a throwaway SQLite database (never touches db/neurogut.db)."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
EXAMPLES = BACKEND.parent / "data" / "v2_examples"
_tmp = tempfile.mkdtemp(prefix="neurogut_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'test.db'}"  # must be set before db.database is imported
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # runs the lifespan: create tables, seed demo users, load models
        yield c


@pytest.fixture(scope="session")
def auth(client):
    r = client.post("/api/auth/login", json={"email": "clinician@neurogut.demo", "password": "clinician123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def models(client, auth):
    r = client.get("/api/v2/models", headers=auth)
    assert r.status_code == 200, r.text
    return {m["disease"]: m for m in r.json()}
