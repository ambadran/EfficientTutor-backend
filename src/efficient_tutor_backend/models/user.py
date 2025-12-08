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
    SubjectEnum,
    AdminPrivilegeType,
    EducationalSystemEnum
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
    teacher_id: UUID
    educational_system: EducationalSystemEnum
    grade: int = Field(..., ge=1, le=12)
    shared_with_student_ids: list[UUID] = Field(default_factory=list) # list of student IDs this subject is shared with

    model_config = ConfigDict(from_attributes=True)

class AvailabilityIntervalRead(BaseModel):
    """
    Pydantic model for reading an availability interval (Student or Teacher).
    Corresponds to db_models.AvailabilityIntervals.
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

class TeacherSpecialtyRead(BaseModel):
    """
    Pydantic model for reading a teacher's specialty.
    Corresponds to db_models.TeacherSpecialties.
    """
    id: UUID
    subject: SubjectEnum
    educational_system: EducationalSystemEnum
    grade: int = Field(..., ge=1, le=12)

    model_config = ConfigDict(from_attributes=True)

class TeacherRead(UserRead):
    """
    Pydantic model for reading a Teacher.
    """
    currency: str
    teacher_specialties: list[TeacherSpecialtyRead] = Field(default_factory=list)
    availability_intervals: list[AvailabilityIntervalRead] = Field(default_factory=list)


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
    grade: Optional[int] = Field(None, ge=1, le=12)
    educational_system: Optional[EducationalSystemEnum] = None
    generated_password: Optional[str] = None # New field
    
    # New relational fields
    student_subjects: list[StudentSubjectRead] = Field(default_factory=list)
    availability_intervals: list[AvailabilityIntervalRead] = Field(default_factory=list)


# --- New Student-Specific Write Models (for relational data) ---

class StudentSubjectWrite(BaseModel):
    """
    Pydantic model for creating/updating a student's subject details.
    Corresponds to db_models.StudentSubjects.
    """
    subject: SubjectEnum
    teacher_id: UUID
    educational_system: EducationalSystemEnum
    grade: int = Field(..., ge=1, le=12)
    lessons_per_week: int = 1
    shared_with_student_ids: list[UUID] = Field(default_factory=list)

class AvailabilityIntervalCreate(BaseModel):
    """
    Pydantic model for creating an availability interval.
    Corresponds to db_models.AvailabilityIntervals.
    """
    day_of_week: int = Field(..., ge=1, le=7) # 1=Monday, 7=Sunday
    start_time: time
    end_time: time
    availability_type: str # This should probably be an Enum too, but for now, string.

class AvailabilityIntervalUpdate(BaseModel):
    """
    Pydantic model for updating an availability interval.
    All fields are optional.
    """
    day_of_week: Optional[int] = Field(None, ge=1, le=7)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    availability_type: Optional[str] = None

class StudentCreate(BaseModel):
    """
    Pydantic model for validating the JSON payload when CREATING a new student.
    Password is not included as it will be auto-generated.
    """
    # Fields from UserCreate, minus password
    first_name: str
    last_name: str

    # Fields specific to Student
    parent_id: UUID
    cost: Decimal = Field(6.00, decimal_places=2)
    status: StudentStatusEnum = StudentStatusEnum.NONE
    min_duration_mins: int = 60
    max_duration_mins: int = 90
    grade: Optional[int] = Field(None, ge=1, le=12)
    educational_system: Optional[EducationalSystemEnum] = None
    
    student_subjects: list[StudentSubjectWrite] = Field(default_factory=list)
    availability_intervals: list[AvailabilityIntervalCreate] = Field(default_factory=list)

class StudentUpdate(BaseModel):
    """
    Pydantic model for validating the JSON payload when UPDATING an existing student.
    All fields are optional to allow for partial updates (PATCH).
    """
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: Optional[str] = None

    parent_id: Optional[UUID] = None # Changing parent is a significant operation, but allowed
    cost: Optional[Decimal] = Field(None, decimal_places=2)
    status: Optional[StudentStatusEnum] = None
    min_duration_mins: Optional[int] = None
    max_duration_mins: Optional[int] = None
    grade: Optional[int] = Field(None, ge=1, le=12)
    educational_system: Optional[EducationalSystemEnum] = None
    
    # For nested lists, we typically replace the entire list on update
    student_subjects: Optional[list[StudentSubjectWrite]] = None
    availability_intervals: Optional[list[AvailabilityIntervalCreate]] = None

class ParentCreate(BaseModel):
    """
    Pydantic model for validating the JSON payload when CREATING a new parent.
    This is used for parent sign-up.
    Timezone and currency will be determined automatically by the backend.
    """
    email: str
    password: str
    first_name: str
    last_name: str

class ParentUpdate(BaseModel):
    """
    Pydantic model for validating the JSON payload when UPDATING a parent.
    All fields are optional to allow for partial updates.
    """
    email: Optional[str] = None
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None

class TeacherSpecialtyWrite(BaseModel):
    """
    Pydantic model for creating/updating a teacher's specialty.
    """
    subject: SubjectEnum
    educational_system: EducationalSystemEnum
    grade: int = Field(..., ge=1, le=12)


class TeacherSpecialtyQuery(BaseModel):
    """
    Pydantic model for querying teachers by specialty.
    """
    subject: SubjectEnum
    educational_system: EducationalSystemEnum
    grade: int = Field(..., ge=1, le=12)


class TeacherCreate(BaseModel):
    """
    Pydantic model for validating the JSON payload when CREATING a new teacher.
    This is used for teacher sign-up.
    Timezone and currency will be determined automatically by the backend.
    """
    email: str
    password: str
    first_name: str
    last_name: str
    teacher_specialties: list[TeacherSpecialtyWrite] = Field(default_factory=list)
    availability_intervals: list[AvailabilityIntervalCreate] = Field(default_factory=list)


class TeacherUpdate(BaseModel):
    """
    Pydantic model for validating the JSON payload when UPDATING a teacher.
    All fields are optional to allow for partial updates.
    """
    email: Optional[str] = None
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    availability_intervals: Optional[list[AvailabilityIntervalCreate]] = None


class AdminRead(UserRead):
    """
    Pydantic model for reading an Admin.
    Includes fields from db_models.Admins.
    """
    privileges: AdminPrivilegeType


class AdminCreate(BaseModel):
    """
    Pydantic model for validating the JSON payload when CREATING a new admin.
    This is used by a Master admin.
    Timezone will be determined automatically by the backend.
    """
    email: str
    password: str
    first_name: str
    last_name: str
    privileges: AdminPrivilegeType = Field(..., description="Privilege level for the new admin.")


class AdminUpdate(BaseModel):
    """
    Pydantic model for validating the JSON payload when UPDATING an admin.
    All fields are optional to allow for partial updates.
    """
    email: Optional[str] = None
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: Optional[str] = None
    privileges: Optional[AdminPrivilegeType] = None

