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
    TEST_PAYMENT_LOG_ID, # Assumes this is in your constants.py
    TEST_UNRELATED_PARENT_ID,
    TEST_UNRELATED_TEACHER_ID,
    TEST_PAYMENT_LOG_ID_SAME_TEACHER_DIFF_PARENT,
    TEST_PAYMENT_LOG_ID_SAME_PARENT_DIFF_TEACHER,
    TEST_PAYMENT_LOG_ID_UNRELATED
)


@pytest.mark.anyio
class TestPaymentLogServiceRead:

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
        assert isinstance(logs[0], finance_models.PaymentLogRead)
        assert test_teacher_orm.first_name in logs[0].teacher_name
        print("--- Example API log (raw dict) ---")
        pprint(logs[0].__dict__)

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
        assert isinstance(logs[0], finance_models.PaymentLogRead)
        assert test_parent_orm.first_name in logs[0].parent_name
        print("--- Example API log (raw dict) ---")
        pprint(logs[0].__dict__)

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
        
        log = await payment_log_service.get_payment_log_by_id_for_api(log_id, test_teacher_orm)
        
        assert isinstance(log, finance_models.PaymentLogRead)
        assert log.id == log_id
        print("--- Found log (API dict) ---")
        pprint(log.__dict__)

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
        
        log = await payment_log_service.get_payment_log_by_id_for_api(log_id, test_parent_orm)
        
        assert isinstance(log, finance_models.PaymentLogRead)
        assert log.id == log_id
        print("--- Found log (API dict) ---")
        pprint(log.__dict__)

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


@pytest.mark.anyio
class TestPaymentLogServiceWrite:

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
        
        new_log = await payment_log_service.create_payment_log(log_data, test_teacher_orm)
        await db_session.flush() # flush the creation
        
        assert new_log is not None
        assert isinstance(new_log, finance_models.PaymentLogRead)
        assert new_log.id is not None
        assert new_log.amount_paid == Decimal("100.00")
        assert new_log.parent_name == f"{test_parent_orm.first_name} {test_parent_orm.last_name}"
        
        print(f"--- Successfully created payment log (API dict) ---")
        pprint(new_log.__dict__)

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
        await db_session.flush()
        await db_session.refresh(log_to_void)
        assert log_to_void.status == LogStatusEnum.ACTIVE.value
        
        # Act
        success = await payment_log_service.void_payment_log(log_to_void.id, test_teacher_orm)
        assert success is True
        
        await db_session.flush() # flush the void
        
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
        await db_session.flush()
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
        new_log = await payment_log_service.correct_payment_log(
            old_log.id, correction_data, test_teacher_orm
        )
        
        await db_session.flush() # flush the correction
        
        # Verify new log (from returned dict)
        assert isinstance(new_log, finance_models.PaymentLogRead)
        assert new_log.id != old_log.id
        assert new_log.amount_paid == Decimal("999.00")
        assert new_log.corrected_from_log_id == old_log.id
        
        # Verify old log (from DB)
        await db_session.refresh(old_log)
        assert old_log.status == LogStatusEnum.VOID.value
        
        print(f"--- Successfully corrected log. Old ID: {old_log.id}, New ID: {new_log.id} ---")
        print("--- New log (API dict) ---")
        pprint(new_log)

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

    async def test_create_payment_log_with_nonexistent_parent(
        self,
        payment_log_service: PaymentLogService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that creating a payment log with a non-existent parent_id raises a 404."""
        print(f"\n--- Testing create_payment_log with non-existent parent_id ---")
        
        non_existent_parent_id = UUID("00000000-0000-0000-0000-000000000001") # A UUID that should not exist
        
        log_data = {
            "parent_id": non_existent_parent_id,
            "teacher_id": test_teacher_orm.id,
            "amount_paid": Decimal("50.00"),
            "payment_date": datetime.now(timezone.utc).isoformat(),
            "notes": "Attempt to create with non-existent parent"
        }
        
        with pytest.raises(HTTPException) as e:
            await payment_log_service.create_payment_log(log_data, test_teacher_orm)
        
        assert e.value.status_code == 404
        assert "Parent not found" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")


@pytest.mark.anyio
class TestPaymentLogServiceReadFilter:
    """
    Tests for the new filtering functionality in get_all_payment_logs.
    Testing Combinations:
    Teacher -> Parent, Unrelated Parent
    Parent -> Teacher, Unrelated Teacher
    Student -> Forbidden
    """

    # --- TEACHER FILTERING ---

    async def test_get_all_payments_orm_by_teacher_for_parent(
        self,
        payment_log_service: PaymentLogService,
        test_teacher_orm: db_models.Users
    ):
        """Test Teacher filtering by a Parent."""
        logs = await payment_log_service.get_all_payment_logs(
            current_user=test_teacher_orm,
            target_parent_id=TEST_PARENT_ID
        )
        
        log_ids = {log.id for log in logs}
        assert TEST_PAYMENT_LOG_ID in log_ids
        assert TEST_PAYMENT_LOG_ID_SAME_TEACHER_DIFF_PARENT not in log_ids
        print(f"Teacher filtered by Parent successfully.")

    async def test_get_all_payments_orm_by_teacher_for_unrelated_parent(
        self,
        payment_log_service: PaymentLogService,
        test_teacher_orm: db_models.Users
    ):
        """Test Teacher filtering by an Unrelated Parent (who has a log with this teacher)."""
        logs = await payment_log_service.get_all_payment_logs(
            current_user=test_teacher_orm,
            target_parent_id=TEST_UNRELATED_PARENT_ID
        )
        
        log_ids = {log.id for log in logs}
        assert TEST_PAYMENT_LOG_ID_SAME_TEACHER_DIFF_PARENT in log_ids
        assert TEST_PAYMENT_LOG_ID not in log_ids
        print(f"Teacher filtered by Unrelated Parent successfully.")

    async def test_get_all_payments_orm_by_teacher_for_teacher_self(
        self,
        payment_log_service: PaymentLogService,
        test_teacher_orm: db_models.Users
    ):
        """Test Teacher filtering by Self (Should return all their logs)."""
        logs = await payment_log_service.get_all_payment_logs(
            current_user=test_teacher_orm,
            target_teacher_id=TEST_TEACHER_ID
        )
        
        log_ids = {log.id for log in logs}
        assert TEST_PAYMENT_LOG_ID in log_ids
        assert TEST_PAYMENT_LOG_ID_SAME_TEACHER_DIFF_PARENT in log_ids
        # Should exclude logs owned by other teachers
        assert TEST_PAYMENT_LOG_ID_UNRELATED not in log_ids
        print("Teacher filtered by Self successfully.")

    async def test_get_all_payments_orm_by_teacher_for_teacher_other(
        self,
        payment_log_service: PaymentLogService,
        test_teacher_orm: db_models.Users
    ):
        """Test Teacher filtering by Other Teacher (Should return empty)."""
        logs = await payment_log_service.get_all_payment_logs(
            current_user=test_teacher_orm,
            target_teacher_id=TEST_UNRELATED_TEACHER_ID
        )
        
        assert len(logs) == 0
        print("Teacher filtered by Other Teacher returned 0 logs as expected.")

    # --- PARENT FILTERING ---

    async def test_get_all_payments_orm_by_parent_for_teacher(
        self,
        payment_log_service: PaymentLogService,
        test_parent_orm: db_models.Users
    ):
        """Test Parent filtering by Teacher."""
        logs = await payment_log_service.get_all_payment_logs(
            current_user=test_parent_orm,
            target_teacher_id=TEST_TEACHER_ID
        )
        
        log_ids = {log.id for log in logs}
        assert TEST_PAYMENT_LOG_ID in log_ids
        assert TEST_PAYMENT_LOG_ID_SAME_PARENT_DIFF_TEACHER not in log_ids
        print("Parent filtered by Teacher successfully.")

    async def test_get_all_payments_orm_by_parent_for_unrelated_teacher(
        self,
        payment_log_service: PaymentLogService,
        test_parent_orm: db_models.Users
    ):
        """Test Parent filtering by Unrelated Teacher (who has a log with this parent)."""
        logs = await payment_log_service.get_all_payment_logs(
            current_user=test_parent_orm,
            target_teacher_id=TEST_UNRELATED_TEACHER_ID
        )
        
        log_ids = {log.id for log in logs}
        assert TEST_PAYMENT_LOG_ID_SAME_PARENT_DIFF_TEACHER in log_ids
        assert TEST_PAYMENT_LOG_ID not in log_ids
        print("Parent filtered by Unrelated Teacher successfully.")

    async def test_get_all_payments_orm_by_parent_for_parent_other(
        self,
        payment_log_service: PaymentLogService,
        test_parent_orm: db_models.Users
    ):
        """Test Parent filtering by Other Parent (Should return empty)."""
        logs = await payment_log_service.get_all_payment_logs(
            current_user=test_parent_orm,
            target_parent_id=TEST_UNRELATED_PARENT_ID
        )
        
        assert len(logs) == 0
        print("Parent filtered by Other Parent returned 0 logs as expected.")

    # --- STUDENT FILTERING ---

    async def test_get_all_payments_orm_as_student_forbidden(
        self,
        payment_log_service: PaymentLogService,
        test_student_orm: db_models.Users
    ):
        """Test Student attempt to get all logs (Forbidden)."""
        with pytest.raises(HTTPException) as e:
            await payment_log_service.get_all_payment_logs(
                current_user=test_student_orm
            )
        
        assert e.value.status_code == 403
        print("Student was correctly forbidden from fetching payment logs.")

