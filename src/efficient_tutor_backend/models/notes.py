'''

'''
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..database.db_enums import SubjectEnum, NoteTypeEnum
from .user import UserRead


class NoteBase(BaseModel):
    """
    Base Pydantic model with common fields for a Note.
    Used for validation and sharing logic.
    """
    name: str = Field(..., min_length=1, max_length=255)
    subject: SubjectEnum
    note_type: NoteTypeEnum
    description: Optional[str] = None
    url: Optional[str] = None


class NoteCreate(NoteBase):
    """
    Pydantic model for validating the JSON payload when CREATING a new note.
    This is what the frontend sends in a POST request.
    'teacher_id' is excluded and will be added by the service.
    """
    student_id: UUID


class NoteUpdate(BaseModel):
    """
    NEW: Pydantic model for validating the JSON payload when UPDATING a note.
    All fields are optional to allow for partial updates (PATCH).
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject: Optional[SubjectEnum] = None
    note_type: Optional[NoteTypeEnum] = None
    description: Optional[str] = None
    url: Optional[str] = None


class NoteRead(NoteBase):
    """
    Pydantic model for formatting a note when READING it from the API.
    This is what is sent back to the frontend in a GET request.
    """
    id: UUID
    created_at: datetime
    
    # We include the full, nested teacher and student
    # objects using our lean UserRead model.
    teacher: UserRead
    student: UserRead

    # This allows the model to be created directly from the
    # db_models.Notes ORM object, as long as the 'teacher' and 'student'
    # relationships were eager-loaded by the service.
    model_config = ConfigDict(from_attributes=True)
