'''
This Python file deals with all user instances in this project
'''
import enum
from datetime import time
from decimal import Decimal
from typing import Literal, Optional, Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

# Use the correct import paths as you specified
from ..database.db_handler2 import DatabaseHandler
from ..common.logger import log


# --- Initialize Dynamic ENUMs on Application Startup ---
try:
    # Create a temporary, function-scoped DB handler just for this block.
    # It will be automatically garbage-collected after the enums are created.
    db_temp = DatabaseHandler()
    
    log.info("Dynamically creating ENUM classes from database...")
    UserRole = enum.Enum(
        'UserRole', 
        {label: label for label in db_temp.get_enum_labels('user_role')}
    )
    StudentStatus = enum.Enum(
        'StudentStatus', 
        {label: label for label in db_temp.get_enum_labels('student_status_enum')}
    )
    SubjectEnum = enum.Enum(
        'SubjectEnum', 
        {label: label for label in db_temp.get_enum_labels('subject_enum')}
    )
    log.info("Successfully created ENUM classes.")
    
except Exception as e:
    log.critical(f"FATAL: Could not initialize dynamic ENUMs from database. Error: {e}", exc_info=True)
    # Define placeholder Enums to allow the application to start, though it will likely be non-functional.
    UserRole = enum.Enum('UserRole', {'parent': 'parent', 'student': 'student', 'teacher': 'teacher'})
    StudentStatus = enum.Enum('StudentStatus', {'NONE': 'NONE', 'Alpha': 'Alpha'})
    SubjectEnum = enum.Enum('SubjectEnum', {'Math': 'Math', 'Physics': 'Physics'})


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

# --- Main User Models ---
class User(BaseModel):
    """Abstract base model for all user types using Pydantic V2 syntax."""
    id: UUID
    email: EmailStr
    is_first_sign_in: bool = Field(alias='is_first_sign_in') # Use alias for db compatibility
    role: UserRole
    timezone: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    # Pydantic V2 configuration
    model_config = ConfigDict(
        from_attributes=True,  # Replaces orm_mode
        populate_by_name=True, # Allows using alias and field name
    )

class Parent(User):
    """Model for a Parent user."""
    role: Literal[UserRole.parent.name]
    currency: str

class Teacher(User):
    """Model for a Teacher user."""
    role: Literal[UserRole.teacher.name]
    # Teacher-specific fields can be added here in the future

class Student(User):
    """Model for a Student user. Does not include legacy db fields."""
    role: Literal[UserRole.student.name]
    parent_id: UUID
    student_data: StudentData
    cost: Decimal
    status: StudentStatus
    min_duration_mins: int
    max_duration_mins: int
    grade: Optional[int] = None
    generated_password: Optional[str] = None


# --- Service/Manager Classes (Plural Classes) ---

class Users:
    """Base service class that provides database access and common methods."""
    def __init__(self):
        self.db = DatabaseHandler()

    def delete(self, user_id: UUID) -> bool:
        """Deletes any user by their ID. Inherited by all service classes."""
        return self.db.delete_user(user_id)

class Parents(Users):
    """Service class for managing Parent users."""
    def get_by_id(self, parent_id: UUID) -> Optional[Parent]:
        """Fetches a single parent by their ID."""
        user_data = self.db.get_user_by_id(parent_id)
        if user_data and user_data.get('role') == 'parent':
            return Parent.model_validate(user_data)
        log.warning(f"Could not find a parent with ID {parent_id} or user is not a parent.")
        return None

    def get_all(self) -> list[Parent]:
        """Fetches all parents from the database with detailed error logging."""
        all_parents_data = self.db.get_all_users_by_role('parent')
        validated_parents = []
        for data in all_parents_data:
            try:
                validated_parents.append(Parent.model_validate(data))
            except ValidationError as e:
                # This will log the entire data dictionary that failed
                # along with the specific Pydantic error.
                log.error(f"Pydantic validation failed for parent data: {data}")
                log.error(f"Validation error details: {e}")
                # Decide if you want to skip bad records or stop completely
                continue 
        
        return validated_parents

    def create(self, email: str, password: str, first_name: str, last_name: str, currency: str = 'EGP') -> Optional[Parent]:
        """Creates a new parent and returns the Parent model instance."""
        new_id = self.db.create_parent(
            email=email, password=password, first_name=first_name, 
            last_name=last_name, currency=currency
        )
        return self.get_by_id(new_id) if new_id else None

class Students(Users):
    """Service class for managing Student users."""
    def get_by_id(self, student_id: UUID) -> Optional[Student]:
        """Fetches a single student by their ID."""
        user_data = self.db.get_user_by_id(student_id)
        if user_data and user_data.get('role') == 'student':
            return Student.model_validate(user_data)
        log.warning(f"Could not find a student with ID {student_id} or user is not a student.")
        return None

    def get_by_parent(self, parent_id: UUID) -> list[Student]:
        """Fetches all students belonging to a specific parent."""
        students_data = self.db.get_students_by_parent_id(parent_id)
        return [Student.model_validate(data) for data in students_data]

    def get_all(self) -> list[Student]:
        """Fetches all students from the database with detailed error logging."""
        all_students_data = self.db.get_all_users_by_role('student')
        validated_students = []
        for data in all_students_data:
            try:
                validated_students.append(Student.model_validate(data))
            except ValidationError as e:
                # This will log the entire data dictionary that failed
                # along with the specific Pydantic error.
                log.error(f"Pydantic validation failed for student data: {data}")
                log.error(f"Validation error details: {e}")
                # Skip the bad record and continue processing others
                continue 
        
        return validated_students
    
    # Note: A create method for students would be more complex, requiring details for
    # both the 'users' and 'students' tables. It can be added here following the same pattern.

class Teachers(Users):
    """Service class for managing Teacher users."""
    def get_by_id(self, teacher_id: UUID) -> Optional[Teacher]:
        """Fetches a single teacher by their ID."""
        user_data = self.db.get_user_by_id(teacher_id)
        if user_data and user_data.get('role') == 'teacher':
            return Teacher.model_validate(user_data)
        log.warning(f"Could not find a teacher with ID {teacher_id} or user is not a teacher.")
        return None

    def get_all(self) -> list[Teacher]:
        """Fetches all teachers from the database with detailed error logging."""
        all_teachers_data = self.db.get_all_users_by_role('teacher')
        validated_teachers = []
        for data in all_teachers_data:
            try:
                validated_teachers.append(Teacher.model_validate(data))
            except ValidationError as e:
                # This will log the entire data dictionary that failed
                # along with the specific Pydantic error.
                log.error(f"Pydantic validation failed for teacher data: {data}")
                log.error(f"Validation error details: {e}")
                # Skip the bad record and continue processing others
                continue 
        
        return validated_teachers

    def create(self, email: str, password: str, first_name: str, last_name: str) -> Optional[Teacher]:
        """Creates a new teacher and returns the Teacher model instance."""
        new_id = self.db.create_teacher(
            email=email, password=password, first_name=first_name, last_name=last_name
        )
        return self.get_by_id(new_id) if new_id else None
