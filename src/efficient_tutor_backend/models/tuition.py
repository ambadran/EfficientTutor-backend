'''

'''
from datetime import timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID
from typing import Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Import the new, simple read models
from .user import UserRead, ParentRead
from ..database.db_enums import SubjectEnum, EducationalSystemEnum
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
    educational_system: EducationalSystemEnum
    grade: int
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
    educational_system: EducationalSystemEnum
    grade: int
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
    educational_system: EducationalSystemEnum
    grade: int
    lesson_index: int
    min_duration_minutes: int
    max_duration_minutes: int
    meeting_link: Optional[MeetingLinkRead] = None # The service will populate this string
    
    # As requested: no cost/charge
    attendee_names: list[str] # All student names for context

    model_config = ConfigDict(from_attributes=True)


# --- API Write Models (Input) ---

class TuitionChargeUpdate(BaseModel):
    """
    Specifies a new cost for a single student within a tuition.
    """
    student_id: UUID
    cost: Decimal = Field(..., gt=0, description="The new cost for the student, must be positive.")

class TuitionUpdate(BaseModel):
    """
    The API model for updating a tuition's editable fields.
    All fields are optional.
    """
    min_duration_minutes: Optional[int] = Field(None, gt=0, description="The new minimum duration in minutes.")
    max_duration_minutes: Optional[int] = Field(None, gt=0, description="The new maximum duration in minutes.")
    charges: Optional[list[TuitionChargeUpdate]] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='after')
    def validate_durations(self) -> 'TuitionUpdate':
        """
        Ensures that if both min and max durations are provided, max is not less than min.
        If only one is provided, it will be validated against the existing value in the service layer.
        """
        min_duration = self.min_duration_minutes
        max_duration = self.max_duration_minutes
        
        if min_duration is not None and max_duration is not None:
            if max_duration < min_duration:
                raise ValueError('max_duration_minutes cannot be less than min_duration_minutes')
        return self


# Define a union type for role-based responses
TuitionReadRoleBased = Union[
    TuitionReadForTeacher,
    TuitionReadForParent,
    TuitionReadForStudent,
]
