import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock

from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.user_service import ParentService, TeacherService
from src.efficient_tutor_backend.main import app
from src.efficient_tutor_backend.services.geo_service import GeoService

@pytest.mark.anyio
class TestAuthRoutes:
    
    async def test_login_for_access_token_success(self, client: TestClient, test_teacher_orm: db_models.Teachers):
        """Tests successful login for a teacher."""
        response = client.post(
            "/auth/login",
            data={"username": test_teacher_orm.email, "password": "testpassword"}
        )
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"

    async def test_login_for_access_token_invalid_credentials(self, client: TestClient, test_teacher_orm: db_models.Teachers):
        """Tests login with invalid credentials."""
        response = client.post(
            "/auth/login",
            data={"username": test_teacher_orm.email, "password": "wrongpassword"}
        )
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    async def test_signup_parent(self, client: TestClient, mock_api_geo_service: MagicMock, db_session):
        """Tests successful parent signup."""
        app.dependency_overrides[GeoService] = lambda: mock_api_geo_service
        app.dependency_overrides[ParentService] = lambda: ParentService(db_session, mock_api_geo_service)

        parent_data = {
            "email": "new.parent@example.com",
            "password": "newpassword123",
            "first_name": "New",
            "last_name": "Parent",
        }
        
        response = client.post("/auth/signup/parent", json=parent_data)
        
        assert response.status_code == 201
        new_parent = response.json()
        assert new_parent["email"] == parent_data["email"]
        assert new_parent["first_name"] == parent_data["first_name"]
        assert new_parent["role"] == "parent"
        assert new_parent["timezone"] == "America/New_York"
        assert new_parent["currency"] == "USD"
        app.dependency_overrides = {}


    async def test_signup_teacher(self, client: TestClient, mock_api_geo_service: MagicMock, db_session):
        """Tests successful teacher signup."""
        app.dependency_overrides[GeoService] = lambda: mock_api_geo_service
        app.dependency_overrides[TeacherService] = lambda: TeacherService(db_session, mock_api_geo_service)

        teacher_data = {
            "email": "new.teacher@example.com",
            "password": "newpassword123",
            "first_name": "New",
            "last_name": "Teacher",
        }

        response = client.post("/auth/signup/teacher", json=teacher_data)
        
        assert response.status_code == 201
        new_teacher = response.json()
        assert new_teacher["email"] == teacher_data["email"]
        assert new_teacher["first_name"] == teacher_data["first_name"]
        assert new_teacher["role"] == "teacher"
        assert new_teacher["timezone"] == "America/New_York"
        assert new_teacher["currency"] == "USD"
        app.dependency_overrides = {}

    async def test_signup_duplicate_email(self, client: TestClient, test_parent_orm: db_models.Parents):
        """Tests signup with a duplicate email."""
        parent_data = {
            "email": test_parent_orm.email, # Existing email
            "password": "newpassword123",
            "first_name": "Duplicate",
            "last_name": "Parent",
        }
        response = client.post("/auth/signup/parent", json=parent_data)
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]
