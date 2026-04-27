"""ASTRA API code generator - generates pytest API test files from A* results."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from schemas.field_schema import FieldSchema, ResolvedField, flatten_schema
from core.search.a_star_engine import AStarResult
from utils.logger import logger

_TESTS_DIR = Path(__file__).parent.parent / "tests" / "api"


class ApiCodeGenerator:
    def __init__(self, schema: FieldSchema, astar_result: AStarResult, api_blueprint: Dict[str, Any]) -> None:
        self.schema = schema
        self.astar_result = astar_result
        self.api_blueprint = api_blueprint

    def generate(self) -> List[str]:
        """Generate 6 API test files: POST, PUT, PATCH, GET, DELETE, CRUD."""
        files_generated: List[str] = []

        test_files = [
            ("test_post.py", "POST", self._generate_post_test),
            ("test_put.py", "PUT", self._generate_put_test),
            ("test_patch.py", "PATCH", self._generate_patch_test),
            ("test_get.py", "GET", self._generate_get_test),
            ("test_delete.py", "DELETE", self._generate_delete_test),
            ("test_crud.py", "CRUD", self._generate_crud_test),
        ]

        _TESTS_DIR.mkdir(parents=True, exist_ok=True)

        for filename, method, generator in test_files:
            content = generator()
            path = _TESTS_DIR / filename
            path.write_text(content, encoding="utf-8")
            files_generated.append(str(path))
            logger.codegen(f"Generated {filename}")

        return files_generated

    def _generate_post_test(self) -> str:
        payload = self._build_payload()
        return f'''"""API test: POST /api/register"""
import httpx
import pytest

BASE_URL = "http://localhost:3000"


@pytest.mark.api
def test_post_register_success(api_headers):
    """Test successful user registration via POST."""
    payload = {payload}
    response = httpx.post(f"{{BASE_URL}}/api/register", json=payload, headers=api_headers)
    assert response.status_code == 201
    assert "id" in response.json()


@pytest.mark.api
def test_post_register_missing_field(api_headers):
    """Test registration fails with missing required field."""
    payload = {payload}
    del payload["email"]
    response = httpx.post(f"{{BASE_URL}}/api/register", json=payload, headers=api_headers)
    assert response.status_code >= 400
'''

    def _generate_put_test(self) -> str:
        payload = self._build_payload()
        return f'''"""API test: PUT /api/register/{{id}}"""
import httpx
import pytest

BASE_URL = "http://localhost:3000"


@pytest.mark.api
def test_put_update_success(api_headers):
    """Test successful user update via PUT."""
    user_id = "123"
    payload = {payload}
    payload["firstName"] = "Updated"
    response = httpx.put(f"{{BASE_URL}}/api/register/{{user_id}}", json=payload, headers=api_headers)
    assert response.status_code in [200, 204]
'''

    def _generate_patch_test(self) -> str:
        return '''"""API test: PATCH /api/register/{id}"""
import httpx
import pytest

BASE_URL = "http://localhost:3000"


@pytest.mark.api
def test_patch_partial_update(api_headers):
    """Test partial user update via PATCH."""
    user_id = "123"
    payload = {"firstName": "Patched"}
    response = httpx.patch(f"{BASE_URL}/api/register/{user_id}", json=payload, headers=api_headers)
    assert response.status_code in [200, 204]
'''

    def _generate_get_test(self) -> str:
        return '''"""API test: GET /api/register/{id}"""
import httpx
import pytest

BASE_URL = "http://localhost:3000"


@pytest.mark.api
def test_get_user_success(api_headers):
    """Test successful user retrieval via GET."""
    user_id = "123"
    response = httpx.get(f"{BASE_URL}/api/register/{user_id}", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert "firstName" in data
    assert "lastName" in data
    assert "email" in data


@pytest.mark.api
def test_get_user_not_found(api_headers):
    """Test GET returns 404 for non-existent user."""
    user_id = "999999"
    response = httpx.get(f"{BASE_URL}/api/register/{user_id}", headers=api_headers)
    assert response.status_code == 404
'''

    def _generate_delete_test(self) -> str:
        return '''"""API test: DELETE /api/register/{id}"""
import httpx
import pytest

BASE_URL = "http://localhost:3000"


@pytest.mark.api
def test_delete_user_success(api_headers):
    """Test successful user deletion via DELETE."""
    user_id = "123"
    response = httpx.delete(f"{BASE_URL}/api/register/{user_id}", headers=api_headers)
    assert response.status_code in [200, 204]


@pytest.mark.api
def test_delete_already_deleted(api_headers):
    """Test DELETE on already-deleted user returns 404."""
    user_id = "123"
    httpx.delete(f"{BASE_URL}/api/register/{user_id}", headers=api_headers)
    response = httpx.delete(f"{BASE_URL}/api/register/{user_id}", headers=api_headers)
    assert response.status_code == 404
'''

    def _generate_crud_test(self) -> str:
        payload = self._build_payload()
        return f'''"""API test: Full CRUD lifecycle"""
import httpx
import pytest

BASE_URL = "http://localhost:3000"


@pytest.mark.api
def test_crud_full_lifecycle(api_headers):
    """Test complete CRUD workflow: Create -> Read -> Update -> Delete."""
    # Create
    payload = {payload}
    create_response = httpx.post(f"{{BASE_URL}}/api/register", json=payload, headers=api_headers)
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    # Read
    get_response = httpx.get(f"{{BASE_URL}}/api/register/{{user_id}}", headers=api_headers)
    assert get_response.status_code == 200

    # Update
    payload["firstName"] = "Updated"
    update_response = httpx.put(f"{{BASE_URL}}/api/register/{{user_id}}", json=payload, headers=api_headers)
    assert update_response.status_code in [200, 204]

    # Delete
    delete_response = httpx.delete(f"{{BASE_URL}}/api/register/{{user_id}}", headers=api_headers)
    assert delete_response.status_code in [200, 204]
'''

    def _build_payload(self) -> Dict[str, Any]:
        """Convert A* path to JSON request body."""
        payload: Dict[str, Any] = {}
        for field in self.astar_result.path:
            # Cast values based on field type
            if field.type == "email":
                payload[field.name] = "test@example.com"
            elif field.type == "password":
                payload[field.name] = "Secure@123"
            elif field.type == "number":
                payload[field.name] = 42
            elif field.type == "checkbox":
                payload[field.name] = True
            else:
                payload[field.name] = f"test_{field.name}"
        return payload
