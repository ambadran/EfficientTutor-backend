'''
This Python file deals with all user instances in this project
'''
import enum
import logging
from datetime import time
from decimal import Decimal
from typing import Literal, Optional, Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator

from ..core.db_handler import DatabaseHandler

# --- Basic Setup ---
log = logging.getLogger(__name__)

# --- Initialize DB Handler and Dynamic ENUMs ---
try:
    db = DatabaseHandler()
    
    # Dynamically create Enum classes from database values
    UserRole = enum.Enum('UserRole', {label: label for label in db.get_enum_labels('user_role')})
    StudentStatus = enum.Enum('StudentStatus', {label: label for label in db.get_enum_labels('student_status_enum')})
    SubjectEnum = enum.Enum('SubjectEnum', {label: label for label in db.get_enum_labels('subject_enum')})
    
except Exception as e:
    log.critical(f"FATAL: Could not initialize database or dynamic ENUMs. Error: {e}", exc_info=True)
    # In a real app, you might want to exit or have a fallback.
    # For now, define placeholder Enums to allow module import.
    #TODO: finish this
    UserRole = enum.Enum('UserRole', {'parent': 'parent', 'student': 'student', 'teacher': 'teacher'})
    StudentStatus = enum.Enum('StudentStatus', {'NONE': 'NONE'})
    SubjectEnum = enum.Enum('SubjectEnum', {'Math': 'Math'})

# --- Pydantic Data Models (Singular Classes) ---

# Nested models for the 'student_data' JSONB field
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

# Main User Models
class User(BaseModel):
    """Abstract base model for all user types."""
    id: UUID
    email: EmailStr
    is_first_sign_in: bool = Field(alias='isFirstSignIn')
    role: UserRole
    timezone: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    class Config:
        orm_mode = True
        allow_population_by_field_name = True

class Parent(User):
    """Model for a Parent user."""
    role: Literal[UserRole.parent] # to validate it only takes UserRole.parent
    currency: str

class Teacher(User):
    """Model for a Teacher user."""
    role: Literal[UserRole.teacher]
    # Add teacher-specific fields here in the future

class Student(User):
    """Model for a Student user."""
    role: Literal[UserRole.student]
    parent_id: UUID
    student_data: StudentData
    cost: Decimal
    status: StudentStatus
    min_duration_mins: int
    max_duration_mins: int
    grade: Optional[int] = None
    generated_password: Optional[str] = None # For parent to view initially

# --- Service/Manager Classes (Plural Classes) ---

class Teachers:
    """Service class for managing Teacher users."""

    def get_by_id(self, teacher_id: UUID) -> Optional[Teacher]:
        """Fetches a single teacher by their ID."""
        user_data = db.get_user_by_id(teacher_id)
        if user_data and user_data.get('role') == 'teacher':
            return Teacher.parse_obj(user_data)
        log.warning(f"Could not find a teacher with ID {teacher_id} or user is not a teacher.")
        return None

    def get_all(self) -> list[Teacher]:
        """Fetches all teachers from the database."""
        all_teachers_data = db.get_all_users_by_role('teacher')
        return [Teacher.parse_obj(data) for data in all_teachers_data]

    def create(self, email: str, password: str, first_name: str, last_name: str) -> Optional[Teacher]:
        """
        Creates a new teacher and returns the Teacher model instance.
        This requires the create_teacher method in the DatabaseHandler.
        """
        new_id = db.create_teacher(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        if new_id:
            return self.get_by_id(new_id)
        return None

class Parents:
    """Service class for managing Parent users."""

    def get_by_id(self, parent_id: UUID) -> Optional[Parent]:
        """Fetches a single parent by their ID."""
        user_data = db.get_user_by_id(parent_id)
        if user_data and user_data.get('role') == 'parent':
            return Parent.parse_obj(user_data)
        log.warning(f"Could not find a parent with ID {parent_id} or user is not a parent.")
        return None

    def get_all(self) -> list[Parent]:
        """Fetches all parents from the database."""
        all_parents_data = db.get_all_users_by_role('parent')
        return [Parent.parse_obj(data) for data in all_parents_data]

    def create(self, email: str, password: str, first_name: str, last_name: str, currency: str = 'EGP') -> Optional[Parent]:
        #TODO: migrate the old user authentication code
        """Creates a new parent and returns the Parent model instance."""
        new_id = db.create_parent(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            currency=currency
        )
        if new_id:
            return self.get_by_id(new_id)
        return None

class Students:
    """Service class for managing Student users."""

    def get_by_id(self, student_id: UUID) -> Optional[Student]:
        """Fetches a single student by their ID."""
        user_data = db.get_user_by_id(student_id)
        if user_data and user_data.get('role') == 'student':
            return Student.parse_obj(user_data)
        log.warning(f"Could not find a student with ID {student_id} or user is not a student.")
        return None

    def get_by_parent(self, parent_id: UUID) -> list[Student]:
        """Fetches all students belonging to a specific parent."""
        students_data = db.get_students_by_parent_id(parent_id)
        return [Student.parse_obj(data) for data in students_data]


    def get_all(self) -> list[Student]:
            """Fetches all students from the database."""
            all_students_data = db.get_all_users_by_role('student')
            return [Student.parse_obj(data) for data in all_students_data]

class Users:
    """General user service class."""

    def delete(self, user_id: UUID) -> bool:
        """Deletes any user by their ID."""
        return db.delete_user(user_id)
