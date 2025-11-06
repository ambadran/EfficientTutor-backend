import pytest
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
from pprint import pprint
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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
    TEST_PARENT_ID
)


@pytest.mark.anyio
class TestTuitionLogService:

    ### Tests for get_tuition_log_by_id_for_api (Auth) ###

    async def test_get_log_by_id_api_as_owner_teacher(
        self,
        tuition_log_service: TuitionLogService,
        tuition_log_custom: db_models.TuitionLogs, # Get a log
        test_teacher_orm: db_models.Users
    ):
        """Tests that the OWNER (Teacher) can fetch a log."""
        log_id = tuition_log_custom.id
        print(f"\n--- Testing get_log_by_id_for_api as OWNER TEACHER ---")
        
        # Verify test data is correct for this test
        assert tuition_log_custom.teacher_id == test_teacher_orm.id
        
        log_dict = await tuition_log_service.get_tuition_log_by_id_for_api(log_id, test_teacher_orm)
        
        assert isinstance(log_dict, dict)
        assert log_dict['id'] == str(log_id)
        assert log_dict['teacher']['id'] == str(test_teacher_orm.id)
        print("--- Found log (API dict) ---")
        pprint(log_dict)

    async def test_get_log_by_id_api_as_related_parent(
        self,
        tuition_log_service: TuitionLogService,
        tuition_log_custom: db_models.TuitionLogs,
        test_parent_orm: db_models.Users
    ):
        """Tests that a related PARENT can fetch a log."""
        log_id = tuition_log_custom.id
        print(f"\n--- Testing get_log_by_id_for_api as RELATED PARENT ---")
        
        # Verify test data
        assert any(c.parent_id == test_parent_orm.id for c in tuition_log_custom.tuition_log_charges)
        
        log_dict = await tuition_log_service.get_tuition_log_by_id_for_api(log_id, test_parent_orm)
        
        assert isinstance(log_dict, dict)
        assert log_dict['id'] == str(log_id)
        print("--- Found log (API dict) ---")
        pprint(log_dict)

    async def test_get_log_by_id_api_as_related_student(
        self,
        tuition_log_service: TuitionLogService,
        tuition_log_custom: db_models.TuitionLogs,
        test_student_orm: db_models.Users
    ):
        """Tests that a related STUDENT is now FORBIDDEN from fetching a log."""
        log_id = tuition_log_custom.id
        print(f"\n--- Testing get_log_by_id_for_api as RELATED STUDENT (expect 403) ---")
        
        # Verify test data is still valid
        assert any(c.student_id == test_student_orm.id for c in tuition_log_custom.tuition_log_charges)
        
        # --- Act & Assert ---
        with pytest.raises(HTTPException) as e:
            await tuition_log_service.get_tuition_log_by_id_for_api(log_id, test_student_orm)
        
        assert e.value.status_code == 403
        
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    async def test_get_log_by_id_api_as_unrelated_parent(
        self,
        tuition_log_service: TuitionLogService,
        tuition_log_custom: db_models.TuitionLogs,
        test_unrelated_parent_orm: db_models.Users
    ):
        """Tests that an UNRELATED Parent is FORBIDDEN."""
        log_id = tuition_log_custom.id
        print(f"\n--- Testing get_log_by_id_for_api as UNRELATED PARENT ---")
        
        with pytest.raises(HTTPException) as e:
            await tuition_log_service.get_tuition_log_by_id_for_api(log_id, test_unrelated_parent_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised 403 FORBIDDEN ---")

    async def test_get_log_by_id_api_not_found(
        self,
        tuition_log_service: TuitionLogService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that a 404 is raised for a non-existent log."""
        test_id = UUID(int=0)
        with pytest.raises(HTTPException) as e:
            await tuition_log_service.get_tuition_log_by_id_for_api(test_id, test_teacher_orm)
        
        assert e.value.status_code == 404
        print(f"--- Correctly raised 404 NOT FOUND ---")

    ### Tests for get_all_tuition_logs_for_api (Auth) ###

    async def test_get_all_logs_api_as_teacher(
        self,
        tuition_log_service: TuitionLogService,
        test_teacher_orm: db_models.Users
    ):
        """Tests API-formatted output for a Teacher."""
        print(f"\n--- Testing get_all_tuition_logs_for_api as TEACHER '{test_teacher_orm.first_name} {test_teacher_orm.last_name}' ---")
        
        logs = await tuition_log_service.get_all_tuition_logs_for_api(test_teacher_orm)
        
        assert isinstance(logs, list)
        print(f"--- Found {len(logs)} API logs for Teacher ---")
        if len(logs) > 0:
            assert isinstance(logs[0], dict)
            assert 'charges' in logs[0] # Teacher-specific field
            pprint(logs[0])

    async def test_get_all_logs_api_as_parent(
        self,
        tuition_log_service: TuitionLogService,
        test_parent_orm: db_models.Users
    ):
        """Tests API-formatted output for a Parent."""
        print(f"\n--- Testing get_all_tuition_logs_for_api as PARENT '{test_parent_orm.first_name} {test_parent_orm.last_name}'---")
        
        logs = await tuition_log_service.get_all_tuition_logs_for_api(test_parent_orm)
        
        assert isinstance(logs, list)
        print(f"--- Found {len(logs)} API logs for Parent ---")
        if len(logs) > 0:
            assert isinstance(logs[0], dict)
            assert 'cost' in logs[0] # Guardian-specific field
            pprint(logs[0])

    async def test_get_all_logs_api_as_student(
        self,
        tuition_log_service: TuitionLogService,
        test_student_orm: db_models.Users
    ):
        """Tests that a STUDENT is now FORBIDDEN from fetching all logs."""
        print(f"\n--- Testing get_all_tuition_logs_for_api as STUDENT (expect 403) ---")
        
        # --- Act & Assert ---
        with pytest.raises(HTTPException) as e:
            await tuition_log_service.get_all_tuition_logs_for_api(test_student_orm)
        
        assert e.value.status_code == 403

        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    ### Tests for create_tuition_log (Auth) ###

    async def test_create_log_as_teacher(
        self,
        db_session: AsyncSession,
        tuition_log_service: TuitionLogService,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests that a TEACHER can create a log."""
        print(f"\n--- Testing create_tuition_log as TEACHER ---")
        
        log_data = {
            "log_type": TuitionLogCreateTypeEnum.SCHEDULED.value,
            "tuition_id": test_tuition_orm.id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat()
        }
        
        new_log_dict = await tuition_log_service.create_tuition_log(log_data, test_teacher_orm)
        await db_session.commit()
        
        assert isinstance(new_log_dict, dict)
        assert new_log_dict['id'] is not None
        assert new_log_dict['create_type'] == "SCHEDULED"
        print("--- Successfully created SCHEDULED log ---")
        pprint(new_log_dict)

    async def test_create_log_as_parent(
        self,
        tuition_log_service: TuitionLogService,
        test_parent_orm: db_models.Users
    ):
        """Tests that a PARENT is FORBIDDEN from creating a log."""
        print(f"\n--- Testing create_tuition_log as PARENT ---")
        
        log_data = { "log_type": "CUSTOM"} # Dummy data
        
        with pytest.raises(HTTPException) as e:
            await tuition_log_service.create_tuition_log(log_data, test_parent_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised 403 FORBIDDEN ---")

    ### Tests for void_tuition_log (Auth) ###

    async def test_void_log_as_owner_teacher(
        self,
        db_session: AsyncSession,
        tuition_log_service: TuitionLogService,
        test_teacher_orm: db_models.Users,
        tuition_log_custom: db_models.TuitionLogs
    ):
        """Tests that the OWNER (Teacher) can void their log."""
        log_to_void = tuition_log_custom
        print(f"\n--- Testing void_tuition_log as OWNER TEACHER ---")
        
        # Pre-condition
        log_to_void.status = LogStatusEnum.ACTIVE.value
        db_session.add(log_to_void)
        await db_session.commit()
        
        # Act
        success = await tuition_log_service.void_tuition_log(log_to_void.id, test_teacher_orm)
        assert success is True
        
        await db_session.commit()
        await db_session.refresh(log_to_void)
        assert log_to_void.status == LogStatusEnum.VOID.value
        print("--- Successfully voided log ---")

    async def test_void_log_as_unrelated_teacher(
        self,
        tuition_log_service: TuitionLogService,
        test_unrelated_teacher_orm: db_models.Users,
        tuition_log_custom: db_models.TuitionLogs
    ):
        """Tests that an UNRELATED Teacher is FORBIDDEN from voiding a log."""
        print(f"\n--- Testing void_tuition_log as UNRELATED TEACHER ---")
        
        with pytest.raises(HTTPException) as e:
            await tuition_log_service.void_tuition_log(tuition_log_custom.id, test_unrelated_teacher_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised 403 FORBIDDEN ---")

    async def test_void_log_as_parent(
        self,
        tuition_log_service: TuitionLogService,
        test_parent_orm: db_models.Users,
        tuition_log_custom: db_models.TuitionLogs
    ):
        """Tests that a PARENT is FORBIDDEN from voiding a log."""
        print(f"\n--- Testing void_tuition_log as PARENT ---")
        
        with pytest.raises(HTTPException) as e:
            await tuition_log_service.void_tuition_log(tuition_log_custom.id, test_parent_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised 403 FORBIDDEN ---")

    ### Tests for correct_tuition_log (Auth) ###

    async def test_correct_log_as_owner_teacher(
        self,
        db_session: AsyncSession,
        tuition_log_service: TuitionLogService,
        test_teacher_orm: db_models.Users,
        tuition_log_scheduled: db_models.TuitionLogs
    ):
        """Tests that the OWNER (Teacher) can correct their log."""
        old_log = tuition_log_scheduled
        print(f"\n--- Testing correct_tuition_log as OWNER TEACHER ---")
        
        # Pre-condition
        old_log.status = LogStatusEnum.ACTIVE.value
        db_session.add(old_log)
        await db_session.commit()
        
        # Correction data
        correction_data = {
            "log_type": TuitionLogCreateTypeEnum.CUSTOM.value,
            "start_time": old_log.start_time.isoformat(),
            "end_time": old_log.end_time.isoformat(),
            "subject": SubjectEnum.CHEMISTRY.value,
            "lesson_index": 99,
            "charges": [
                {"student_id": c.student_id, "cost": c.cost + 10}
                for c in old_log.tuition_log_charges
            ]
        }
        
        # Act
        new_log_dict = await tuition_log_service.correct_tuition_log(
            old_log.id, correction_data, test_teacher_orm
        )
        await db_session.commit()
        
        # Verify new log
        assert isinstance(new_log_dict, dict)
        assert new_log_dict['id'] != old_log.id
        assert new_log_dict['subject'] == SubjectEnum.CHEMISTRY.value
        
        # Verify old log
        await db_session.refresh(old_log)
        assert old_log.status == LogStatusEnum.VOID.value
        
        print("--- Successfully corrected log ---")
        pprint(new_log_dict)

    async def test_correct_log_as_unrelated_teacher(
        self,
        tuition_log_service: TuitionLogService,
        test_unrelated_teacher_orm: db_models.Users,
        tuition_log_scheduled: db_models.TuitionLogs
    ):
        """Tests that an UNRELATED Teacher is FORBIDDEN from correcting a log."""
        print(f"\n--- Testing correct_tuition_log as UNRELATED TEACHER ---")
        
        correction_data = { "log_type": "CUSTOM"} # Dummy
        
        with pytest.raises(HTTPException) as e:
            await tuition_log_service.correct_tuition_log(
                tuition_log_scheduled.id, correction_data, test_unrelated_teacher_orm
            )
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised 403 FORBIDDEN ---")
