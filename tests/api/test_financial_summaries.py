"""
Tests for the Financial Summary API endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from decimal import Decimal

from tests.constants import TEST_STUDENT_ID, TEST_PARENT_ID, TEST_TEACHER_ID
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

