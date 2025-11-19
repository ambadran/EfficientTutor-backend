'''

'''
from typing import List, Optional, Annotated, Any
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import ValidationError

from ..database.engine import get_db_session
from ..database import models as db_models
from ..database.db_enums import UserRole, SubjectEnum, NoteTypeEnum
from ..models import notes as notes_models
from ..common.logger import log



from ..services.user_service import UserService # Add this import

class NotesService:
    """
    Service for all business logic related to student notes.
    """
    def __init__(
        self, 
        db: Annotated[AsyncSession, Depends(get_db_session)],
        user_service: Annotated[UserService, Depends(UserService)]
    ):
        self.db = db
        self.user_service = user_service

    # --- Authorization Helpers ---

    def _authorize(self, current_user: db_models.Users, allowed_roles: list[UserRole]):
        """Helper to check general role permissions."""
        allowed_role_values = [role.value for role in allowed_roles]
        if current_user.role not in allowed_role_values:
            log.warning(f"Unauthorized action by user {current_user.id} (Role: {current_user.role}). Required one of: {allowed_role_values}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action."
            )

    async def _authorize_read_access(self, note: db_models.Notes, current_user: db_models.Users):
        """
        Checks if a user has read permission for a *specific* note.
        (Teacher owner, the student, or the student's parent).
        """
        # 1. Check if Teacher is the owner
        if current_user.role == UserRole.TEACHER.value:
            if note.teacher_id == current_user.id:
                return  # Allow
        
        # 2. Check if Student is the subject
        elif current_user.role == UserRole.STUDENT.value:
            if note.student_id == current_user.id:
                return  # Allow
        
        # 3. Check if Parent is the parent of the subject student
        elif current_user.role == UserRole.PARENT.value:
            # We must rely on the 'students' relationship being loaded on the
            # 'current_user' (a Parent object) by the UserService.
            await self.db.refresh(current_user, ['students'])
            student_ids = [student.id for student in current_user.students]
            if note.student_id in student_ids:
                return  # Allow
        
        # 4. If none of the above passed, deny access
        log.warning(f"SECURITY: User {current_user.id} tried to read note {note.id} without permission.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this note."
        )

    def _authorize_write_access(self, note: db_models.Notes, current_user: db_models.Users):
        """
        Checks if a user has write/delete permission (Teacher owner only).
        """
        if not (current_user.role == UserRole.TEACHER.value and note.teacher_id == current_user.id):
            log.warning(f"SECURITY: User {current_user.id} tried to write to note {note.id} owned by {note.teacher_id}.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify or delete this note."
            )

    # --- Internal Fetcher ---
    
    async def _get_note_by_id_internal(self, note_id: UUID) -> db_models.Notes:
        """
        Internal helper to fetch a single note by ID, fully loaded.
        Raises 404 if not found.
        """
        log.info(f"Internal fetch for note by ID: {note_id}")
        stmt = select(db_models.Notes).options(
            selectinload(db_models.Notes.student).joinedload('*'), # Load student (and their parent)
            selectinload(db_models.Notes.teacher)
        ).filter(db_models.Notes.id == note_id)
        
        result = await self.db.execute(stmt)
        note = result.scalars().first()
        if not note:
            log.warning(f"Tried to fetch non-existing note: {note_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found.")
        return note

    # --- Public Read Methods (API-Facing) ---
    
    async def get_note_by_id_for_api(self, note_id: UUID, current_user: db_models.Users) -> notes_models.NoteRead:
        """
        Fetches a single note and returns it in API format,
        after verifying read authorization.
        """
        log.info(f"User {current_user.id} requesting note {note_id}")
        try:
            # 1. Fetch
            note_orm = await self._get_note_by_id_internal(note_id)
            
            # 2. Authorize
            await self._authorize_read_access(note_orm, current_user)
            
            # 3. Format and return
            return notes_models.NoteRead.model_validate(note_orm)
        
        except HTTPException as http_exc:
            raise http_exc # Re-raise 404s and 403s
        except Exception as e:
            log.error(f"Error in get_note_by_id_for_api for note {note_id}: {e}", exc_info=True)
            raise

    async def get_all_notes_for_api(self, current_user: db_models.Users) -> list[notes_models.NoteRead]:
        """
        Fetches all notes visible to the current user (Teacher, Parent, or Student)
        and returns them in API format.
        """
        log.info(f"User {current_user.id} (Role: {current_user.role}) requesting all notes.")
        
        # 1. Base query with eager loading
        stmt = select(db_models.Notes).options(
            selectinload(db_models.Notes.student).joinedload('*'),
            selectinload(db_models.Notes.teacher)
        ).order_by(db_models.Notes.created_at.desc())

        try:
            # 2. Build filter based on role
            if current_user.role == UserRole.TEACHER.value:
                stmt = stmt.filter(db_models.Notes.teacher_id == current_user.id)
            
            elif current_user.role == UserRole.PARENT.value:
                await self.db.refresh(current_user, ['students'])
                student_ids = [student.id for student in current_user.students]
                if not student_ids:
                    return [] # This parent has no students
                stmt = stmt.filter(db_models.Notes.student_id.in_(student_ids))
            
            elif current_user.role == UserRole.STUDENT.value:
                stmt = stmt.filter(db_models.Notes.student_id == current_user.id)
            
            else: # Admin or other roles
                self._authorize(current_user, [UserRole.TEACHER, UserRole.PARENT, UserRole.STUDENT])
                # This will raise a 403, as intended
                return [] 
            
            # 3. Execute and format
            result = await self.db.execute(stmt)
            notes_orm = result.scalars().all()
            
            return [notes_models.NoteRead.model_validate(note) for note in notes_orm]
        
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Database error in get_all_notes_for_api for user {current_user.id}: {e}", exc_info=True)
            raise

    # --- Public Write Methods (API-Facing) ---
    
    async def create_note_for_api(self, data: notes_models.NoteCreate, current_user: db_models.Users) -> notes_models.NoteRead:
        """
        Creates a new note. Restricted to Teachers only.
        Returns the newly created note in API format.
        """
        log.info(f"User {current_user.id} attempting to create note for student {data.student_id}.")
        
        try:
            # 1. Authorize: Must be a Teacher
            self._authorize(current_user, [UserRole.TEACHER])
            
            # 2. Validate student_id
            student = await self.user_service.get_user_by_id(data.student_id)
            if not student or student.role != UserRole.STUDENT.value:
                log.warning(f"Attempted to create note with non-existent or non-student student_id: {data.student_id}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

            # 3. Create the ORM object
            new_note = db_models.Notes(
                student_id=data.student_id,
                name=data.name,
                subject=data.subject.value,       # Use .value
                note_type=data.note_type.value,     # Use .value
                description=data.description,
                url=data.url,
                teacher_id=current_user.id        # 4. IDOR Security
            )
            
            self.db.add(new_note)
            await self.db.flush()
            await self.db.refresh(new_note, ['student', 'teacher']) # Load relationships
            
            # 4. Format and return
            return notes_models.NoteRead.model_validate(new_note)
        
        except (ValidationError, ValueError) as e:
            log.error(f"Validation failed for creating note. Data: {data}, Error: {e}")
            raise
        except HTTPException as http_exc:
            raise http_exc # Re-raise auth errors
        except Exception as e:
            log.error(f"Error in create_note_for_api: {e}", exc_info=True)
            raise

    async def update_note_for_api(self, note_id: UUID, data: notes_models.NoteUpdate, current_user: db_models.Users) -> notes_models.NoteRead:
        """
        Updates an existing note. Restricted to the Teacher who created it.
        Returns the updated note in API format.
        """
        log.info(f"User {current_user.id} attempting to update note {note_id}.")
        
        try:
            # 1. Fetch the existing note
            note_to_update = await self._get_note_by_id_internal(note_id)
            
            # 2. Authorize: Must be the *owner*
            self._authorize_write_access(note_to_update, current_user)
            
            # 3. Get update data (exclude_unset=True is perfect for PATCH)
            update_data = data.model_dump(exclude_unset=True)
            
            if not update_data:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update.")
            
            # 4. Apply updates
            for key, value in update_data.items():
                # Handle enums by getting their value before setting the attribute
                if key in ['subject', 'note_type'] and value is not None:
                    setattr(note_to_update, key, value.value)
                else:
                    setattr(note_to_update, key, value)
            
            self.db.add(note_to_update)
            await self.db.flush()
            await self.db.refresh(note_to_update, ['student', 'teacher'])
            
            # 5. Format and return
            return notes_models.NoteRead.model_validate(note_to_update)
        
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Error in update_note_for_api for note {note_id}: {e}", exc_info=True)
            raise
    
    async def delete_note(self, note_id: UUID, current_user: db_models.Users) -> bool:
        """
        Deletes a note. Restricted to the Teacher who created it.
        """
        log.info(f"User {current_user.id} attempting to delete note {note_id}.")
        
        try:
            # 1. Fetch the existing note
            note_to_delete = await self._get_note_by_id_internal(note_id)
            
            # 2. Authorize: Must be the *owner*
            self._authorize_write_access(note_to_delete, current_user)
            
            # 3. Delete
            await self.db.delete(note_to_delete)
            
            return True
        
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Error in delete_note for note {note_id}: {e}", exc_info=True)
            raise
