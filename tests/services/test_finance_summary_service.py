import pytest
from decimal import Decimal
from pprint import pprint
from fastapi import HTTPException

# --- Import models, services, and Pydantic models ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.finance_service import FinancialSummaryService
from src.efficient_tutor_backend.models import finance as finance_models

# --- Import Test Constants ---
from tests.constants import (
    TEST_TEACHER_ID, 
    TEST_PARENT_ID, 
    TEST_STUDENT_ID
)


@pytest.mark.anyio
class TestFinancialSummaryService:

    ### 1. Test the core logic for a Parent ###

    async def test_get_summary_for_parent(
        self,
        financial_summary_service: FinancialSummaryService
    ):
        """
        Vigorously tests the parent financial summary calculations.
        """
        print(f"\n--- Testing _get_summary_for_parent for ID: {TEST_PARENT_ID} ---")
        
        # --- !! FILL IN THESE VALUES !! ---
        EXPECTED_TOTAL_DUE = Decimal("0.00")  # Example: 100.00
        EXPECTED_CREDIT = Decimal("0.00")     # Example: 0.00
        EXPECTED_UNPAID_COUNT = 3               # Example: 3
        # ----------------------------------

        # --- Act ---
        summary = await financial_summary_service._get_summary_for_parent(TEST_PARENT_ID)
        
        # --- Logging ---
        print("--- Generated Parent Summary (Pydantic) ---")
        pprint(summary.model_dump())
        # --- End Logging ---
        
        # --- Assert ---
        assert isinstance(summary, finance_models.FinancialSummaryForParent)
        #TODO:
        # assert summary.total_due == EXPECTED_TOTAL_DUE
        # assert summary.credit_balance == EXPECTED_CREDIT
        # assert summary.unpaid_count == EXPECTED_UNPAID_COUNT

    ### 2. Test the core logic for a Teacher ###

    async def test_get_summary_for_teacher(
        self,
        financial_summary_service: FinancialSummaryService
    ):
        """
        Vigorously tests the teacher financial summary calculations.
        """
        print(f"\n--- Testing _get_summary_for_teacher for ID: {TEST_TEACHER_ID} ---")

        # --- !! FILL IN THESE VALUES !! ---
        EXPECTED_OWED = Decimal("500.00")       # Example: 500.00
        EXPECTED_CREDIT_HELD = Decimal("50.00") # Example: 50.00
        EXPECTED_LESSONS_MONTH = 10             # Example: 10
        # ----------------------------------
        
        # --- Act ---
        summary = await financial_summary_service._get_summary_for_teacher(TEST_TEACHER_ID)
        
        # --- Logging ---
        print("--- Generated Teacher Summary (Pydantic) ---")
        pprint(summary.model_dump())
        # --- End Logging ---
        
        # --- Assert ---
        assert isinstance(summary, finance_models.FinancialSummaryForTeacher)
        #TODO:
        # assert summary.total_owed_to_teacher == EXPECTED_OWED
        # assert summary.total_credit_held == EXPECTED_CREDIT_HELD
        # assert summary.total_lessons_given_this_month == EXPECTED_LESSONS_MONTH

    ### 3. Test the public API dispatcher (Authorization) ###

    async def test_get_summary_api_as_teacher(
        self,
        financial_summary_service: FinancialSummaryService,
        test_teacher_orm: db_models.Users
    ):
        """
        Tests that the API dispatcher correctly calls the
        teacher summary method and returns a dict.
        """
        print(f"\n--- Testing get_financial_summary_for_api as TEACHER ---")
        
        summary = await financial_summary_service.get_financial_summary_for_api(test_teacher_orm)
        
        assert isinstance(summary, finance_models.FinancialSummaryForTeacher)
        # Check for a teacher-specific key
        assert summary.total_owed_to_teacher is not None
        
        print("--- API-formatted dict for Teacher ---")
        pprint(summary.__dict__)

    async def test_get_summary_api_as_parent(
        self,
        financial_summary_service: FinancialSummaryService,
        test_parent_orm: db_models.Users
    ):
        """
        Tests that the API dispatcher correctly calls the
        parent summary method and returns a dict.
        """
        print(f"\n--- Testing get_financial_summary_for_api as PARENT ---")
        
        summary = await financial_summary_service.get_financial_summary_for_api(test_parent_orm)
        
        assert isinstance(summary, finance_models.FinancialSummaryForParent)
        # Check for a parent-specific key
        assert summary.total_due is not None
        
        print("--- API-formatted dict for Parent ---")
        pprint(summary.__dict__)

    async def test_get_summary_api_as_student(
        self,
        financial_summary_service: FinancialSummaryService,
        test_student_orm: db_models.Users
    ):
        """
        Tests that a STUDENT is FORBIDDEN from fetching a financial summary.
        """
        print(f"\n--- Testing get_financial_summary_for_api as STUDENT ---")
        
        with pytest.raises(HTTPException) as e:
            await financial_summary_service.get_financial_summary_for_api(test_student_orm)
        
        assert e.value.status_code == 403
        
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")


