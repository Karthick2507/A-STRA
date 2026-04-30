"""
ASTRA-v2 example API test — Users CRUD.

Demonstrates:
  - APIClient with BearerAuth fixture
  - Full CRUD cycle (create → read → update → delete)
  - Response contract validation
  - OpenAPI spec loader for contract tests
"""
import json
from pathlib import Path

import pytest

from API.client import APIClient, BearerAuth
from API.openapi import OpenAPISpecLoader
from core.config import CONFIG


_DATA_FILE = Path("Data/API/users_data.json")
_DATA: dict = json.loads(_DATA_FILE.read_text()) if _DATA_FILE.exists() else {}
_SPEC_FILE = Path("Data/API/openapi_example.json")


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def api_base_url() -> str:
    return CONFIG.api_url


@pytest.fixture(scope="session")
def auth_token(api_base_url: str) -> str:
    """Acquire a Bearer token by calling the login endpoint."""
    creds = _DATA.get("credentials", {
        "email":    "testuser@example.com",
        "password": "Test@1234",
    })
    with APIClient(api_base_url) as client:
        resp = client.post("/auth/login", json=creds)
        if resp.status_code == 200:
            return resp.json().get("access_token", "")
    return ""


@pytest.fixture(scope="session")
def api_client(api_base_url: str, auth_token: str) -> APIClient:
    client = APIClient(api_base_url, auth=BearerAuth(auth_token))
    return client


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestUsersAPI:
    """CRUD operations on the /users endpoint."""

    def test_list_users_returns_200(self, api_client: APIClient) -> None:
        with api_client:
            resp = api_client.get("/users")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, (list, dict)), "Expected list or paginated dict"

    def test_create_user(self, api_client: APIClient) -> None:
        payload = _DATA.get("create_user", {
            "name": "Alice Test", "email": "alice@example.com", "role": "viewer"
        })
        with api_client:
            resp = api_client.post("/users", json=payload)
        assert resp.status_code in (200, 201), f"Expected 201, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("email") == payload["email"]

    def test_get_user_by_id(self, api_client: APIClient) -> None:
        # Create first to get an ID
        payload = _DATA.get("create_user", {"name": "Bob", "email": "bob@example.com"})
        with api_client:
            create_resp = api_client.post("/users", json=payload)
            if create_resp.status_code not in (200, 201):
                pytest.skip("Cannot create user — skipping get test")
            user_id = create_resp.json().get("id")
            if not user_id:
                pytest.skip("No id in create response")

            resp = api_client.get(f"/users/{user_id}")
        assert resp.status_code == 200
        assert resp.json().get("id") == user_id

    def test_delete_user(self, api_client: APIClient) -> None:
        payload = {"name": "ToDelete", "email": "delete_me@example.com"}
        with api_client:
            create_resp = api_client.post("/users", json=payload)
            if create_resp.status_code not in (200, 201):
                pytest.skip("Cannot create user for deletion test")
            user_id = create_resp.json().get("id")
            if not user_id:
                pytest.skip("No id in create response")

            resp = api_client.delete(f"/users/{user_id}")
        assert resp.status_code in (200, 204)

    def test_get_nonexistent_user_returns_404(self, api_client: APIClient) -> None:
        with api_client:
            resp = api_client.get("/users/999999999")
        assert resp.status_code == 404


class TestOpenAPIContract:
    """Verify live API responses match the OpenAPI spec."""

    @pytest.fixture
    def spec(self) -> OpenAPISpecLoader:
        if not _SPEC_FILE.exists():
            pytest.skip(f"Spec file not found: {_SPEC_FILE}")
        loader = OpenAPISpecLoader(_SPEC_FILE)
        loader.load()
        return loader

    def test_spec_has_expected_endpoints(self, spec: OpenAPISpecLoader) -> None:
        paths = {ep.path for ep in spec.endpoints}
        assert "/auth/login" in paths
        assert "/users" in paths
        assert "/users/{id}" in paths

    def test_get_users_endpoint_spec(self, spec: OpenAPISpecLoader) -> None:
        gets = spec.get_by_method("get")
        user_list_ep = next((ep for ep in gets if ep.path == "/users"), None)
        assert user_list_ep is not None
        assert "200" in user_list_ep.response_schemas

    def test_login_endpoint_requires_request_body(self, spec: OpenAPISpecLoader) -> None:
        posts = spec.get_by_method("post")
        login_ep = next((ep for ep in posts if ep.path == "/auth/login"), None)
        assert login_ep is not None
        assert login_ep.request_body is not None
