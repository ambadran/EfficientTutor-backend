import pytest
from uuid import UUID
from datetime import datetime, time
from pprint import pprint
from fastapi import HTTPException

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.timetable_service import TimeTableService
from src.efficient_tutor_backend.models import timetable as timetable_models
from tests.constants import (
    TEST_TIMETABLE_RUN_ID, 
    TEST_USER_SOLUTION_ID, 
    TEST_SLOT_ID,
    TEST_TUITION_ID,
    TEST_TUITION_ID_NO_LINK,
    TEST_SLOT_ID_STUDENT_MATH,
    TEST_SLOT_ID_STUDENT_PHYSICS,
    TEST_SLOT_ID_TEACHER_AVAILABILITY,
    TEST_AVAILABILITY_INTERVAL_ID_TEACHER
)

@pytest.mark.anyio
class TestTimeTableService:

    ### Tests for _authorize_view_access ###

    async def test_authorize_self_view(
        self,
        timetable_service: TimeTableService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that a user can always view their own timetable."""
        print(f"\n--- Testing Authorize Self View ({test_teacher_orm.email}) ---")
        target = await timetable_service._authorize_view_access(test_teacher_orm, test_teacher_orm.id)
        assert target.id == test_teacher_orm.id

    async def test_authorize_teacher_viewing_student(
        self,
        timetable_service: TimeTableService,
        test_teacher_orm: db_models.Users,
        test_student_orm: db_models.Users
    ):
        """Tests that a teacher can view a student's timetable."""
        print(f"\n--- Testing Authorize Teacher -> Student ---")
        target = await timetable_service._authorize_view_access(test_teacher_orm, test_student_orm.id)
        assert target.id == test_student_orm.id

    async def test_authorize_teacher_viewing_other_teacher_forbidden(
        self,
        timetable_service: TimeTableService,
        test_teacher_orm: db_models.Users,
        test_unrelated_teacher_orm: db_models.Users
    ):
        """Tests that a teacher CANNOT view another teacher's timetable."""
        print("\n--- Testing Authorize Teacher -> Other Teacher (Forbidden) ---")
        with pytest.raises(HTTPException) as e:
            await timetable_service._authorize_view_access(test_teacher_orm, test_unrelated_teacher_orm.id)
        assert e.value.status_code == 403

    async def test_authorize_parent_viewing_own_child(
        self,
        timetable_service: TimeTableService,
        test_parent_orm: db_models.Users,
        test_student_orm: db_models.Users
    ):
        """Tests that a parent can view their own child's timetable."""
        print(f"\n--- Testing Authorize Parent -> Child ---")
        assert test_student_orm.parent_id == test_parent_orm.id
        target = await timetable_service._authorize_view_access(test_parent_orm, test_student_orm.id)
        assert target.id == test_student_orm.id

    async def test_authorize_parent_viewing_unrelated_student_forbidden(
        self,
        timetable_service: TimeTableService,
        test_parent_orm: db_models.Users,
        test_unrelated_student_orm: db_models.Users 
    ):
        """Tests that a parent CANNOT view an unrelated student."""
        print(f"\n--- Testing Authorize Parent -> Unrelated Student (Forbidden) ---")
        with pytest.raises(HTTPException) as e:
            await timetable_service._authorize_view_access(test_parent_orm, test_unrelated_student_orm.id)
        assert e.value.status_code == 403

    ### Tests for get_timetable_for_api ###

    async def test_get_timetable_for_student_viewing_self(
        self,
        timetable_service: TimeTableService,
        test_student_orm: db_models.Users
    ):
        """
        Tests a Student viewing their own timetable.
        Expects 2 Tuition slots (Math, Physics).
        """
        print(f"\n--- Testing Student ({test_student_orm.email}) viewing Self ---")
        
        slots = await timetable_service.get_timetable_for_api(
            current_user=test_student_orm,
            target_user_id=test_student_orm.id
        )
        
        print(f"Found {len(slots)} slots.")
        for slot in slots:
            pprint(slot.model_dump())
        
        assert len(slots) == 2
        
        # Verify Math Slot
        math_slot = next((s for s in slots if s.id == TEST_SLOT_ID_STUDENT_MATH), None)
        assert math_slot is not None
        assert math_slot.name == "Math Session"
        assert math_slot.slot_type == timetable_models.TimeTableSlotType.TUITION
        assert math_slot.object_uuid == TEST_TUITION_ID
        assert math_slot.user_id == test_student_orm.id # Check user_id

        # Verify Physics Slot
        physics_slot = next((s for s in slots if s.id == TEST_SLOT_ID_STUDENT_PHYSICS), None)
        assert physics_slot is not None
        assert physics_slot.name == "Physics Session"
        assert physics_slot.slot_type == timetable_models.TimeTableSlotType.TUITION
        assert physics_slot.object_uuid == TEST_TUITION_ID_NO_LINK
        assert physics_slot.user_id == test_student_orm.id # Check user_id

    async def test_get_timetable_for_teacher_viewing_self(
        self,
        timetable_service: TimeTableService,
        test_teacher_orm: db_models.Users
    ):
        """
        Tests a Teacher viewing their own timetable.
        Expects 3 slots: Math (Tuition), Physics (Tuition), Work (Availability).
        """
        print(f"\n--- Testing Teacher ({test_teacher_orm.email}) viewing Self ---")
        
        slots = await timetable_service.get_timetable_for_api(
            current_user=test_teacher_orm,
            target_user_id=test_teacher_orm.id
        )
        
        print(f"Found {len(slots)} slots.")
        assert len(slots) == 3
        
        # Verify Availability Slot
        avail_slot = next((s for s in slots if s.id == TEST_SLOT_ID_TEACHER_AVAILABILITY), None)
        assert avail_slot is not None
        assert avail_slot.name == "Work"
        assert avail_slot.slot_type == timetable_models.TimeTableSlotType.AVAILABILITY
        assert avail_slot.object_uuid == TEST_AVAILABILITY_INTERVAL_ID_TEACHER
        assert avail_slot.user_id == test_teacher_orm.id # Check user_id

    async def test_get_timetable_for_teacher_viewing_student(
        self,
        timetable_service: TimeTableService,
        test_teacher_orm: db_models.Users,
        test_student_orm: db_models.Users
    ):
        """
        Tests a Teacher viewing a Student.
        Teacher should see details for slots where they are a participant.
        """
        print(f"\n--- Testing Teacher ({test_teacher_orm.email}) viewing Student ({test_student_orm.email}) ---")
        
        slots = await timetable_service.get_timetable_for_api(
            current_user=test_teacher_orm,
            target_user_id=test_student_orm.id
        )
        
        assert len(slots) == 2
        
        math_slot = next((s for s in slots if s.id == TEST_SLOT_ID_STUDENT_MATH), None)
        assert math_slot.name == "Math Session" # Unmasked
        assert math_slot.object_uuid == TEST_TUITION_ID
        assert math_slot.user_id == test_student_orm.id # Slot belongs to the target (Student)

    async def test_get_timetable_masking_for_unrelated_teacher(
        self,
        timetable_service: TimeTableService,
        test_unrelated_teacher_orm: db_models.Users,
        test_student_orm: db_models.Users
    ):
        """
        Tests a Teacher viewing a Student where the teacher is NOT a participant.
        Slots should be masked.
        """
        print(f"\n--- Testing Unrelated Teacher viewing Student (Masking) ---")
        
        slots = await timetable_service.get_timetable_for_api(
            current_user=test_unrelated_teacher_orm,
            target_user_id=test_student_orm.id
        )
        
        assert len(slots) == 2
        
        for slot in slots:
            assert slot.name == "Others"
            assert slot.object_uuid is None
            assert slot.slot_type == timetable_models.TimeTableSlotType.OTHER
            assert slot.user_id == test_student_orm.id # Even masked slots belong to the student

    async def test_get_timetable_for_parent_viewing_child(
        self,
        timetable_service: TimeTableService,
        test_parent_orm: db_models.Users,
        test_student_orm: db_models.Users
    ):
        """
        Tests a Parent viewing their Child.
        Parent should see everything unmasked (Parent Proxy logic).
        """
        print(f"\n--- Testing Parent viewing Child (Proxy) ---")
        
        slots = await timetable_service.get_timetable_for_api(
            current_user=test_parent_orm,
            target_user_id=test_student_orm.id
        )
        
        assert len(slots) == 2
        math_slot = next((s for s in slots if s.id == TEST_SLOT_ID_STUDENT_MATH), None)
        assert math_slot.name == "Math Session" # Unmasked
        assert math_slot.object_uuid == TEST_TUITION_ID
        assert math_slot.user_id == test_student_orm.id # Slot belongs to child

    async def test_date_calculation_timezone(
        self,
        timetable_service: TimeTableService
    ):
        """
        Tests the _calculate_next_occurrence logic directly.
        """
        print(f"\n--- Testing Date Calculation ---")
        
        day_of_week = 1 
        start_time = time(10, 0)
        end_time = time(11, 0)
        timezone_str = "UTC"
        
        start_dt, end_dt = timetable_service._calculate_next_occurrence(
            day_of_week, start_time, end_time, timezone_str
        )
        
        assert start_dt.time() == start_time
        assert start_dt.weekday() == 0
        assert start_dt.tzinfo is not None