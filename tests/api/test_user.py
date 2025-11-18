"""
Tests for the general User API endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.security import JWTHandler
from tests.constants import TEST_TEACHER_ID


def auth_headers_for_user(user: db_models.Users) -> dict[str, str]:
    """Helper to create auth headers for a given user."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestUserAPIGET:
    """Test class for the GET endpoints under the UserAPI router."""

    async def test_get_users_me(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
    ):
        """Test that any authenticated user can retrieve their own profile."""
        headers = auth_headers_for_user(test_teacher_orm)
        
        response = client.get("/users/me", headers=headers)
        
        assert response.status_code == 200
        
        response_data = response.json()
        assert response_data["id"] == str(TEST_TEACHER_ID)
        assert response_data["email"] == test_teacher_orm.email
        
        print(f"Successfully retrieved profile for user {test_teacher_orm.email}")

