'''

'''
from datetime import timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# Import the new, simple read models
from .user import UserRead, ParentRead
from ..database.db_enums import SubjectEnum
from .meeting_links import MeetingLinkRead

# --- API Read Models (Output) ---

class TuitionChargeDetailRead(BaseModel):
    """
    A detailed charge model for the Teacher's view.
    Includes Student and Parent info.
    """
    cost: Decimal
    student: UserRead
    parent: ParentRead # As requested, show the parent for each student

    model_config = ConfigDict(from_attributes=True)

class TuitionReadForTeacher(BaseModel):
    """
    The API model for a tuition as seen by a TEACHER.
    Shows full financial details.
    """
    id: UUID
    subject: SubjectEnum
    lesson_index: int
    min_duration_minutes: int
    max_duration_minutes: int
    meeting_link: Optional[MeetingLinkRead] = None # The service will populate this string
    
    # As requested: full details
    charges: list[TuitionChargeDetailRead]

    model_config = ConfigDict(from_attributes=True)

class TuitionReadForParent(BaseModel):
    """
    The API model for a tuition as seen by a PARENT.
    Shows only their specific cost.
    """
    id: UUID
    subject: SubjectEnum
    lesson_index: int
    min_duration_minutes: int
    max_duration_minutes: int
    meeting_link: Optional[MeetingLinkRead] = None # The service will populate this string

    # As requested: only the parent's cost
    charge: Decimal 
    attendee_names: list[str] # All student names for context

    model_config = ConfigDict(from_attributes=True)

class TuitionReadForStudent(BaseModel):
    """
    The API model for a tuition as seen by a STUDENT.
    Shows NO financial details.
    """
    id: UUID
    subject: SubjectEnum
    lesson_index: int
    min_duration_minutes: int
    max_duration_minutes: int
    meeting_link: Optional[MeetingLinkRead] = None # The service will populate this string
    
    # As requested: no cost/charge
    attendee_names: list[str] # All student names for context

    model_config = ConfigDict(from_attributes=True)
