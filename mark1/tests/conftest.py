from fastapi.testclient import TestClient
import pytest

from mark1.server.app import create_app
from mark1.server.config import Settings


@pytest.fixture
def backend(tmp_path):
    app = create_app(Settings(database=tmp_path / "backend.sqlite"))
    service = app.state.service
    token = service.store.issue_token()
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + token
        yield client, service, token
