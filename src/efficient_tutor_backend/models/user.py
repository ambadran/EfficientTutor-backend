# In models/user.py

from datetime import time
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Import the new, static enums from your db_enums.py file
from ..database.db_enums import (
    UserRole, 
    StudentStatusEnum, 
    SubjectEnum
)

# --- New Student-Specific Read Models (for relational data) ---

class StudentSubjectRead(BaseModel):
    """
    Pydantic model for reading a student's subject details.
    Corresponds to db_models.StudentSubjects.
    """
    id: UUID
    subject: SubjectEnum
    lessons_per_week: int
    shared_with_student_ids: List[UUID] = Field(default_factory=list) # List of student IDs this subject is shared with

    model_config = ConfigDict(from_attributes=True)

class StudentAvailabilityIntervalRead(BaseModel):
    """
    Pydantic model for reading a student's availability interval.
    Corresponds to db_models.StudentAvailabilityIntervals.
    """
    id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    availability_type: str

    model_config = ConfigDict(from_attributes=True)


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
    cost: Decimal
    status: StudentStatusEnum
    min_duration_mins: int
    max_duration_mins: int
    grade: Optional[int] = None
    
    # New relational fields
    student_subjects: List[StudentSubjectRead] = Field(default_factory=list)
    student_availability_intervals: List[StudentAvailabilityIntervalRead] = Field(default_factory=list)

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


# --- New Student-Specific Write Models (for relational data) ---

class StudentSubjectWrite(BaseModel):
    """
    Pydantic model for creating/updating a student's subject details.
    Corresponds to db_models.StudentSubjects.
    """
    subject: SubjectEnum
    lessons_per_week: int = 1
    shared_with_student_ids: List[UUID] = Field(default_factory=list)

class StudentAvailabilityIntervalWrite(BaseModel):
    """
    Pydantic model for creating/updating a student's availability interval.
    Corresponds to db_models.StudentAvailabilityIntervals.
    """
    day_of_week: int = Field(..., ge=1, le=7) # 1=Monday, 7=Sunday
    start_time: time
    end_time: time
    availability_type: str # This should probably be an Enum too, but for now, string.

class StudentCreate(BaseModel):
    """
    Pydantic model for validating the JSON payload when CREATING a new student.
    Password is not included as it will be auto-generated.
    """
    # Fields from UserCreate, minus password
    email: str
    first_name: str
    last_name: str
    timezone: str

    # Fields specific to Student
    parent_id: UUID
    cost: Decimal = Field(6.00, decimal_places=2)
    status: StudentStatusEnum = StudentStatusEnum.NONE
    min_duration_mins: int = 60
    max_duration_mins: int = 90
    grade: Optional[int] = None
    
    student_subjects: List[StudentSubjectWrite] = Field(default_factory=list)
    student_availability_intervals: List[StudentAvailabilityIntervalWrite] = Field(default_factory=list)
