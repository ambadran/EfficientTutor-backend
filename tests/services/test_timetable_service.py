import pytest
from uuid import UUID
from datetime import datetime
from pprint import pprint

# --- Import models, services, and the dataclass ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.timetable_service import (
    TimeTableService, 
    ScheduledTuition
)
from src.efficient_tutor_backend.models import timetable as timetable_models


@pytest.mark.anyio
class TestTimeTableService:

    ### Tests for _get_latest_solution_data (private) ###

    async def test_get_latest_solution_data(
        self,
        timetable_service: TimeTableService
    ):
        """
        Tests that the private _get_latest_solution_data method can
        successfully fetch a timetable run from the database.
        """
        print("\n--- Testing _get_latest_solution_data ---")
        
        data = await timetable_service._get_latest_solution_data()
        
        # This test assumes your test DB has at least one successful run.
        # If it doesn't, data being None is also a valid test.
        assert data is not None
        assert isinstance(data, list)
        assert len(data) > 0
        
        # --- Logging ---
        print(f"--- Found solution data with {len(data)} entries ---")
        print("--- Example solution entry (raw) ---")
        pprint(data[20])
        # --- End Logging ---

    ### Tests for get_all (core logic) ###

    async def test_get_all_as_teacher(
        self,
        timetable_service: TimeTableService,
        test_teacher_orm: db_models.Users
    ):
        """Tests the core get_all logic for a Teacher."""
        print(f"\n--- Testing get_all for TEACHER ({test_teacher_orm.first_name}) ---")
        
        scheduled_tuitions = await timetable_service.get_all(current_user=test_teacher_orm)
        
        assert isinstance(scheduled_tuitions, list)
        print(f"--- Found {len(scheduled_tuitions)} relevant scheduled tuitions for Teacher ---")
        
        if len(scheduled_tuitions) > 0:
            assert isinstance(scheduled_tuitions[0], ScheduledTuition)
            # --- Logging ---
            print("--- Example ScheduledTuition dataclass (raw) ---")
            pprint(scheduled_tuitions[0])
            # --- End Logging ---

    async def test_get_all_as_parent(
        self,
        timetable_service: TimeTableService,
        test_parent_orm: db_models.Users
    ):
        """Tests the core get_all logic for a Parent."""
        print(f"\n--- Testing get_all for PARENT ({test_parent_orm.first_name}) ---")
        
        scheduled_tuitions = await timetable_service.get_all(current_user=test_parent_orm)
        
        assert isinstance(scheduled_tuitions, list)
        print(f"--- Found {len(scheduled_tuitions)} relevant scheduled tuitions for Parent ---")
        
        if len(scheduled_tuitions) > 0:
            assert isinstance(scheduled_tuitions[0], ScheduledTuition)
            # --- Logging ---
            print("--- Example ScheduledTuition dataclass (raw) ---")
            pprint(scheduled_tuitions[0])
            # --- End Logging ---

    async def test_get_all_as_student(
        self,
        timetable_service: TimeTableService,
        test_student_orm: db_models.Users
    ):
        """Tests the core get_all logic for a Student."""
        print(f"\n--- Testing get_all for Student ({test_student_orm.first_name}) ---")
        
        scheduled_tuitions = await timetable_service.get_all(current_user=test_student_orm)
        
        assert isinstance(scheduled_tuitions, list)
        print(f"--- Found {len(scheduled_tuitions)} relevant scheduled tuitions for Student ---")
        
        if len(scheduled_tuitions) > 0:
            assert isinstance(scheduled_tuitions[0], ScheduledTuition)
            # --- Logging ---
            print("--- Example ScheduledTuition dataclass (raw) ---")
            pprint(scheduled_tuitions[0])
            # --- End Logging ---


    ### Tests for get_all_for_api (public) ###

    async def test_get_all_for_api_as_teacher(
        self,
        timetable_service: TimeTableService,
        test_teacher_orm: db_models.Users
    ):
        """Tests the public API formatter for a Teacher."""
        print(f"\n--- Testing get_all_for_api for TEACHER ({test_teacher_orm.first_name}) ---")
        
        api_data = await timetable_service.get_all_for_api(current_user=test_teacher_orm)
        
        assert isinstance(api_data, list)
        print(f"--- Found {len(api_data)} API-formatted tuitions for Teacher ---")
        
        if len(api_data) > 0:
            assert isinstance(api_data[0], timetable_models.ScheduledTuitionReadForTeacher)
            # --- Logging ---
            print("--- Example Pydantic model (raw) ---")
            pprint(api_data[0].model_dump())  # Use .model_dump() for Pydantic
            # --- End Logging ---

    async def test_get_all_for_api_as_parent(
        self,
        timetable_service: TimeTableService,
        test_parent_orm: db_models.Users
    ):
        """Tests the public API formatter for a Guardian (Parent)."""
        print(f"\n--- Testing get_all_for_api for PARENT ({test_parent_orm.first_name}) ---")
        
        api_data = await timetable_service.get_all_for_api(current_user=test_parent_orm)
        
        assert isinstance(api_data, list)
        print(f"--- Found {len(api_data)} API-formatted tuitions for Parent ---")
        
        if len(api_data) > 0:
            assert isinstance(api_data[0], timetable_models.ScheduledTuitionReadForGuardian)
            # --- Logging ---
            print("--- Example Pydantic model (raw) ---")
            pprint(api_data[0].model_dump())
            # --- End Logging ---

    async def test_get_all_for_api_as_student(
        self,
        timetable_service: TimeTableService,
        test_student_orm: db_models.Users
    ):
        """Tests the public API formatter for a Guardian (Student)."""
        print(f"\n--- Testing get_all_for_api for STUDENT ({test_student_orm.first_name}) ---")
        
        api_data = await timetable_service.get_all_for_api(current_user=test_student_orm)
        
        assert isinstance(api_data, list)
        print(f"--- Found {len(api_data)} API-formatted tuitions for Student ---")
        
        if len(api_data) > 0:
            assert isinstance(api_data[0], timetable_models.ScheduledTuitionReadForGuardian)
            # --- Logging ---
            print("--- Example Pydantic model (raw) ---")
            pprint(api_data[0].model_dump())
            # --- End Logging ---


    ### Tests for _format_for_teacher_api (sync utility) ###
    
    def test_format_for_teacher_api(
        self,
        timetable_service_sync: TimeTableService, # Use the sync fixture
        test_tuition_orm: db_models.Tuitions      # Get a real tuition
    ):
        """Tests the synchronous teacher-formatting utility."""
        print("\n--- Testing _format_for_teacher_api (sync) ---")
        
        # 1. Create a dummy ScheduledTuition dataclass
        dummy_schedule = ScheduledTuition(
            tuition=test_tuition_orm,
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        # 2. Call the sync method
        formatted = timetable_service_sync._format_for_teacher_api(dummy_schedule)
        
        # 3. Assert
        assert isinstance(formatted, timetable_models.ScheduledTuitionReadForTeacher)
        assert formatted.tuition_id == test_tuition_orm.id
        
        # --- Logging ---
        print("--- Successfully formatted data for Teacher view (raw) ---")
        pprint(formatted.model_dump())
        # --- End Logging ---

    ### Tests for _format_for_guardian_api (sync utility) ###

    def test_format_for_guardian_api(
        self,
        timetable_service_sync: TimeTableService, # Use the sync fixture
        test_tuition_orm: db_models.Tuitions,     # Get a real tuition
        test_parent_orm: db_models.Users          # Get a real parent
    ):
        """Tests the synchronous guardian-formatting utility."""
        print(f"\n--- Testing _format_for_guardian_api (sync) for Parent {test_parent_orm.first_name} ---")
        
        # 1. Create a dummy ScheduledTuition dataclass
        dummy_schedule = ScheduledTuition(
            tuition=test_tuition_orm,
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        # 2. Call the sync method
        formatted = timetable_service_sync._format_for_guardian_api(
            dummy_schedule, 
            current_user=test_parent_orm
        )
        
        # 3. Assert
        assert isinstance(formatted, timetable_models.ScheduledTuitionReadForGuardian)
        assert formatted.tuition_id == test_tuition_orm.id
        
        # --- Logging ---
        print("--- Successfully formatted data for Guardian view (raw) ---")
        pprint(formatted.model_dump())
        # --- End Logging ---
