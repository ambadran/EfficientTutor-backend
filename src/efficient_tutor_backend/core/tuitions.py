'''
This file processes everything related to tuitions
'''
import enum
import hashlib
from datetime import timedelta
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_serializer

# Assuming these are in the same directory or accessible via PYTHONPATH
from ..common.logger import log
from ..database.db_handler2 import DatabaseHandler
from .users import (
    Student, Parent, Teacher, Students, Parents, Teachers,
    SubjectEnum # Assuming you move the dynamic Enum creation here or a central place
)


# --- Data Models ---

class TuitionCharge(BaseModel):
    """Represents one student's charge and related entities within a tuition."""
    student: Student
    parent: Parent
    cost: float

class Tuition(BaseModel):
    """
    A self-contained descriptor for a specific tuition session, built from DB data.
    """
    id: UUID
    teacher: Teacher
    subject: SubjectEnum
    charges: list[TuitionCharge]
    min_duration: timedelta = Field(..., alias='min_duration_minutes')
    max_duration: timedelta = Field(..., alias='max_duration_minutes')
    lesson_index: int
    meeting_link: Optional[str] = None

    # This replaces the old 'json_encoders' logic
    @field_serializer('min_duration', 'max_duration')
    def serialize_duration_to_minutes(self, value: timedelta) -> float:
        """Serializes timedelta objects into a float representing total minutes."""
        return value.total_seconds() / 60

    # This replaces the old 'class Config'
    model_config = ConfigDict(
        from_attributes=True,      # Replaces orm_mode = True
        populate_by_name=True,     # Replaces allow_population_by_field_name = True
    )

# --- Service Class ---

class Tuitions:
    """
    Service class to handle all business logic related to tuitions.
    Primary responsibility is regenerating all tuitions based on current student data.
    """
    def __init__(self):
        self.db = DatabaseHandler()
        # Instantiate services to fetch user data
        self.students_service = Students()
        self.parents_service = Parents()
        self.teachers_service = Teachers()

    def _generate_deterministic_id(self, subject: str, lesson_index: int, teacher_id: UUID, student_ids: list[UUID]) -> UUID:
        """
        Creates a stable, deterministic UUID for a tuition based on its core, unchanging properties.
        This ensures that regenerating the same tuition results in the same ID.
        """
        # Sort student IDs to ensure consistency regardless of order
        sorted_student_ids = sorted(student_ids)
        
        id_string = f"{subject}:{lesson_index}:{teacher_id}:{','.join(map(str, sorted_student_ids))}"
        
        # Hash the string using SHA256 and take the first 16 bytes for the UUID
        hasher = hashlib.sha256(id_string.encode('utf-8'))
        return UUID(bytes=hasher.digest()[:16])

    def get_all(self) -> list[Tuition]:
        """
        Fetches all tuitions from the database and constructs them into Tuition models.
        """
        log.info("Fetching all tuitions...")
        try:
            tuition_data_list = self.db.get_all_tuitions()
            if not tuition_data_list:
                log.warning("No tuitions found in the database.")
                return []
            
            # The DB method is designed to return data pre-structured for this model
            return [Tuition.parse_obj(data) for data in tuition_data_list]
        except Exception as e:
            log.error(f"Failed to fetch and construct all tuitions: {e}", exc_info=True)
            return []

    def regenerate_all_tuitions(self) -> bool:
        """
        The main method to regenerate all tuitions. It reads all necessary student and teacher
        data, constructs the tuition structures, and passes them to the database handler
        to be transactionally inserted.
        
        This is the primary "create" and "update" mechanism.
        """
        log.info("Starting regeneration of all tuitions...")
        all_students = self.students_service.get_all()
        if not all_students:
            log.warning("No students found. Aborting tuition regeneration.")
            # We can also choose to simply truncate the tables here if that's the desired behavior.
            self.db.truncate_tuitions()
            return True

        tuitions_to_create = []
        
        # --- Business Logic: Define how tuitions are created ---
        # Here, we assume a tuition is formed for each subject a student takes.
        # Students taking the same subject are grouped.
        
        # Group students by subject and the teachers they share that subject with
        grouped_students = {} # Key: (subject_name, teacher_id), Value: list of students
        
        for student in all_students:
            if not student.student_data or not student.student_data.subjects:
                continue
            
            for subject_info in student.student_data.subjects:
                # 'sharedWith' contains teacher IDs
                for teacher_id in subject_info.sharedWith:
                    key = (subject_info.name.value, teacher_id)
                    if key not in grouped_students:
                        grouped_students[key] = []
                    grouped_students[key].append(student)

        # Now, create a tuition object for each group
        for (subject_name, teacher_id), students_in_group in grouped_students.items():
            
            # Let's assume lesson_index is 1 for now, this could be more complex later
            lesson_index = 1
            
            student_ids = [s.id for s in students_in_group]
            tuition_id = self._generate_deterministic_id(
                subject=subject_name,
                lesson_index=lesson_index,
                teacher_id=teacher_id,
                student_ids=student_ids
            )
            
            # Prepare the charges for the tuition_template_charges table
            charges_to_create = []
            for student in students_in_group:
                charges_to_create.append({
                    "student_id": student.id,
                    "parent_id": student.parent_id,
                    "cost": student.cost # Using the student's default cost
                })

            # For now, we use the student's default min/max duration.
            # This could be averaged or taken from the first student.
            min_duration = students_in_group[0].min_duration_mins
            max_duration = students_in_group[0].max_duration_mins
            
            tuitions_to_create.append({
                "id": tuition_id,
                "teacher_id": teacher_id,
                "subject": subject_name,
                "lesson_index": lesson_index,
                "min_duration_minutes": min_duration,
                "max_duration_minutes": max_duration,
                "charges": charges_to_create
            })

        log.info(f"Generated {len(tuitions_to_create)} tuitions to be created.")
        
        # Pass the prepared data to the database handler for transactional execution
        try:
            success = self.db.regenerate_all_tuitions_transaction(tuitions_to_create)
            if success:
                log.info("Successfully regenerated all tuitions in the database.")
            else:
                log.error("Tuition regeneration transaction failed.")
            return success
        except Exception as e:
            log.critical(f"A critical error occurred during tuition regeneration: {e}", exc_info=True)
            return False
