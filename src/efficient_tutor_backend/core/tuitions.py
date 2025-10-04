'''
This file processes everything related to tuitions
'''
import enum
import hashlib
from datetime import timedelta
from typing import Optional, Any
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, field_serializer, computed_field

from ..common.logger import log
from ..database.db_handler2 import DatabaseHandler
from .users import (
    UserRole, ApiUser, Student, Parent, Teacher, Students, Parents, Teachers,
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

    def __repr__(self) -> str:
        """
        Provides an unambiguous, developer-friendly representation of the Tuition object.
        """
        student_count = len(self.charges)
        return (
            f"Tuition(id={self.id!r}, subject='{self.subject.value}', "
            f"lesson_index={self.lesson_index}, teacher='{self.teacher.email}', "
            f"students={student_count})"
        )

    def __str__(self) -> str:
        """
        Provides a clean, human-readable summary of the Tuition object.
        """
        # Nicely format the list of student names
        student_names = ", ".join(
            [charge.student.first_name for charge in self.charges if charge.student.first_name]
        )
        # Fallback if names aren't set
        if not student_names:
            student_names = f"{len(self.charges)} student(s)"
        
        # Use the teacher's first name if available, otherwise their email
        teacher_name = self.teacher.first_name or self.teacher.email

        return f"[{self.subject.value} - Lesson {self.lesson_index}] with {teacher_name} for {student_names}"


# --- NEW: API-Specific Models for Tuitions ---

class ApiTuitionCharge(BaseModel):
    """A lean representation of a student charge for the teacher's view."""
    student: ApiUser
    cost: Decimal

    model_config = ConfigDict(from_attributes=True)

class ApiTuitionForGuardian(BaseModel):
    """The API model for a tuition as seen by a parent or student."""
    # Internal fields for computation
    source: Tuition
    viewer_id: UUID

    @computed_field
    @property
    def id(self) -> str:
        return str(self.source.id)

    @computed_field
    @property
    def subject(self) -> str:
        return self.source.subject.value
        
    @computed_field
    @property
    def attendee_names(self) -> list[str]:
        """Shows all attendees for context."""
        names = []
        for charge in self.source.charges:
            full_name = f"{charge.student.first_name or ''} {charge.student.last_name or ''}".strip()
            names.append(full_name or "Unknown Student")
        return names

    @computed_field
    @property
    def charge(self) -> str:
        """Finds the specific cost for the viewer (parent or student)."""
        for charge in self.source.charges:
            if charge.parent.id == self.viewer_id or charge.student.id == self.viewer_id:
                return f"{charge.cost:.2f}"
        return "0.00" # Fallback

class ApiTuitionForTeacher(BaseModel):
    """The API model for a tuition as seen by a teacher."""
    source: Tuition # Keep this simple, we'll use a helper for transformation

    @computed_field
    @property
    def id(self) -> str:
        return str(self.source.id)

    @computed_field
    @property
    def subject(self) -> str:
        return self.source.subject.value

    @computed_field
    @property
    def attendee_names(self) -> list[str]:
        """Shows all attendees for context."""
        names = []
        for charge in self.source.charges:
            full_name = f"{charge.student.first_name or ''} {charge.student.last_name or ''}".strip()
            names.append(full_name or "Unknown Student")
        return names

    @computed_field
    @property
    def total_cost(self) -> str:
        """Calculates the total value of the tuition."""
        total = sum(charge.cost for charge in self.source.charges)
        return f"{total:.2f}"

    @computed_field
    @property
    def charges(self) -> list[ApiTuitionCharge]:
        """Provides a detailed list of charges for the teacher."""
        return [ApiTuitionCharge(student=ApiUser.model_validate(c.student), cost=c.cost) for c in self.source.charges]

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

    def get_by_id(self, tuition_id: UUID) -> Optional[Tuition]:
        """
        CORRECTED: Fetches a single, fully hydrated Tuition object by its ID
        using an efficient, bulk-fetching hydration pattern.
        """
        # 1. Fetch the single raw tuition data.
        raw_data = self.db.get_tuition_raw_by_id(tuition_id)
        if not raw_data:
            return None

        # 2. Collect all unique user IDs needed from this single raw object.
        user_ids_to_fetch = set()
        user_ids_to_fetch.add(raw_data['teacher_id'])
        if raw_data.get('charges'):
            for charge in raw_data['charges']:
                user_ids_to_fetch.add(UUID(charge['student_id']))
                user_ids_to_fetch.add(UUID(charge['parent_id']))

        # 3. Fetch all required user details in a single, efficient batch.
        all_needed_users_data = self.db.get_users_by_ids(list(user_ids_to_fetch))

        # 4. Create lookup dictionaries from the fetched data.
        all_students_dict = {
            s['id']: Student.model_validate(s) for s in all_needed_users_data if s['role'] == 'student'
        }
        all_parents_dict = {
            p['id']: Parent.model_validate(p) for p in all_needed_users_data if p['role'] == 'parent'
        }
        all_teachers_dict = {
            t['id']: Teacher.model_validate(t) for t in all_needed_users_data if t['role'] == 'teacher'
        }
        
        # 5. Hydrate the final Tuition object.
        teacher_obj = all_teachers_dict.get(raw_data['teacher_id'])
        if not teacher_obj:
            log.error(f"Hydration failed for tuition {tuition_id}: Teacher {raw_data['teacher_id']} not found.")
            return None # Data integrity issue

        tuition_charges = []
        if raw_data.get('charges'):
            for charge_data in raw_data['charges']:
                student_obj = all_students_dict.get(UUID(charge_data['student_id']))
                parent_obj = all_parents_dict.get(UUID(charge_data['parent_id']))
                if student_obj and parent_obj:
                    tuition_charges.append(TuitionCharge(student=student_obj, parent=parent_obj, cost=charge_data['cost']))
        
        return Tuition(
            id=raw_data['id'],
            subject=raw_data['subject'],
            lesson_index=raw_data['lesson_index'],
            min_duration_minutes=raw_data['min_duration_minutes'],
            max_duration_minutes=raw_data['max_duration_minutes'],
            meeting_link=raw_data['meeting_link'],
            teacher=teacher_obj,
            charges=tuition_charges
        )
    def get_all(self, viewer_id: UUID) -> list[Tuition]:
        """
        Fetches all tuitions from the database and constructs them into Tuition models.
        This method orchestrates calls to other services to build the final objects.
        """
        log.info("Fetching and orchestrating all tuitions...")
        role = self.db.identify_user_role(viewer_id)
        
        # 1. Get the raw tuition data structures from the database only related to specific user
        raw_tuition_list = []
        if role == UserRole.teacher.name:
            raw_tuition_list = self.db.get_all_tuitions_raw_for_teacher(viewer_id)
        elif role == UserRole.parent.name:
            raw_tuition_list = self.db.get_all_tuitions_raw_for_parent(viewer_id)
        elif role == UserRole.student.name:
            raw_tuition_list = self.db.get_all_tuitions_raw_for_student(viewer_id)
        else:
            raise UnauthorizedRoleError(f"User with role '{role}' is not authorized to view tuitions.")

        if not raw_tuition_list:
            log.warning("No raw tuitions found in the database for this viewer.")
            return []

        # 2. OPTIMIZATION: Collect all unique user IDs needed from the raw data.
        student_ids = set()
        parent_ids = set()
        teacher_ids = set()
        for raw_data in raw_tuition_list:
            teacher_ids.add(raw_data['teacher_id'])
            if raw_data.get('charges'):
                for charge in raw_data['charges']:
                    student_ids.add(charge['student_id'])
                    parent_ids.add(charge['parent_id'])

        # 3. OPTIMIZATION: Fetch all required users in efficient batches.
        # We use our powerful get_users_by_ids method here.
        all_needed_users_data = self.db.get_users_by_ids(list(student_ids | parent_ids | teacher_ids))
        
        # 4. Create lookup dictionaries from the fetched data.
        all_students_dict = {
            s['id']: Student.model_validate(s) for s in all_needed_users_data if s['role'] == 'student'
        }
        all_parents_dict = {
            p['id']: Parent.model_validate(p) for p in all_needed_users_data if p['role'] == 'parent'
        }
        all_teachers_dict = {
            t['id']: Teacher.model_validate(t) for t in all_needed_users_data if t['role'] == 'teacher'
        }
              
        # 5. Hydrate the final Tuition objects 
        final_tuitions = []
        try:
            # 2. Assemble the final Pydantic models in Python.
            for raw_data in raw_tuition_list:
                # Look up the full Teacher object from our eager-loaded dictionary.
                teacher_obj = all_teachers_dict.get(raw_data['teacher_id'])
                if not teacher_obj:
                    log.warning(f"Skipping tuition {raw_data['id']}: teacher {raw_data['teacher_id']} not found.")
                    continue

                tuition_charges = []
                for charge_data in raw_data.get('charges', []):
                    # Look up the full Student and Parent objects.
                    student_obj = all_students_dict.get(UUID(charge_data['student_id']))
                    parent_obj = all_parents_dict.get(UUID(charge_data['parent_id']))

                    if not student_obj or not parent_obj:
                        log.warning(f"Skipping charge in tuition {raw_data['id']}: student or parent not found.")
                        continue
                    
                    tuition_charges.append(
                        TuitionCharge(
                            student=student_obj,
                            parent=parent_obj,
                            cost=charge_data['cost']
                        )
                    )
                
                # If after checking, there are no valid charges, skip this tuition.
                if not tuition_charges:
                    log.warning(f"Skipping tuition {raw_data['id']}: no valid charges could be constructed.")
                    continue

                # Construct the final, validated Tuition object.
                # Pydantic will handle the timedelta conversion from _minutes fields.
                final_tuitions.append(
                    Tuition(
                        id=raw_data['id'],
                        subject=raw_data['subject'],
                        lesson_index=raw_data['lesson_index'],
                        min_duration_minutes=raw_data['min_duration_minutes'],
                        max_duration_minutes=raw_data['max_duration_minutes'],
                        meeting_link=raw_data['meeting_link'],
                        teacher=teacher_obj,
                        charges=tuition_charges
                    )
                )
            return final_tuitions

        except Exception as e:
            # This will now catch both DB errors and Pydantic validation errors during assembly.
            log.error(f"Failed to fetch and construct all tuitions: {e}", exc_info=True)
            # You might want to re-raise the exception depending on your error handling strategy.
            raise

    def get_all_for_api(self, viewer_id: UUID) -> list[dict[str, Any]]:
        """
        NEW: Public dispatcher that returns a lean list of tuitions formatted
        correctly for the viewer's role.
        """
        role = self.db.identify_user_role(viewer_id)
        rich_tuitions = self.get_all(viewer_id) # Get the filtered rich objects

        if role == UserRole.teacher.name:
            return self._format_for_teacher_api(rich_tuitions)
        elif role in (UserRole.parent.name, UserRole.student.name):
            return self._format_for_guardian_api(rich_tuitions, viewer_id)
        else:
            raise UnauthorizedRoleError(f"User with role '{role}' is not authorized to view tuitions.")

    def _format_for_teacher_api(self, tuitions: list[Tuition]) -> list[dict[str, Any]]:
        """Formats tuitions for a teacher's view."""
        api_models = [ApiTuitionForTeacher(source=t) for t in tuitions]
        return [model.model_dump(exclude={'source'}) for model in api_models]

    def _format_for_guardian_api(self, tuitions: list[Tuition], viewer_id: UUID) -> list[dict[str, Any]]:
        """Formats tuitions for a parent's or student's view."""
        api_models = [ApiTuitionForGuardian(source=t, viewer_id=viewer_id) for t in tuitions]
        return [model.model_dump(exclude={'source', 'viewer_id'}) for model in api_models]
    
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

                # NEW: Run integrity check immediately after regeneration for verification.
                log.info("Running post-regeneration integrity check...")
                self.verify_data_integrity()
            else:
                log.error("Tuition regeneration transaction failed.")
            return success
        except Exception as e:
            log.critical(f"A critical error occurred during tuition regeneration: {e}", exc_info=True)
            return False

    def verify_data_integrity(self) -> list[dict[str, Any]]:
        """
        NEW: Service layer method to run the diagnostic check for tuition data.
        This method finds and logs tuitions with missing linked data.
        It can be called on demand by admin tools or scheduled tasks.
        """
        log.info("Verifying tuition data integrity...")
        problematic_tuitions = self.db.check_tuition_data_integrity()
        
        if problematic_tuitions:
            log.warning(f"Data integrity check found {len(problematic_tuitions)} problematic tuitions.")
            for problem in problematic_tuitions:
                log.warning(f"  - Tuition ID: {problem['tuition_id']}, Teacher Issue: {problem['teacher_issue']}, Charges Issue: {problem['charges_issue']}")
        else:
            log.info("Tuition data integrity check passed with no issues.")
            
        return problematic_tuitions
