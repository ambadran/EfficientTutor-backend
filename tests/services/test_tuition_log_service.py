import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal
from pprint import pprint

# --- Import models, services, and Pydantic models ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.finance_service import TuitionLogService
from src.efficient_tutor_backend.models import finance as finance_models
from src.efficient_tutor_backend.database.db_enums import (
    TuitionLogCreateTypeEnum, 
    SubjectEnum,
    PaidStatus,
    LogStatusEnum
)

# --- Import Test Constants ---
from tests.constants import (
    TEST_TEACHER_ID, 
    TEST_STUDENT_ID, 
    TEST_PARENT_ID, 
    TEST_TUITION_ID
)


@pytest.mark.anyio
class TestTuitionLogService:

    ### Tests for get_tuition_log_by_id ###

    async def test_get_tuition_log_by_id(
        self,
        tuition_log_service: TuitionLogService,
        tuition_log_scheduled: db_models.TuitionLogs  # <-- Use new fixture
    ):
        """Tests fetching a single, fully-loaded tuition log."""
        log_id = tuition_log_scheduled.id
        print(f"\n--- Testing get_tuition_log_by_id for ID: {log_id} ---")
        
        log = await tuition_log_service.get_tuition_log_by_id(log_id)
        
        assert log is not None
        assert log.id == log_id
        
        # --- Logging ---
        print("--- Found log (raw) ---")
        pprint(log.__dict__)
        print("--- Log charges (raw) ---")
        pprint(log.tuition_log_charges[0].__dict__)
        # --- End Logging ---

    async def test_get_tuition_log_by_id_not_found(
        self,
        tuition_log_service: TuitionLogService
    ):
        """Tests that a 404 HTTPException is raised for a non-existent log ID."""
        test_id = UUID(int=0)  # A random, non-existent UUID
        print(f"\n--- Testing get_tuition_log_by_id for non-existent ID: {test_id} ---")
        
        # Use pytest.raises to catch the expected exception
        with pytest.raises(HTTPException) as e:
            await tuition_log_service.get_tuition_log_by_id(test_id)
        
        # Check that the exception has the correct status code
        assert e.value.status_code == 404
        
        # --- Logging ---
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")
        # --- End Logging ---

    ### Tests for get_all_tuition_logs (by role) ###
    async def test_get_all_logs_as_teacher(
        self,
        tuition_log_service: TuitionLogService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that a TEACHER gets all relevant tuition logs."""
        print(f"\n--- Testing get_all_tuition_logs as TEACHER ({test_teacher_orm.first_name}) ---")
        
        logs = await tuition_log_service.get_all_tuition_logs(test_teacher_orm)
        
        assert isinstance(logs, list)
        print(f"\n--- Found {len(logs)} logs for Teacher ---")
        if len(logs) > 0:
            assert all(log.teacher_id == test_teacher_orm.id for log in logs)

            print(f"\nHere is the raw {type(logs[0])}:")
            pprint(logs[0].__dict__)
            print("\nHere is the logs[0].tuition_log_charges[0]:")
            pprint(logs[0].tuition_log_charges[0].__dict__)

    async def test_get_all_logs_as_parent(
        self,
        tuition_log_service: TuitionLogService,
        test_parent_orm: db_models.Users
    ):
        """Tests that a PARENT gets all relevant tuition logs."""
        print(f"\n--- Testing get_all_tuition_logs as PARENT ({test_parent_orm.first_name}) ---")
        
        logs = await tuition_log_service.get_all_tuition_logs(test_parent_orm)
        
        assert isinstance(logs, list)
        print(f"--- Found {len(logs)} logs for Parent ---")
        if len(logs) > 0:
            # Check that at least one charge in one log belongs to this parent
            assert any(charge.parent_id == test_parent_orm.id 
                       for log in logs for charge in log.tuition_log_charges)

            print(f"\nHere is the raw {type(logs[0])}:")
            pprint(logs[0].__dict__)
            print("\nHere is the logs[0].tuition_log_charges[0]:")
            pprint(logs[0].tuition_log_charges[0].__dict__)

    async def test_get_all_logs_as_student(
        self,
        tuition_log_service: TuitionLogService,
        test_student_orm: db_models.Users
    ):
        """Tests that a STUDENT gets all relevant tuition logs."""
        print(f"\n--- Testing get_all_tuition_logs as STUDENT ({test_student_orm.first_name}) ---")
        
        logs = await tuition_log_service.get_all_tuition_logs(test_student_orm)
        
        assert isinstance(logs, list)
        print(f"--- Found {len(logs)} logs for Student ---")
        if len(logs) > 0:
            # Check that at least one charge in one log belongs to this student
            assert any(charge.student_id == test_student_orm.id 
                       for log in logs for charge in log.tuition_log_charges)
            print(f"\nHere is the raw {type(logs[0])}:")
            pprint(logs[0].__dict__)
            print("\nHere is the logs[0].tuition_log_charges[0]:")
            pprint(logs[0].tuition_log_charges[0].__dict__)

    ### Tests for create_tuition_log ###

    async def test_create_log_scheduled(
        self,
        tuition_log_service: TuitionLogService,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
        ):
        """Tests creating a new tuition log from a SCHEDULED template."""
        print(f"\n--- Testing create_tuition_log (SCHEDULED) ---")
        
        # --- FIX ---
        # We now instantiate the specific 'ScheduledLogInput' model.
        log_data = {
            "log_type": TuitionLogCreateTypeEnum.SCHEDULED.value,
            "tuition_id": test_tuition_orm.id,
            "start_time": datetime.now(),
            "end_time": datetime.now()
        }
        # -----------
        
        new_log = await tuition_log_service.create_tuition_log(log_data, test_teacher_orm)
        
        assert new_log is not None
        assert new_log["id"] is not None
        assert new_log["create_type"] == TuitionLogCreateTypeEnum.SCHEDULED.value
        assert new_log["tuition_id"] == str(test_tuition_orm.id)
        
        print(f"--- Successfully created SCHEDULED log ID: {new_log['id']} ---")
        pprint(new_log)

    async def test_create_log_custom(
        self,
        tuition_log_service: TuitionLogService,
        test_teacher_orm: db_models.Users,
        test_student_orm: db_models.Students
    ):
        """Tests creating a new CUSTOM tuition log."""
        print(f"\n--- Testing create_tuition_log (CUSTOM) ---")
        
        # --- FIX ---
        # We instantiate 'CustomLogInput' and have removed 'teacher_id'.
        log_data = finance_models.CustomLogInput(
            log_type=TuitionLogCreateTypeEnum.CUSTOM.value, # Must use .value
            start_time=datetime.now(),
            end_time=datetime.now(),
            subject=SubjectEnum.PHYSICS,
            lesson_index=1,
            charges=[
                finance_models.CustomTuitionChargeInput(
                    student_id=test_student_orm.id, 
                    cost=Decimal("10.00")
                )
            ]
        )
        # -----------
        
        # The service now gets the teacher from the authenticated 'current_user'
        new_log = await tuition_log_service.create_tuition_log(log_data, test_teacher_orm)

        print(f"--- Successfully created CUSTOM log ID: {new_log["id"]} ---")
        pprint(new_log)

        assert new_log is not None
        assert new_log["id"] is not None
        assert new_log["create_type"] == TuitionLogCreateTypeEnum.CUSTOM.value
        assert new_log["subject"] == SubjectEnum.PHYSICS.value
        # Check that the teacher_id was correctly assigned from current_user
        assert new_log["teacher"]["id"] == str(test_teacher_orm.id)
        assert len(new_log["charges"]) == 1
        assert new_log["charges"][0]["student_id"] == str(test_student_orm.id)

    ### Tests for void_tuition_log ###

    async def test_void_tuition_log(
        self,
        db_session: AsyncSession,
        tuition_log_service: TuitionLogService,
        test_teacher_orm: db_models.Users,
        tuition_log_custom: db_models.TuitionLogs # Using the 'custom' fixture
    ):
        """Tests voiding an active tuition log."""
        log_to_void = tuition_log_custom
        log_to_void_id = log_to_void.id
        print(f"\n--- Testing void_tuition_log for ID: {log_to_void_id} ---")
        
        # --- Pre-condition: Ensure log is ACTIVE ---
        # This is crucial so the test is repeatable.
        log_to_void.status = LogStatusEnum.ACTIVE.value
        db_session.add(log_to_void)
        await db_session.commit()
        await db_session.refresh(log_to_void)
        
        assert log_to_void.status == LogStatusEnum.ACTIVE.value
        print(f"--- Pre-condition: Log {log_to_void_id} set to ACTIVE ---")
        
        # --- Act ---
        success = await tuition_log_service.void_tuition_log(log_to_void_id, test_teacher_orm)
        assert success is True

        # Commit the work done by the service
        await db_session.commit()

        # --- Verify ---
        await db_session.refresh(log_to_void) # Refresh from DB
        assert log_to_void.status == LogStatusEnum.VOID.value
        
        print(f"--- Successfully voided log. Final Status: {log_to_void.status} ---")

    ### Tests for correct_tuition_log ###
    async def test_correct_tuition_log(
        self,
        db_session: AsyncSession,
        tuition_log_service: TuitionLogService,
        test_teacher_orm: db_models.Users,
        tuition_log_scheduled: db_models.TuitionLogs
        ):
        """Tests correcting a log (voids old, creates new)."""
        old_log = tuition_log_scheduled
        old_log_id = old_log.id
        print(f"\n--- Testing correct_tuition_log for old ID: {old_log_id} ---")

        # --- Pre-condition: Ensure log is ACTIVE ---
        old_log.status = LogStatusEnum.ACTIVE.value
        db_session.add(old_log)
        await db_session.commit()
        await db_session.refresh(old_log)
        
        assert old_log.status == LogStatusEnum.ACTIVE.value
        print(f"--- Pre-condition: Log {old_log_id} set to ACTIVE ---")

        # --- Correction data ---
        correction_data = finance_models.CustomLogInput(
            log_type=TuitionLogCreateTypeEnum.CUSTOM.value,
            start_time=old_log.start_time,
            end_time=old_log.end_time,
            subject=SubjectEnum.CHEMISTRY,  # <-- The correction
            lesson_index=99,                # <-- The correction
            charges=[
                finance_models.CustomTuitionChargeInput(
                    student_id=c.student_id, 
                    cost=c.cost + 10 # Corrected cost
                ) for c in old_log.tuition_log_charges
            ]
        )
        
        # --- Act ---
        new_log = await tuition_log_service.correct_tuition_log(
            old_log_id, correction_data, test_teacher_orm
        )

        # --- THE FIX ---
        # Commit the work done by the service (voiding old, creating new)
        await db_session.commit()
        # ---------------

        # --- Verify new log ---
        # We refresh the new log to make sure it was committed correctly
        assert new_log is not None
        assert new_log["id"] != str(old_log_id)
        assert new_log["subject"] == SubjectEnum.CHEMISTRY.value
        assert new_log["lesson_index"] == 99
        assert new_log["corrected_from_log_id"] == str(old_log_id)
        
        # --- Verify old log ---
        await db_session.refresh(old_log) # Refresh from DB
        assert old_log.status == LogStatusEnum.VOID.value
        
        print(f"--- Successfully corrected log. Old ID: {old_log_id}, New ID: {new_log["id"]} ---")
        print("--- Old log (raw) ---")
        pprint(old_log.__dict__)
        print("--- New log (raw) ---")
        pprint(new_log)

    ### Tests for get_all_tuition_logs_for_api ###

    async def test_get_all_logs_api_as_teacher(
        self,
        tuition_log_service: TuitionLogService,
        test_teacher_orm: db_models.Users
    ):
        """Tests the API-formatted output for a Teacher."""
        print(f"\n--- Testing get_all_tuition_logs_for_api as TEACHER ---")
        
        logs = await tuition_log_service.get_all_tuition_logs_for_api(test_teacher_orm)
        
        assert isinstance(logs, list)
        print(f"--- Found {len(logs)} API logs for Teacher ---")
        if len(logs) > 0:
            assert isinstance(logs[0], dict)
            print("--- Example API log (dict) ---")
            pprint(logs[0])

    async def test_get_all_logs_api_as_parent(
        self,
        tuition_log_service: TuitionLogService,
        test_parent_orm: db_models.Users
    ):
        """Tests the API-formatted output for a Parent."""
        print(f"\n--- Testing get_all_tuition_logs_for_api as PARENT ---")
        
        logs = await tuition_log_service.get_all_tuition_logs_for_api(test_parent_orm)
        
        assert isinstance(logs, list)
        print(f"--- Found {len(logs)} API logs for Parent ---")
        if len(logs) > 0:
            assert isinstance(logs[0], dict)
            print("--- Example API log (dict) ---")
            pprint(logs[0])

    async def test_get_all_logs_api_as_student(
        self,
        tuition_log_service: TuitionLogService,
        test_student_orm: db_models.Users
    ):
        """Tests the API-formatted output for a Student."""
        print(f"\n--- Testing get_all_tuition_logs_for_api as STUDENT ---")
        
        logs = await tuition_log_service.get_all_tuition_logs_for_api(test_student_orm)
        
        assert isinstance(logs, list)
        print(f"--- Found {len(logs)} API logs for Student ---")
        if len(logs) > 0:
            assert isinstance(logs[0], dict)
            print("--- Example API log (dict) ---")
            pprint(logs[0])


    ### Tests for _get_paid_statuses_for_parents ###

    async def test_get_paid_statuses(
        self,
        tuition_log_service: TuitionLogService,
        test_parent_orm: db_models.Users
    ):
        """Tests the FIFO paid status calculation."""
        parent_id_list = [test_parent_orm.id]
        print(f"\n--- Testing _get_paid_statuses_for_parents for IDs: {parent_id_list} ---")
        
        statuses = await tuition_log_service._get_paid_statuses_for_parents(parent_id_list)
        
        assert isinstance(statuses, dict)
        print(f"--- Found {len(statuses)} status entries ---")
        
        if len(statuses) > 0:
            first_key = list(statuses.keys())[0]
            assert isinstance(first_key, UUID)
            assert isinstance(statuses[first_key], PaidStatus)
            
            print("--- Full paid status dictionary (raw) ---")
            pprint(statuses)
