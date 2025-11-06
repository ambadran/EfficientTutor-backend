'''

'''
import pytest
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.database.db_enums import MeetingLinkTypeEnum
from src.efficient_tutor_backend.models import meeting_links as meeting_link_models
from src.efficient_tutor_backend.services.tuition_service import TuitionService
# --- Import Test Constants ---
from tests.constants import TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_PARENT_ID

from pprint import pp as pprint

@pytest.mark.anyio
class TestTuitionService:

    ### Tests for get_tuition_by_id ###

    async def test_get_tuition_by_id(
        self,
        tuition_service: TuitionService,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests fetching a single tuition template by its ID."""
        # Use the fixture to get a known tuition
        tuition = await tuition_service._get_tuition_by_id_internal(test_tuition_orm.id)
       
        print(f"\n--- Found Tuition by ID ({test_tuition_orm.id}) ---")
        pprint(tuition.__dict__)
        pprint(tuition.tuition_template_charges[0].__dict__)

        assert tuition is not None
        assert tuition.id == test_tuition_orm.id

    async def test_get_tuition_by_id_not_found(
        self,
        tuition_service: TuitionService
    ):
        """Tests that None is returned for a non-existent tuition ID."""
        print(f"\n--- Testing _get_tuition_by_id_internal for non-existing tuition ---")
        with pytest.raises(HTTPException) as e:
            await tuition_service._get_tuition_by_id_internal(UUID(int=0)) # Random UUID

        assert e.value.status_code == 404
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_get_tuition_by_id_for_api(
        self,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users,
        test_parent_orm: db_models.Users,
        test_student_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests fetching a single tuition template by its ID."""
        # Use the fixture to get a known tuition
        tuition = await tuition_service.get_tuition_by_id_for_api(test_tuition_orm.id, test_teacher_orm)
        tuition = await tuition_service.get_tuition_by_id_for_api(test_tuition_orm.id, test_parent_orm)
        tuition = await tuition_service.get_tuition_by_id_for_api(test_tuition_orm.id, test_student_orm)
       
        print(f"\n--- Found Tuition by ID ({test_tuition_orm.id}) ---")
        pprint(tuition)

        assert tuition is not None
        assert tuition["id"] == str(test_tuition_orm.id)

    async def test_get_tuition_by_id_for_api_not_related(
        self,
        tuition_service: TuitionService,
        test_unrelated_teacher_orm: db_models.Users,
        test_unrelated_parent_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests fetching a single tuition template by its ID."""
        # Use the fixture to get a known tuition
        with pytest.raises(HTTPException) as e:
            await tuition_service.get_tuition_by_id_for_api(test_tuition_orm.id, test_unrelated_teacher_orm)
        assert e.value.status_code == 403


        with pytest.raises(HTTPException) as e:
            await tuition_service.get_tuition_by_id_for_api(test_tuition_orm.id, test_unrelated_parent_orm)
        assert e.value.status_code == 403
        
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")


    ### Tests for get_all_tuitions ###

    async def test_get_all(
        self,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users
    ):
        """
        Tests that a TEACHER can successfully fetch all tuitions.
        The service should return all tuitions associated with this teacher.
        """
        print(f"\n--- Testing get_all_tuitions as TEACHER ({test_teacher_orm.first_name}) ---")
        
        tuitions = await tuition_service.get_all_tuitions_orm(current_user=test_teacher_orm)
        
        # --- Assertions ---
        assert isinstance(tuitions, list)
        
        # --- Logging ---
        print(f"--- Found {len(tuitions)} Total Tuitions for Teacher '{test_teacher_orm.first_name} {test_teacher_orm.last_name}'---")
        if tuitions:
            assert isinstance(tuitions[0], db_models.Tuitions)
            print(f"Example Tuition Subject: {tuitions[0].subject}")
            print("--- Example Tuition Object (raw) ---")
            pprint(tuitions[0].__dict__)
        else:
            print("--- No tuitions found for this teacher in the test data. ---")
        # --- End Logging ---


    async def test_get_all_for_api_as_teacher(
        self,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users
    ):
        """
        Tests that a TEACHER can successfully fetch all tuitions.
        The service should return all tuitions associated with this teacher.
        """
        print(f"\n--- Testing get_all_tuitions as TEACHER ({test_teacher_orm.first_name}) ---")
        
        tuitions = await tuition_service.get_all_tuitions_for_api(current_user=test_teacher_orm)
        
        # --- Assertions ---
        assert isinstance(tuitions, list)
        
        # --- Logging ---
        print(f"--- Found {len(tuitions)} Total Tuitions for Teacher '{test_teacher_orm.first_name} {test_teacher_orm.last_name}'---")
        if tuitions:
            print(f"Example Tuition Subject: {tuitions[0]["subject"]}")
            print("--- Example Tuition Object (raw) ---")
            pprint(tuitions[0])
        else:
            print("--- No tuitions found for this teacher in the test data. ---")
        # --- End Logging ---

    async def test_get_all_for_api_as_parent(
        self,
        tuition_service: TuitionService,
        test_parent_orm: db_models.Users
    ):
        """
        Tests that a PARENT can successfully fetch their tuitions.
        The service should return only tuitions relevant to this parent.
        """
        print(f"\n--- Testing get_all_tuitions as PARENT ({test_parent_orm.first_name}) ---")
        
        tuitions = await tuition_service.get_all_tuitions_for_api(current_user=test_parent_orm)
        
        # --- Assertions ---
        assert isinstance(tuitions, list)
        # We can't know the exact count, but we know the call succeeded.
        
        # --- Logging ---
        print(f"--- Found {len(tuitions)} Tuitions for Parent '{test_parent_orm.first_name} {test_parent_orm.last_name}' ---")
        if tuitions:
            print(f"Example Tuition Subject: {tuitions[0]["subject"]}")
            print("--- Example Tuition Object (raw) ---")
            pprint(tuitions[0])
        else:
            print("--- No tuitions found for this parent in the test data. ---")
        # --- End Logging ---

    async def test_get_all_for_api_as_student(
        self,
        tuition_service: TuitionService,
        test_student_orm: db_models.Users
    ):
        """
        Tests that a STUDENT can successfully fetch their tuitions.
        The service should return only tuitions relevant to this student.
        """
        print(f"\n--- Testing get_all_tuitions as STUDENT ({test_student_orm.first_name}) ---")

        tuitions = await tuition_service.get_all_tuitions_for_api(current_user=test_student_orm)

        # --- Assertions ---
        assert isinstance(tuitions, list)
        
        # --- Logging ---
        print(f"--- Found {len(tuitions)} Tuitions for Student '{test_student_orm.first_name} {test_student_orm.last_name}' ---")
        if tuitions:
            print(f"Example Tuition Subject: {tuitions[0]["subject"]}")
            print("--- Example Tuition Object (raw) ---")
            pprint(tuitions[0])

    ### Tests for regenerate_all_tuitions ###

    async def test_regenerate_all_tuitions(
        self,
        tuition_service: TuitionService
    ):
        """
        Tests that the regeneration process runs and returns True.
        This test confirms the method call succeeds.
        """
        #TODO:
        pass

    ### Tests for _generate_deterministic_id ###
    
    def test_generate_deterministic_id(
        self,
        tuition_service_sync: TuitionService # Request the service to get the method
    ):
        """
        Tests the internal ID generation logic.
        Note: This is a regular 'def' test, not 'async def'.
        """
        # For clarity, assign it to the name the rest of the
        # test expects, or just use tuition_service_sync directly.
        tuition_service = tuition_service_sync

        # Define two lists of student IDs, sorted to ensure order doesn't matter
        student_ids_1 = sorted([TEST_STUDENT_ID, TEST_PARENT_ID]) # Just using 2 IDs
        student_ids_2 = sorted([TEST_STUDENT_ID]) # A different list
        
        # --- Case 1: Same inputs should produce the same UUID ---
        uuid_1 = tuition_service._generate_deterministic_id(
            subject="Math",
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_1
        )
        
        uuid_2 = tuition_service._generate_deterministic_id(
            subject="Math",
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_1
        )
        
        assert isinstance(uuid_1, UUID)
        assert uuid_1 == uuid_2, "Same inputs did not produce the same UUID"
        
        # --- Case 2: Different student list should produce a different UUID ---
        uuid_3 = tuition_service._generate_deterministic_id(
            subject="Math",
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_2 # <-- Different list
        )
        
        assert uuid_1 != uuid_3, "Different student list produced the same UUID"
        
        # --- Case 3: Different subject should produce a different UUID ---
        uuid_4 = tuition_service._generate_deterministic_id(
            subject="Physics", # <-- Different subject
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_1
        )
        
        assert uuid_1 != uuid_4, "Different subject produced the same UUID"


# --- Helper Function (to create a link for update/delete tests) ---
# We make this a helper function to avoid duplicating create logic
async def create_test_link(
    db_session: AsyncSession,
    tuition_service: TuitionService,
    tuition_id: UUID,
    current_user: db_models.Users
) -> db_models.Tuitions:
    """Helper to create and commit a meeting link for a tuition."""
    create_data = meeting_link_models.MeetingLinkCreate(
        meeting_link_type=MeetingLinkTypeEnum.GOOGLE_MEET,
        meeting_link="https://meet.google.com/test-link"
    )
    await tuition_service.create_meeting_link_for_api(
        tuition_id, create_data, current_user
    )
    await db_session.commit() # Commit this pre-condition
    
    # Re-fetch the tuition with the link eagerly loaded
    stmt = select(db_models.Tuitions).options(
        selectinload(db_models.Tuitions.meeting_link)
    ).filter(db_models.Tuitions.id == tuition_id)
    
    tuition = (await db_session.scalars(stmt)).first()
    assert tuition.meeting_link is not None
    return tuition


@pytest.mark.anyio
class TestMeetingLinkService:
    """
    Tests the meeting link C/U/D methods (assumed to be on TuitionService).
    """

    ### Tests for create_meeting_link_for_api ###

    async def test_create_meeting_link_as_owner(
        self,
        db_session: AsyncSession,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users,
        test_tuition_orm_no_link: db_models.Tuitions  # <-- USE THE NEW FIXTURE
    ):
        """Tests that the OWNER (Teacher) can create a meeting link."""
        tuition_id = test_tuition_orm_no_link.id  # <-- Use the clean tuition
        print(f"\n--- Testing create_meeting_link as OWNER TEACHER ---")
        
        create_data = meeting_link_models.MeetingLinkCreate(
            meeting_link_type=MeetingLinkTypeEnum.ZOOM,
            meeting_link="https://zoom.us/j/12345",
            meeting_id="12345",
            meeting_password="pass"
        )
        
        # Act
        link_dict = await tuition_service.create_meeting_link_for_api(
            tuition_id, create_data, test_teacher_orm
        )
        
        await db_session.flush() 
        
        # Verify response
        assert isinstance(link_dict, dict)
        assert link_dict['tuition_id'] == str(tuition_id)
        assert link_dict['meeting_id'] == "12345"
        
        # Verify DB object
        await db_session.refresh(test_tuition_orm_no_link, ['meeting_link'])
        assert test_tuition_orm_no_link.meeting_link is not None
        assert test_tuition_orm_no_link.meeting_link.meeting_password == "pass"
        
        print("--- Successfully created meeting link (API dict) ---")
        pprint(link_dict)

    async def test_create_meeting_link_as_unrelated_teacher(
        self,
        tuition_service: TuitionService,
        test_unrelated_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests that an UNRELATED Teacher is FORBIDDEN from creating a link."""
        print(f"\n--- Testing create_meeting_link as UNRELATED TEACHER ---")
        
        create_data = meeting_link_models.MeetingLinkCreate(
            meeting_link_type=MeetingLinkTypeEnum.ZOOM,
            meeting_link="https://zoom.us/j/12345"
        )
        
        with pytest.raises(HTTPException) as e:
            await tuition_service.create_meeting_link_for_api(
                test_tuition_orm.id, create_data, test_unrelated_teacher_orm
            )
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_create_meeting_link_as_parent(
        self,
        tuition_service: TuitionService,
        test_parent_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests that a PARENT is FORBIDDEN from creating a link."""
        print(f"\n--- Testing create_meeting_link as PARENT ---")
        
        create_data = meeting_link_models.MeetingLinkCreate(
            meeting_link_type=MeetingLinkTypeEnum.ZOOM,
            meeting_link="https://zoom.us/j/12345"
        )
        
        with pytest.raises(HTTPException) as e:
            await tuition_service.create_meeting_link_for_api(
                test_tuition_orm.id, create_data, test_parent_orm
            )
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    ### Tests for update_meeting_link_for_api ###

    async def test_update_meeting_link_as_owner(
        self,
        db_session: AsyncSession,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions  # <-- This fixture *already has* a link
    ):
        """Tests that the OWNER (Teacher) can update their meeting link."""
        
        # --- THE FIX ---
        # 1. No helper function is needed. Just use the fixture.
        #    The `test_tuition_orm` fixture already has a link.
        tuition = test_tuition_orm
        # -----------------

        print(f"\n--- Testing update_meeting_link as OWNER TEACHER ---")
        print(f"--- Pre-condition: Using tuition {tuition.id} which has link: {tuition.meeting_link.meeting_link} ---")

        # --- Act ---
        update_data = meeting_link_models.MeetingLinkUpdate(
            meeting_link="https://meet.google.com/new-updated-link",
            meeting_link_type=MeetingLinkTypeEnum.GOOGLE_MEET # Pass the enum object
        )
        
        updated_link_dict = await tuition_service.update_meeting_link_for_api(
            tuition.id, update_data, test_teacher_orm
        )
        await db_session.flush() # Send update to DB
        
        # --- Verify Response ---
        assert isinstance(updated_link_dict, dict)
        assert updated_link_dict['meeting_link'] == "https://meet.google.com/new-updated-link"
        assert updated_link_dict['meeting_link_type'] == MeetingLinkTypeEnum.GOOGLE_MEET.value
        
        # --- Verify DB Object ---
        # We refresh the *existing* meeting_link object
        await db_session.refresh(tuition.meeting_link) 
        assert tuition.meeting_link.meeting_link == "https://meet.google.com/new-updated-link"
        assert tuition.meeting_link.meeting_link_type == MeetingLinkTypeEnum.GOOGLE_MEET.value
        
        print("--- Successfully updated meeting link (API dict) ---")
        pprint(updated_link_dict)

    async def test_update_meeting_link_as_unrelated_teacher(
        self,
        db_session: AsyncSession, # Retained for consistency
        tuition_service: TuitionService,
        test_unrelated_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions # This fixture has the link
    ):
        """Tests that an UNRELATED Teacher is FORBIDDEN from updating a link."""
        
        # Use the fixture directly, it already has the link
        tuition = test_tuition_orm
        
        print(f"\n--- Testing update_meeting_link as UNRELATED TEACHER ---")
        print(f"--- Using Tuition ID: {tuition.id} ---")
        print(f"--- Unrelated Teacher ID: {test_unrelated_teacher_orm.id} ---")

        # --- Act & Assert ---
        update_data = meeting_link_models.MeetingLinkUpdate(
            meeting_link="https://meet.google.com/forbidden-link"
        )
        
        with pytest.raises(HTTPException) as e:
            await tuition_service.update_meeting_link_for_api(
                tuition.id, update_data, test_unrelated_teacher_orm
            )
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    ### Tests for delete_meeting_link ###

    async def test_delete_meeting_link_as_owner(
        self,
        db_session: AsyncSession,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions # <-- This fixture has the link
    ):
        """Tests that the OWNER (Teacher) can delete their meeting link."""
        
        # --- Setup: Use the fixture directly ---
        tuition = test_tuition_orm
        tuition_id = tuition.id
        
        print(f"\n--- Testing delete_meeting_link as OWNER TEACHER ---")
        
        # Verify the link exists before we try to delete it
        assert tuition.meeting_link is not None
        print(f"--- Pre-condition: Link exists for tuition {tuition.id} ---")

        # --- Act ---
        await tuition_service.delete_meeting_link(tuition_id, test_teacher_orm)
        await db_session.flush() # Send DELETE to DB
        
        # --- Verify DB Object ---
        # We refresh the *parent* tuition. Its 'meeting_link' relationship
        # will now be None because the link row is gone.
        await db_session.refresh(tuition, ['meeting_link'])
        assert tuition.meeting_link is None
        
        print(f"--- Successfully deleted link. tuition.meeting_link is now None. ---")
        # The test's final rollback will restore this deleted link.

    async def test_delete_meeting_link_as_unrelated_teacher(
        self,
        db_session: AsyncSession,
        tuition_service: TuitionService,
        test_unrelated_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions # <-- This fixture has the link
    ):
        """Tests that an UNRELATED Teacher is FORBIDDEN from deleting a link."""
        
        tuition = test_tuition_orm
        print(f"\n--- Testing delete_meeting_link as UNRELATED TEACHER ---")
        
        # Verify the link exists to start
        assert tuition.meeting_link is not None

        # --- Act & Assert ---
        with pytest.raises(HTTPException) as e:
            await tuition_service.delete_meeting_link(
                tuition.id, test_unrelated_teacher_orm
            )
        
        assert e.value.status_code == 403
        
        # --- Verify link was NOT deleted ---
        # We refresh just to be 100% sure the DB state hasn't changed
        await db_session.refresh(tuition, ['meeting_link'])
        assert tuition.meeting_link is not None
        
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")
