# In models/user.py

from datetime import time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Import the new, static enums from your db_enums.py file
from ..database.db_enums import (
    UserRole, 
    StudentStatusEnum, 
    SubjectEnum
)

# --- StudentData Models (for the JSONB field) ---
# These are Pydantic models that parse the 'student_data' JSONB
# from the db_models.Students table.

class SubjectDetail(BaseModel):
    name: SubjectEnum
    sharedWith: list[UUID] = Field(default_factory=list)
    lessonsPerWeek: int

class AvailabilityInterval(BaseModel):
    start: time
    end: time
    type: str

class Availability(BaseModel):
    monday: list[AvailabilityInterval] = Field(default_factory=list)
    tuesday: list[AvailabilityInterval] = Field(default_factory=list)
    wednesday: list[AvailabilityInterval] = Field(default_factory=list)
    thursday: list[AvailabilityInterval] = Field(default_factory=list)
    friday: list[AvailabilityInterval] = Field(default_factory=list)
    saturday: list[AvailabilityInterval] = Field(default_factory=list)
    sunday: list[AvailabilityInterval] = Field(default_factory=list)

class StudentData(BaseModel):
    subjects: list[SubjectDetail] = Field(default_factory=list)
    availability: Availability = Field(default_factory=Availability)


# --- User API Read Models ---

class UserRead(BaseModel):
    """
    Base Pydantic model for reading user data.
    Corresponds to the db_models.Users ORM model.
    """
    id: UUID
    email: str
    role: UserRole
    timezone: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_first_sign_in: bool

    model_config = ConfigDict(from_attributes=True)

class ParentRead(UserRead):
    """
    Pydantic model for reading a Parent.
    Includes fields from db_models.Parents.
    """
    currency: str

class TeacherRead(UserRead):
    """
    Pydantic model for reading a Teacher.
    (No extra fields for now)
    """
    pass

class StudentRead(UserRead):
    """
    Pydantic model for reading a Student.
    Includes fields from db_models.Students.
    """
    parent_id: UUID
    student_data: StudentData
    cost: Decimal
    status: StudentStatusEnum
    min_duration_mins: int
    max_duration_mins: int
    grade: Optional[int] = None

# We can also add input/create models here
class UserCreate(BaseModel):
    """
    Pydantic model for validating user creation input.
    """
    email: str
    password: str
    first_name: str
    last_name: str
    timezone: str
    
    # We will expand this as we build the user creation service
