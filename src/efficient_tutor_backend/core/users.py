'''
This Python file deals with all user instances in this project
'''
import enum
from datetime import time
from decimal import Decimal
from typing import Literal, Optional, Any, Type, TypeVar
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict, ValidationError

# Use the correct import paths as you specified
from ..database.db_handler2 import DatabaseHandler
from ..common.logger import log

# --- Initialize Dynamic ENUMs on Application Startup ---
class ListableEnum(str, enum.Enum):
    """A custom Enum base class that includes a helper method to list all member names."""
    @classmethod
    def get_all_names(cls) -> list[str]:
        """Returns a list of all member string values."""
        return [member.value for member in cls]
try:
    db_temp = DatabaseHandler()
    log.info("Dynamically creating ENUM classes from database...")
    UserRole = ListableEnum('UserRole', {label: label for label in db_temp.get_enum_labels('user_role')})
    StudentStatus = ListableEnum('StudentStatus', {label: label for label in db_temp.get_enum_labels('student_status_enum')})
    SubjectEnum = ListableEnum('SubjectEnum', {label: label for label in db_temp.get_enum_labels('subject_enum')})
    log.info("Successfully created ENUM classes.")
except Exception as e:
    log.error(f"FATAL: Could not initialize dynamic ENUMs. Error: {e}", exc_info=True)
    raise 


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

# --- Generic API User Model ---
class ApiUser(BaseModel):
    """A lean, generic representation of a user for simple API list responses."""
    id: UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

# --- Service/Manager Classes (Plural Classes) ---
UserType = TypeVar("UserType", bound=User)

class Users:
    """Base service class that provides database access and common methods."""
    # Subclasses MUST define these two attributes
    _model: Type[UserType]
    _role: UserRole
    def __init__(self):
        self.db = DatabaseHandler()

    def get_by_id(self, user_id: UUID) -> Optional[UserType]:
        """
        A generic method to fetch any user by their ID, validating against
        the specific subclass model and role.
        """
        user_data = self.db.get_user_by_id(user_id)
        # Use the class attributes from the subclass (e.g., Parents._model, Parents._role)
        if user_data and user_data.get('role') == self._role.name:
            return self._model.model_validate(user_data)
        log.warning(f"Could not find a {self._role.name} with ID {user_id}.")
        return None

    def get_all(self) -> list[UserType]:
        """
        A generic method to fetch all users of a specific role.
        Includes detailed error logging for validation failures.
        """
        all_user_data = self.db.get_all_users_by_role(self._role.name)
        validated_users = []
        for data in all_user_data:
            try:
                # Use the subclass's specific model for validation
                validated_users.append(self._model.model_validate(data))
            except ValidationError as e:
                log.error(f"Pydantic validation failed for {self._role.name} data: {data}")
                log.error(f"Validation error details: {e}")
                continue 
        return validated_users

    def get_all_for_api(self) -> list[dict[str, Any]]:
        """
        A generic method to fetch all users of a specific type and format them
        into a lean list of dictionaries for API responses.
        """
        log.info(f"Fetching and preparing API list for {self.__class__.__name__}...")
        all_users_of_type = self.get_all()
        api_users = [ApiUser.model_validate(user) for user in all_users_of_type]
        return [model.model_dump() for model in api_users]

    def delete(self, user_id: UUID) -> bool:
        """Deletes any user by their ID. Inherited by all service classes."""
        return self.db.delete_user(user_id)

class Parents(Users):
    """Service class for managing Parent users."""
    _model = Parent
    _role = UserRole.parent
    def create(self, email: str, password: str, first_name: str, last_name: str, currency: str = 'EGP') -> Optional[Parent]:
        """Creates a new parent and returns the Parent model instance."""
        new_id = self.db.create_parent(
            email=email, password=password, first_name=first_name, 
            last_name=last_name, currency=currency
        )
        return self.get_by_id(new_id) if new_id else None

    def get_all_for_api(self, teacher_id: UUID) -> list[dict[str, Any]]:
        """
        OVERRIDDEN: Fetches a lean list of ONLY the parents associated with a
        specific teacher for API responses.
        """
        log.info(f"Fetching and preparing API list of parents for teacher {teacher_id}...")
        
        # 1. Get the list of relevant parent IDs from the database.
        parent_ids = self.db.get_parent_ids_for_teacher(teacher_id)
        if not parent_ids:
            return []
            
        # 2. Fetch all user details for those specific parents in one batch.
        parents_data = self.db.get_users_by_ids(parent_ids)
        
        # 3. Hydrate the raw data into our rich Pydantic models.
        validated_parents = [Parent.model_validate(data) for data in parents_data]
        
        # 4. Convert the rich models to the lean ApiUser models.
        api_users = [ApiUser.model_validate(user) for user in validated_parents]
        
        # 5. Return the final list of dictionaries.
        return [model.model_dump() for model in api_users]

class Students(Users):
    """Service class for managing Student users."""
    _model = Student
    _role = UserRole.student
    def get_by_parent(self, parent_id: UUID) -> list[Student]:
        """Fetches all students belonging to a specific parent."""
        students_data = self.db.get_students_by_parent_id(parent_id)
        return [Student.model_validate(data) for data in students_data]

   
    # Note: A create method for students would be more complex, requiring details for
    # both the 'users' and 'students' tables. It can be added here following the same pattern.

class Teachers(Users):
    """Service class for managing Teacher users."""
    _model = Teacher
    _role = UserRole.teacher

    def create(self, email: str, password: str, first_name: str, last_name: str) -> Optional[Teacher]:
        """Creates a new teacher and returns the Teacher model instance."""
        new_id = self.db.create_teacher(
            email=email, password=password, first_name=first_name, last_name=last_name
        )
        return self.get_by_id(new_id) if new_id else None
