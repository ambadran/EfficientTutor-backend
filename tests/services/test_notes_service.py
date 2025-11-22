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
class TestNotesServiceReadbyID:

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
        
        note = await notes_service.get_note_by_id_for_api(note_id, test_teacher_orm)
        
        assert isinstance(note, notes_models.NoteRead)
        assert note.id == note_id
        assert note.teacher.id == test_teacher_orm.id
        
        print("--- Found note (API Model) ---")
        pprint(note.model_dump())

    async def test_get_note_by_id_as_student(
        self,
        notes_service: NotesService,
        test_note_orm: db_models.Notes,
        test_student_orm: db_models.Users
    ):
        """Tests that the related STUDENT can fetch a note."""
        note_id = test_note_orm.id
        print(f"\n--- Testing get_note_by_id as STUDENT ---")
        
        note = await notes_service.get_note_by_id_for_api(note_id, test_student_orm)
        
        assert isinstance(note, notes_models.NoteRead)
        assert note.id == note_id
        assert note.student.id == test_student_orm.id

        print("--- Found note (API Model) ---")
        pprint(note.model_dump())

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
        
        note = await notes_service.get_note_by_id_for_api(note_id, test_parent_orm)
        
        assert isinstance(note, notes_models.NoteRead)
        assert note.id == note_id
        assert note.student.id == test_student_orm.id # The student, not parent

        print("--- Found note (API Model) ---")
        pprint(note.model_dump())

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

@pytest.mark.anyio
class TestNotesServiceReadAll:

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
            assert isinstance(notes[0], notes_models.NoteRead)
            assert all(n.teacher.id == test_teacher_orm.id for n in notes)
            print("--- Example note ---")
            pprint(notes[0].model_dump())

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
            assert isinstance(notes[0], notes_models.NoteRead)
            # 4. Check that every note's student ID is in the parent's list
            for note in notes:
                student_id_in_note = note.student.id
                print(f"Checking Note ID {note.id} for Student ID {student_id_in_note}...")
                assert student_id_in_note in valid_student_ids, \
                    f"Note {note.id} belongs to student {student_id_in_note}, who is not in the parent's child list!"
            
            print("--- All notes successfully validated against parent's children. ---")
            print("--- Example note ---")
            pprint(notes[0].model_dump())
            
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
            assert isinstance(notes[0], notes_models.NoteRead)
            assert all(n.student.id == test_student_orm.id for n in notes)
            pprint(notes[0].model_dump())

@pytest.mark.anyio
class TestNotesServiceCreate:

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
        
        # ACT
        new_note_read = await notes_service.create_note_for_api(note_data, test_teacher_orm)
        await db_session.flush() # Save the new note to the transaction
        
        # ASSERT: Check the returned Pydantic model
        assert isinstance(new_note_read, notes_models.NoteRead)
        assert new_note_read.id is not None
        assert new_note_read.name == "Pytest Created Note"
        assert new_note_read.teacher.id == test_teacher_orm.id
        assert new_note_read.student.id == TEST_STUDENT_ID
        
        print("--- Successfully created note (API Model) ---")
        pprint(new_note_read.model_dump())

        # ASSERT: Verify the data in the database directly
        db_note = await db_session.get(db_models.Notes, new_note_read.id)
        assert db_note is not None
        assert db_note.name == "Pytest Created Note"
        assert db_note.subject == SubjectEnum.MATH.value
        assert db_note.note_type == NoteTypeEnum.HOMEWORK.value
        assert db_note.teacher_id == test_teacher_orm.id
        assert db_note.student_id == TEST_STUDENT_ID
        print(f"--- Successfully verified note {db_note.id} in database ---")

    async def test_create_note_as_parent_forbidden(
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

    async def test_create_note_as_student_forbidden(
        self,
        notes_service: NotesService,
        test_student_orm: db_models.Users
    ):
        """Tests that a STUDENT is FORBIDDEN from creating a note."""
        print(f"\n--- Testing create_note_for_api as STUDENT ---")

        note_data = notes_models.NoteCreate(
            student_id=TEST_STUDENT_ID,
            name="Pytest Created Note by Student",
            subject=SubjectEnum.MATH,
            note_type=NoteTypeEnum.HOMEWORK
        )
        
        with pytest.raises(HTTPException) as e:
            await notes_service.create_note_for_api(note_data, test_student_orm)
        
        assert e.value.status_code == 403
        assert e.value.detail == "You do not have permission to perform this action."
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_create_note_with_nonexistent_student(
        self,
        notes_service: NotesService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that creating a note with a non-existent student_id raises a 404."""
        print(f"\n--- Testing create_note_for_api with non-existent student_id ---")
        
        non_existent_student_id = UUID("00000000-0000-0000-0000-000000000001") # A UUID that should not exist
        
        note_data = notes_models.NoteCreate(
            student_id=non_existent_student_id,
            name="Note for non-existent student",
            subject=SubjectEnum.MATH,
            note_type=NoteTypeEnum.HOMEWORK
        )
        
        with pytest.raises(HTTPException) as e:
            await notes_service.create_note_for_api(note_data, test_teacher_orm)
        
        assert e.value.status_code == 404
        assert "Student not found" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

@pytest.mark.anyio
class TestNotesServiceUpdate:

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
        
        update_data = notes_models.NoteUpdate(
                name=new_name, 
                subject= "Physics", 
                description="Updated description.")
        
        # ACT
        updated_note_read = await notes_service.update_note_for_api(
            note_id, update_data, test_teacher_orm
        )
        await db_session.flush()
        
        # ASSERT: Check the returned Pydantic model
        assert isinstance(updated_note_read, notes_models.NoteRead)
        assert updated_note_read.id == note_id
        assert updated_note_read.name == new_name
        assert updated_note_read.description == "Updated description."
        
        print("--- Successfully updated note (API Model) ---")
        pprint(updated_note_read.model_dump())

        # ASSERT: Verify the data in the database directly
        await db_session.refresh(test_note_orm) # Refresh the note object itself
        assert test_note_orm.name == new_name
        assert test_note_orm.description == "Updated description."
        print(f"--- Successfully verified updated note {test_note_orm.id} in database ---")

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

    async def test_update_note_as_parent_forbidden(
        self,
        notes_service: NotesService,
        test_parent_orm: db_models.Users,
        test_note_orm: db_models.Notes
    ):
        """Tests that a PARENT is FORBIDDEN from updating a note."""
        print(f"\n--- Testing update_note_for_api as PARENT ---")
        
        update_data = notes_models.NoteUpdate(name="Forbidden update by parent")
        
        with pytest.raises(HTTPException) as e:
            await notes_service.update_note_for_api(
                test_note_orm.id, update_data, test_parent_orm
            )
        
        assert e.value.status_code == 403
        assert e.value.detail == "You do not have permission to modify or delete this note."
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_update_note_as_student_forbidden(
        self,
        notes_service: NotesService,
        test_student_orm: db_models.Users,
        test_note_orm: db_models.Notes
    ):
        """Tests that a STUDENT is FORBIDDEN from updating a note."""
        print(f"\n--- Testing update_note_for_api as STUDENT ---")
        
        update_data = notes_models.NoteUpdate(name="Forbidden update by student")
        
        with pytest.raises(HTTPException) as e:
            await notes_service.update_note_for_api(
                test_note_orm.id, update_data, test_student_orm
            )
        
        assert e.value.status_code == 403
        assert e.value.detail == "You do not have permission to modify or delete this note."
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")


@pytest.mark.anyio
class TestNotesServiceDelete:

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


