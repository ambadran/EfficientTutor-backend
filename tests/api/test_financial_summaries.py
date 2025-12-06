"""
Tests for the Financial Summary API endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from decimal import Decimal

from tests.constants import (
    TEST_STUDENT_ID,
    TEST_PARENT_ID,
    TEST_TEACHER_ID,
    TEST_UNRELATED_TEACHER_ID,
    TEST_UNRELATED_PARENT_ID,
    TEST_UNRELATED_STUDENT_ID,
)
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.security import JWTHandler


def auth_headers_for_user(user: db_models.Users) -> dict[str, str]:
    """Helper to create auth headers for a given user."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestFinancialSummaryAPI:
    """Test class for the GET /financial-summary/ endpoint."""

    async def test_get_summary_as_student_is_forbidden(
        self,
        client: TestClient,
        test_student_orm: db_models.Students,
    ):
        """Test that a student is forbidden from accessing financial summaries."""
        headers = auth_headers_for_user(test_student_orm)
        
        response = client.get("/financial-summary/", headers=headers)
        
        assert response.status_code == 403
        assert response.json()["detail"] == "User role not authorized for financial summaries."
        print("Student was correctly forbidden from accessing financial summaries.")

    async def test_get_summary_as_parent(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
    ):
        """Test that a parent can successfully retrieve their financial summary."""
        headers = auth_headers_for_user(test_parent_orm)
        
        response = client.get("/financial-summary/", headers=headers)
        
        assert response.status_code == 200
        
        # Structural validation, not value validation
        response_data = response.json()
        assert "total_due" in response_data
        assert "credit_balance" in response_data
        assert "unpaid_count" in response_data

        # Check if values can be cast to their expected types
        try:
            Decimal(response_data["total_due"])
            Decimal(response_data["credit_balance"])
            int(response_data["unpaid_count"])
        except (ValueError, TypeError):
            pytest.fail("Financial summary values have incorrect data types.")

        print("Parent successfully retrieved a structurally valid financial summary.")

    async def test_get_summary_as_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
    ):
        """Test that a teacher can successfully retrieve their financial summary."""
        headers = auth_headers_for_user(test_teacher_orm)
        
        response = client.get("/financial-summary/", headers=headers)
        
        assert response.status_code == 200
        
        # Structural validation, not value validation
        response_data = response.json()
        assert "total_owed_to_teacher" in response_data
        assert "total_credit_held" in response_data
        assert "total_lessons_given_this_month" in response_data

        # Check if values can be cast to their expected types
        try:
            Decimal(response_data["total_owed_to_teacher"])
            Decimal(response_data["total_credit_held"])
            int(response_data["total_lessons_given_this_month"])
        except (ValueError, TypeError):
            pytest.fail("Financial summary values have incorrect data types.")

        print("Teacher successfully retrieved a structurally valid financial summary.")


@pytest.mark.anyio
class TestFinancialSummaryAPIWithFilters:
    """Test class for the GET /financial-summary/ endpoint with filters."""

    # --- Teacher Perspective ---

    async def test_get_summary_as_teacher_for_parent(
        self, client: TestClient, test_teacher_orm: db_models.Teachers
    ):
        """A teacher requests a financial summary for a specific parent."""
        headers = auth_headers_for_user(test_teacher_orm)
        params = {"parent_id": str(TEST_PARENT_ID)}
        response = client.get("/financial-summary/", headers=headers, params=params)

        assert response.status_code == 200
        # Just assert that the structure is correct, not the values
        data = response.json()
        assert "total_owed_to_teacher" in data
        assert "total_credit_held" in data
        assert "total_lessons_given_this_month" in data
        print("Teacher successfully retrieved a filtered summary for a parent.")

    async def test_get_summary_as_teacher_for_student(
        self, client: TestClient, test_teacher_orm: db_models.Teachers
    ):
        """A teacher requests a financial summary for a specific student."""
        headers = auth_headers_for_user(test_teacher_orm)
        params = {"student_id": str(TEST_STUDENT_ID)}
        response = client.get("/financial-summary/", headers=headers, params=params)

        assert response.status_code == 200
        data = response.json()
        assert "total_owed_to_teacher" in data
        assert "total_credit_held" in data
        assert "total_lessons_given_this_month" in data
        print("Teacher successfully retrieved a filtered summary for a student.")

    async def test_get_summary_as_teacher_for_unrelated_parent(
        self, client: TestClient, test_teacher_orm: db_models.Teachers
    ):
        """A teacher requests a summary for a parent they have no logs with."""
        headers = auth_headers_for_user(test_teacher_orm)
        params = {"parent_id": str(TEST_UNRELATED_PARENT_ID)}
        response = client.get("/financial-summary/", headers=headers, params=params)

        assert response.status_code == 403
        # assert "not authorized to view a summary for this student" in response.json()["detail"]
        print("Teacher was correctly forbidden from viewing summary for an unrelated parent.")

    # --- Parent Perspective ---

    async def test_get_summary_as_parent_for_teacher(
        self, client: TestClient, test_parent_orm: db_models.Parents
    ):
        """A parent requests a financial summary for a specific teacher."""
        headers = auth_headers_for_user(test_parent_orm)
        params = {"teacher_id": str(TEST_TEACHER_ID)}
        response = client.get("/financial-summary/", headers=headers, params=params)

        assert response.status_code == 200
        data = response.json()
        assert "total_due" in data
        assert "credit_balance" in data
        assert "unpaid_count" in data
        print("Parent successfully retrieved a filtered summary for a teacher.")

    async def test_get_summary_as_parent_for_student(
        self, client: TestClient, test_parent_orm: db_models.Parents
    ):
        """A parent requests a financial summary for one of their children."""
        headers = auth_headers_for_user(test_parent_orm)
        params = {"student_id": str(TEST_STUDENT_ID)}
        response = client.get("/financial-summary/", headers=headers, params=params)

        assert response.status_code == 200
        data = response.json()
        assert "total_due" in data
        assert "credit_balance" in data
        assert "unpaid_count" in data
        print("Parent successfully retrieved a filtered summary for their student.")

    async def test_get_summary_as_parent_for_unrelated_student_is_forbidden(
        self, client: TestClient, test_parent_orm: db_models.Parents
    ):
        """A parent is forbidden from requesting a summary for a student who is not their child."""
        headers = auth_headers_for_user(test_parent_orm)
        params = {"student_id": str(TEST_UNRELATED_STUDENT_ID)}
        response = client.get("/financial-summary/", headers=headers, params=params)

        assert response.status_code == 403
        # assert "not authorized to view a summary for this student" in response.json()["detail"]
        print("Parent was correctly forbidden from viewing summary for an unrelated student.")

