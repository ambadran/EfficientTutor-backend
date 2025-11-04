import pytest
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
from pprint import pprint
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# --- Import models, services, and Pydantic models ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.finance_service import PaymentLogService
from src.efficient_tutor_backend.models import finance as finance_models
from src.efficient_tutor_backend.database.db_enums import LogStatusEnum

# --- Import Test Constants ---
from tests.constants import (
    TEST_TEACHER_ID, 
    TEST_PARENT_ID, 
    TEST_STUDENT_ID,
    TEST_PAYMENT_LOG_ID # Assumes this is in your constants.py
)


@pytest.mark.anyio
class TestPaymentLogService:

    ### Tests for get_all_payment_logs_for_api (and its underlying auth) ###

    async def test_get_all_logs_api_as_teacher(
        self,
        payment_log_service: PaymentLogService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that a TEACHER gets their relevant payment logs."""
        print(f"\n--- Testing get_all_payment_logs_for_api as TEACHER ({test_teacher_orm.first_name}) ---")
        
        logs = await payment_log_service.get_all_payment_logs_for_api(test_teacher_orm)
        
        assert isinstance(logs, list)
        print(f"--- Found {len(logs)} API logs for Teacher ---")
        if len(logs) > 0:
            assert isinstance(logs[0], dict)
            assert 'parent_name' in logs[0] # Check for teacher-specific field
            print("--- Example API log (raw dict) ---")
            pprint(logs[0])

    async def test_get_all_logs_api_as_parent(
        self,
        payment_log_service: PaymentLogService,
        test_parent_orm: db_models.Users
    ):
        """Tests that a PARENT gets their relevant payment logs."""
        print(f"\n--- Testing get_all_payment_logs_for_api as PARENT ({test_parent_orm.first_name}) ---")
        
        logs = await payment_log_service.get_all_payment_logs_for_api(test_parent_orm)
        
        assert isinstance(logs, list)
        print(f"--- Found {len(logs)} API logs for Parent ---")
        if len(logs) > 0:
            assert isinstance(logs[0], dict)
            assert 'teacher_name' in logs[0] # Check for parent-specific field
            print("--- Example API log (raw dict) ---")
            pprint(logs[0])

    async def test_get_all_logs_api_as_student(
        self,
        payment_log_service: PaymentLogService,
        test_student_orm: db_models.Users
    ):
        """Tests that a STUDENT is FORBIDDEN from fetching payment logs."""
        print(f"\n--- Testing get_all_payment_logs_for_api as STUDENT ({test_student_orm.first_name}) ---")
        
        with pytest.raises(HTTPException) as e:
            await payment_log_service.get_all_payment_logs_for_api(test_student_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    ### Tests for get_payment_log_by_id_for_api (and its auth) ###

    async def test_get_log_by_id_api_as_teacher(
        self,
        payment_log_service: PaymentLogService,
        payment_log_orm: db_models.PaymentLogs,
        test_teacher_orm: db_models.Users
    ):
        """Tests that a TEACHER can fetch an associated payment log."""
        log_id = payment_log_orm.id
        print(f"\n--- Testing get_payment_log_by_id_for_api as TEACHER for ID: {log_id} ---")
        
        # This assumes the test_teacher_orm is the teacher associated with payment_log_orm
        assert payment_log_orm.teacher_id == test_teacher_orm.id, "Test data mismatch"
        
        log_dict = await payment_log_service.get_payment_log_by_id_for_api(log_id, test_teacher_orm)
        
        assert isinstance(log_dict, dict)
        assert log_dict['id'] == str(log_id)
        print("--- Found log (API dict) ---")
        pprint(log_dict)

    async def test_get_log_by_id_api_as_parent(
        self,
        payment_log_service: PaymentLogService,
        payment_log_orm: db_models.PaymentLogs,
        test_parent_orm: db_models.Users
    ):
        """Tests that a PARENT can fetch an associated payment log."""
        log_id = payment_log_orm.id
        print(f"\n--- Testing get_payment_log_by_id_for_api as PARENT for ID: {log_id} ---")

        # This assumes the test_parent_orm is the parent associated with payment_log_orm
        assert payment_log_orm.parent_id == test_parent_orm.id, "Test data mismatch"
        
        log_dict = await payment_log_service.get_payment_log_by_id_for_api(log_id, test_parent_orm)
        
        assert isinstance(log_dict, dict)
        assert log_dict['id'] == str(log_id)
        print("--- Found log (API dict) ---")
        pprint(log_dict)

    async def test_get_log_by_id_api_as_student(
        self,
        payment_log_service: PaymentLogService,
        payment_log_orm: db_models.PaymentLogs,
        test_student_orm: db_models.Users
    ):
        """Tests that a STUDENT is FORBIDDEN from fetching a payment log."""
        log_id = payment_log_orm.id
        print(f"\n--- Testing get_payment_log_by_id_for_api as STUDENT for ID: {log_id} ---")
        
        with pytest.raises(HTTPException) as e:
            await payment_log_service.get_payment_log_by_id_for_api(log_id, test_student_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    ### Tests for create_payment_log (Teacher only) ###

    async def test_create_payment_log_as_teacher(
        self,
        db_session: AsyncSession,
        payment_log_service: PaymentLogService,
        test_teacher_orm: db_models.Users,
        test_parent_orm: db_models.Users
    ):
        """Tests that a TEACHER can create a new payment log."""
        print(f"\n--- Testing create_payment_log as TEACHER ---")
        
        log_data = {
            "parent_id": test_parent_orm.id,
            "teacher_id": test_teacher_orm.id,
            "amount_paid": Decimal("100.00"),
            "payment_date": datetime.now(timezone.utc).isoformat(),
            "notes": "Test payment from pytest"
        }
        
        new_log_dict = await payment_log_service.create_payment_log(log_data, test_teacher_orm)
        await db_session.commit() # Commit the creation
        
        assert new_log_dict is not None
        assert isinstance(new_log_dict, dict)
        assert new_log_dict['id'] is not None
        assert new_log_dict['amount_paid'] == "100.00"
        assert new_log_dict['parent_name'] == f"{test_parent_orm.first_name} {test_parent_orm.last_name}"
        
        print(f"--- Successfully created payment log (API dict) ---")
        pprint(new_log_dict)

    async def test_create_payment_log_as_parent(
        self,
        payment_log_service: PaymentLogService,
        test_parent_orm: db_models.Users
    ):
        """Tests that a PARENT is FORBIDDEN from creating a payment log."""
        print(f"\n--- Testing create_payment_log as PARENT ---")
        
        log_data = { "parent_id": TEST_PARENT_ID, "teacher_id": TEST_TEACHER_ID, "amount_paid": 100, "payment_date": datetime.now().isoformat() }
        
        with pytest.raises(HTTPException) as e:
            await payment_log_service.create_payment_log(log_data, test_parent_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    ### Tests for void_payment_log (Teacher only) ###

    async def test_void_payment_log_as_teacher(
        self,
        db_session: AsyncSession,
        payment_log_service: PaymentLogService,
        test_teacher_orm: db_models.Users,
        payment_log_orm: db_models.PaymentLogs
    ):
        """Tests that a TEACHER can void a payment log."""
        log_to_void = payment_log_orm
        print(f"\n--- Testing void_payment_log as TEACHER for ID: {log_to_void.id} ---")
        
        # Pre-condition
        log_to_void.status = LogStatusEnum.ACTIVE.value
        db_session.add(log_to_void)
        await db_session.commit()
        await db_session.refresh(log_to_void)
        assert log_to_void.status == LogStatusEnum.ACTIVE.value
        
        # Act
        success = await payment_log_service.void_payment_log(log_to_void.id, test_teacher_orm)
        assert success is True
        
        await db_session.commit() # Commit the void
        
        # Verify
        await db_session.refresh(log_to_void)
        assert log_to_void.status == LogStatusEnum.VOID.value
        
        print(f"--- Successfully voided log. Final Status: {log_to_void.status} ---")

    async def test_void_payment_log_as_parent(
        self,
        payment_log_service: PaymentLogService,
        test_parent_orm: db_models.Users,
        payment_log_orm: db_models.PaymentLogs
    ):
        """Tests that a PARENT is FORBIDDEN from voiding a log."""
        print(f"\n--- Testing void_payment_log as PARENT for ID: {payment_log_orm.id} ---")
        
        with pytest.raises(HTTPException) as e:
            await payment_log_service.void_payment_log(payment_log_orm.id, test_parent_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    ### Tests for correct_payment_log (Teacher only) ###

    async def test_correct_payment_log_as_teacher(
        self,
        db_session: AsyncSession,
        payment_log_service: PaymentLogService,
        test_teacher_orm: db_models.Users,
        payment_log_orm: db_models.PaymentLogs
    ):
        """Tests that a TEACHER can correct a payment log."""
        old_log = payment_log_orm
        print(f"\n--- Testing correct_payment_log as TEACHER for old ID: {old_log.id} ---")

        # Pre-condition
        old_log.status = LogStatusEnum.ACTIVE.value
        db_session.add(old_log)
        await db_session.commit()
        await db_session.refresh(old_log)
        
        # Correction data
        correction_data = {
            "parent_id": old_log.parent_id,
            "teacher_id": old_log.teacher_id,
            "amount_paid": Decimal("999.00"), # <-- The correction
            "payment_date": old_log.payment_date.isoformat(),
            "notes": "Corrected payment from pytest"
        }
        
        # Act
        new_log_dict = await payment_log_service.correct_payment_log(
            old_log.id, correction_data, test_teacher_orm
        )
        
        await db_session.commit() # Commit the correction
        
        # Verify new log (from returned dict)
        assert isinstance(new_log_dict, dict)
        assert new_log_dict['id'] != old_log.id
        assert new_log_dict['amount_paid'] == "999.00"
        assert new_log_dict['corrected_from_log_id'] == str(old_log.id)
        
        # Verify old log (from DB)
        await db_session.refresh(old_log)
        assert old_log.status == LogStatusEnum.VOID.value
        
        print(f"--- Successfully corrected log. Old ID: {old_log.id}, New ID: {new_log_dict['id']} ---")
        print("--- New log (API dict) ---")
        pprint(new_log_dict)

    async def test_correct_payment_log_as_parent(
        self,
        payment_log_service: PaymentLogService,
        test_parent_orm: db_models.Users,
        payment_log_orm: db_models.PaymentLogs
    ):
        """Tests that a PARENT is FORBIDDEN from correcting a log."""
        print(f"\n--- Testing correct_payment_log as PARENT for old ID: {payment_log_orm.id} ---")
        
        correction_data = { "amount_paid": 999 } # Dummy data
        
        with pytest.raises(HTTPException) as e:
            await payment_log_service.correct_payment_log(
                payment_log_orm.id, correction_data, test_parent_orm
            )
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

