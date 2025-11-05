import pytest
from uuid import UUID
from datetime import datetime
from pprint import pprint
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# --- Import models, services, and Pydantic models ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.notes_service import NotesService
from src.efficient_tutor_backend.models import notes as notes_models
from src.efficient_tutor_backend.database.db_enums import SubjectEnum, NoteTypeEnum

# --- Import Test Constants ---
from tests.constants import (
    TEST_TEACHER_ID, 
    TEST_STUDENT_ID, 
    TEST_PARENT_ID
)


@pytest.mark.anyio
class TestNotesService:

    ### Tests for get_note_by_id_for_api ###

    async def test_get_note_by_id_as_owner_teacher(
        self,
        notes_service: NotesService,
        test_note_orm: db_models.Notes,
        test_teacher_orm: db_models.Users
    ):
        """Tests that the OWNER (Teacher) can fetch a note."""
        note_id = test_note_orm.id
        print(f"\n--- Testing get_note_by_id as OWNER TEACHER ---")
        
        note_dict = await notes_service.get_note_by_id_for_api(note_id, test_teacher_orm)
        
        assert isinstance(note_dict, dict)
        assert note_dict['id'] == str(note_id)
        assert note_dict['teacher']['id'] == str(test_teacher_orm.id)
        
        print("--- Found note (API dict) ---")
        pprint(note_dict)

    async def test_get_note_by_id_as_student(
        self,
        notes_service: NotesService,
        test_note_orm: db_models.Notes,
        test_student_orm: db_models.Users
    ):
        """Tests that the related STUDENT can fetch a note."""
        note_id = test_note_orm.id
        print(f"\n--- Testing get_note_by_id as STUDENT ---")
        
        note_dict = await notes_service.get_note_by_id_for_api(note_id, test_student_orm)
        
        assert isinstance(note_dict, dict)
        assert note_dict['id'] == str(note_id)
        assert note_dict['student']['id'] == str(test_student_orm.id)

        print("--- Found note (API dict) ---")
        pprint(note_dict)

    async def test_get_note_by_id_as_parent(
        self,
        notes_service: NotesService,
        test_note_orm: db_models.Notes,
        test_parent_orm: db_models.Users,
        test_student_orm: db_models.Users
    ):
        """Tests that the related PARENT can fetch a note."""
        note_id = test_note_orm.id
        print(f"\n--- Testing get_note_by_id as PARENT ---")
        
        note_dict = await notes_service.get_note_by_id_for_api(note_id, test_parent_orm)
        
        assert isinstance(note_dict, dict)
        assert note_dict['id'] == str(note_id)
        assert note_dict['student']['id'] == str(test_student_orm.id) # The student, not parent

        print("--- Found note (API dict) ---")
        pprint(note_dict)

    async def test_get_note_by_id_as_unrelated_teacher(
        self,
        notes_service: NotesService,
        test_note_orm: db_models.Notes,
        test_unrelated_teacher_orm: db_models.Users
    ):
        """Tests that an UNRELATED teacher is FORBIDDEN."""
        note_id = test_note_orm.id
        print(f"\n--- Testing get_note_by_id as UNRELATED TEACHER ---")
        
        with pytest.raises(HTTPException) as e:
            await notes_service.get_note_by_id_for_api(note_id, test_unrelated_teacher_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_get_note_by_id_not_found(
        self,
        notes_service: NotesService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that a 404 is raised for a non-existent note."""
        note_id = UUID(int=0) # Random UUID
        print(f"\n--- Testing get_note_by_id for non-existent ID ---")
        
        with pytest.raises(HTTPException) as e:
            await notes_service.get_note_by_id_for_api(note_id, test_teacher_orm)
        
        assert e.value.status_code == 404
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")


    ### Tests for get_all_notes_for_api ###

    async def test_get_all_notes_as_teacher(
        self,
        notes_service: NotesService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that a TEACHER gets all their notes."""
        print(f"\n--- Testing get_all_notes_for_api as TEACHER ---")
        notes = await notes_service.get_all_notes_for_api(test_teacher_orm)
        assert isinstance(notes, list)
        print(f"--- Found {len(notes)} notes for Teacher {test_teacher_orm.first_name} ---")
        if len(notes) > 0:
            assert all(n['teacher']['id'] == str(test_teacher_orm.id) for n in notes)
            print("--- Example note Json Read ---")
            pprint(notes[0])

    async def test_get_all_notes_as_parent(
        self,
        notes_service: NotesService,
        test_parent_orm: db_models.Users
    ):
        """Tests that a PARENT gets all notes for their children."""
        print(f"\n--- Testing get_all_notes_for_api as PARENT ---")

        # 1. Get the set of valid student IDs for this parent
        # (This works now because the fixture eagerly loaded them)
        valid_student_ids = {student.id for student in test_parent_orm.students}
        print(f"--- Parent {test_parent_orm.first_name} has {len(valid_student_ids)} children ---")
        print(f"Valid Student IDs: {valid_student_ids}")

        # 2. Act
        notes = await notes_service.get_all_notes_for_api(test_parent_orm)

        # 3. Assert
        assert isinstance(notes, list)
        print(f"--- Found {len(notes)} notes for Parent {test_parent_orm.first_name}'s children ---")
        if len(notes) > 0:
            # 4. Check that every note's student ID is in the parent's list
            for note in notes:
                student_id_in_note = note['student']['id']
                print(f"Checking Note ID {note['id']} for Student ID {student_id_in_note}...")
                assert UUID(student_id_in_note) in valid_student_ids, \
                    f"Note {note['id']} belongs to student {student_id_in_note}, who is not in the parent's child list!"
            
            print("--- All notes successfully validated against parent's children. ---")
            print("--- Example note Json Read ---")
            pprint(notes[0])
            
    async def test_get_all_notes_as_student(
        self,
        notes_service: NotesService,
        test_student_orm: db_models.Users
    ):
        """Tests that a STUDENT gets all their notes."""
        print(f"\n--- Testing get_all_notes_for_api as STUDENT ---")
        notes = await notes_service.get_all_notes_for_api(test_student_orm)
        assert isinstance(notes, list)
        print(f"--- Found {len(notes)} notes for Student {test_student_orm.first_name} ---")
        if len(notes) > 0:
            assert all(n['student']['id'] == str(test_student_orm.id) for n in notes)
            pprint(notes[0])

    ### Tests for create_note_for_api ###

    async def test_create_note_as_teacher(
        self,
        db_session: AsyncSession,
        notes_service: NotesService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that a TEACHER can create a new note."""
        print(f"\n--- Testing create_note_for_api as TEACHER ---")
        
        note_data = notes_models.NoteCreate(
            student_id=TEST_STUDENT_ID,
            name="Pytest Created Note",
            subject=SubjectEnum.MATH,
            note_type=NoteTypeEnum.HOMEWORK
        )
        
        new_note_dict = await notes_service.create_note_for_api(note_data, test_teacher_orm)
        await db_session.commit() # Save the new note
        
        assert isinstance(new_note_dict, dict)
        assert new_note_dict['id'] is not None
        assert new_note_dict['name'] == "Pytest Created Note"
        assert new_note_dict['teacher']['id'] == str(test_teacher_orm.id)
        
        print("--- Successfully created note (API dict) ---")
        pprint(new_note_dict)

    async def test_create_note_as_parent(
        self,
        notes_service: NotesService,
        test_parent_orm: db_models.Users
    ):
        """Tests that a PARENT is FORBIDDEN from creating a note."""
        print(f"\n--- Testing create_note_for_api as PARENT ---")

        note_data = notes_models.NoteCreate(
            student_id=TEST_STUDENT_ID,
            name="Pytest Created Note",
            subject=SubjectEnum.MATH,
            note_type=NoteTypeEnum.HOMEWORK
        )
        
        with pytest.raises(HTTPException) as e:
            await notes_service.create_note_for_api(note_data, test_parent_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    ### Tests for update_note_for_api ###

    async def test_update_note_as_owner_teacher(
        self,
        db_session: AsyncSession,
        notes_service: NotesService,
        test_teacher_orm: db_models.Users,
        test_note_orm: db_models.Notes
    ):
        """Tests that the OWNER (Teacher) can update their note."""
        note_id = test_note_orm.id
        new_name = f"Updated by Pytest {datetime.now()}"
        print(f"\n--- Testing update_note_for_api as OWNER TEACHER ---")
        
        update_data = notes_models.NoteUpdate(name=new_name)
        
        updated_note_dict = await notes_service.update_note_for_api(
            note_id, update_data, test_teacher_orm
        )
        await db_session.commit()
        
        assert isinstance(updated_note_dict, dict)
        assert updated_note_dict['id'] == str(note_id)
        assert updated_note_dict['name'] == new_name
        
        print("--- Successfully updated note (API dict) ---")
        pprint(updated_note_dict)

    async def test_update_note_as_unrelated_teacher(
        self,
        notes_service: NotesService,
        test_unrelated_teacher_orm: db_models.Users,
        test_note_orm: db_models.Notes
    ):
        """Tests that an UNRELATED teacher is FORBIDDEN from updating a note."""
        print(f"\n--- Testing update_note_for_api as UNRELATED TEACHER ---")
        
        update_data = notes_models.NoteUpdate(name="Forbidden update")
        
        with pytest.raises(HTTPException) as e:
            await notes_service.update_note_for_api(
                test_note_orm.id, update_data, test_unrelated_teacher_orm
            )
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    ### Tests for delete_note ###

    async def test_delete_note_as_owner_teacher(
        self,
        db_session: AsyncSession,  # <-- We need the session to flush
        notes_service: NotesService,
        test_teacher_orm: db_models.Users,
        test_note_orm: db_models.Notes
    ):
        """
        Tests that the OWNER can delete their note, but rolls back the
        deletion so other tests can still use the note.
        """
        note_id = test_note_orm.id
        print(f"\n--- Testing delete_note as OWNER TEACHER (with rollback) ---")
        
        # --- Act ---
        # This marks the note for deletion *in the session*
        success = await notes_service.delete_note(note_id, test_teacher_orm)
        assert success is True
        
        # 2. Flush the session. This sends the DELETE statement to
        #    the database transaction but does NOT make it permanent.
        await db_session.flush()
        
        # --- Verify it's gone (within this transaction) ---
        print(f"--- Verifying note {note_id} is deleted within the transaction ---")
        with pytest.raises(HTTPException) as e:
            # This query will now fail to find the note
            await notes_service._get_note_by_id_internal(note_id)
        assert e.value.status_code == 404
        
        print(f"--- Successfully verified deletion. Test will now roll back. ---")

        # When this test ends, the db_session fixture's `rollback()`
        # will undo the deletion, and the note will be back for the next test.

    async def test_delete_note_as_unrelated_teacher(
        self,
        notes_service: NotesService,
        test_unrelated_teacher_orm: db_models.Users,
        test_note_orm: db_models.Notes
    ):
        """Tests that an UNRELATED teacher is FORBIDDEN from deleting a note."""
        print(f"\n--- Testing delete_note as UNRELATED TEACHER ---")
        
        with pytest.raises(HTTPException) as e:
            await notes_service.delete_note(
                test_note_orm.id, test_unrelated_teacher_orm
            )
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")
