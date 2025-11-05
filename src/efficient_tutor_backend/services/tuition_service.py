'''

'''
from typing import Optional, Annotated
from uuid import UUID
import hashlib
from fastapi import Depends
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database.engine import get_db_session
from ..database import models as db_models
from ..database.db_enums import UserRole
from ..common.logger import log
from .user_service import UserService

class TuitionService:
    """
    Service for managing tuition templates (the "schedulable" tuitions).
    """
    def __init__(
        self, 
        db: Annotated[AsyncSession, Depends(get_db_session)],
        user_service: Annotated[UserService, Depends(UserService)]
    ):
        self.db = db
        self.user_service = user_service

    async def get_tuition_by_id(self, tuition_id: UUID) -> db_models.Tuitions | None:
        """
        Fetches a single, fully-loaded tuition object by its ID.
        """
        log.info(f"Fetching tuition by ID: {tuition_id}")
        try:
            stmt = select(db_models.Tuitions).options(
                selectinload(db_models.Tuitions.teacher),
                selectinload(db_models.Tuitions.tuition_template_charges).options(
                    selectinload(db_models.TuitionTemplateCharges.student),
                    selectinload(db_models.TuitionTemplateCharges.parent)
                )
            ).filter(db_models.Tuitions.id == tuition_id)
            
            result = await self.db.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            log.error(f"Database error fetching tuition by ID {tuition_id}: {e}", exc_info=True)
            raise

    async def get_all_tuitions(self, current_user: db_models.Users) -> list[db_models.Tuitions]:
        """
        Fetches all tuitions relevant to the current user, fully loaded.
        """
        log.info(f"Fetching all tuitions for user {current_user.id} (Role: {current_user.role})")
        
        # Base query with all relationships eager-loaded
        stmt = select(db_models.Tuitions).options(
            selectinload(db_models.Tuitions.teacher),
            selectinload(db_models.Tuitions.meeting_link),  # <-- EAGER LOAD THE MEETING LINK
            selectinload(db_models.Tuitions.tuition_template_charges).options(
                selectinload(db_models.TuitionTemplateCharges.student), # Load the student (base User)
                selectinload(db_models.TuitionTemplateCharges.parent)  # Load the parent (base User)
            )
        )       

        # Add role-based filtering
        try:
            if current_user.role == UserRole.TEACHER.value:
                stmt = stmt.filter(db_models.Tuitions.teacher_id == current_user.id)
            
            elif current_user.role == UserRole.PARENT.value:
                stmt = stmt.join(db_models.TuitionTemplateCharges).filter(
                    db_models.TuitionTemplateCharges.parent_id == current_user.id
                )
            
            elif current_user.role == UserRole.STUDENT.value:
                stmt = stmt.join(db_models.TuitionTemplateCharges).filter(
                    db_models.TuitionTemplateCharges.student_id == current_user.id
                )
            else:
                log.warning(f"User {current_user.id} with role {current_user.role} is not authorized to list tuitions.")
                return []
            
            stmt = stmt.order_by(db_models.Tuitions.subject, db_models.Tuitions.lesson_index).distinct()
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
            
        except Exception as e:
            log.error(f"Database error fetching all tuitions for user {current_user.id}: {e}", exc_info=True)
            raise

    async def regenerate_all_tuitions(self) -> bool:
        """
        THIS METHOD SHOULD NOT BE USED UNLESS NECESSARY,
        #TODO: it deletes meeting_link data for now, but after we implemented same tuition_id methodology and after we put the meeting data in its own table, we shouldn't face this issue anymore
        Regenerates all tuition templates based on the current student data.
        This is a full TRUNCATE and-RELOAD operation.
        """
        log.info("Starting regeneration of all tuitions...")
        
        try:
            # 1. Fetch all students with their parent relationships pre-loaded
            student_stmt = select(db_models.Students).options(
                selectinload(db_models.Students.parent)
            )
            all_students = list((await self.db.execute(student_stmt)).scalars().all())
            
            if not all_students:
                log.warning("No students found. Truncating tuitions and finishing.")
                await self.db.execute(text("TRUNCATE TABLE tuitions, tuition_template_charges RESTART IDENTITY CASCADE"))
                return True

            # 2. Fetch existing tuitions to preserve meeting links
            existing_links = {}
            links_stmt = select(db_models.Tuitions.id, db_models.Tuitions.meeting_link).filter(
                db_models.Tuitions.meeting_link.is_not(None)
            )
            for row in (await self.db.execute(links_stmt)).all():
                existing_links[row.id] = row.meeting_link
            log.info(f"Preserved {len(existing_links)} existing meeting links.")

            # 3. Group students in Python (same logic as before)
            grouped_students = {}
            for student in all_students:
                if not student.student_data or not student.student_data.get('subjects'):
                    continue
                
                for subject_info in student.student_data['subjects']:
                    for teacher_id in subject_info.get('sharedWith', []):
                        key = (subject_info['name'], teacher_id)
                        if key not in grouped_students:
                            grouped_students[key] = []
                        grouped_students[key].append(student)

            # 4. Prepare new ORM objects
            new_tuitions = []
            new_charges = []
            for (subject_name, teacher_id), students_in_group in grouped_students.items():
                
                lesson_index = 1 # Assuming this is still 1
                student_ids = sorted([s.id for s in students_in_group])
                
                tuition_id = self._generate_deterministic_id(
                    subject=subject_name,
                    lesson_index=lesson_index,
                    teacher_id=teacher_id,
                    student_ids=student_ids
                )
                
                new_tuition = db_models.Tuitions(
                    id=tuition_id,
                    teacher_id=teacher_id,
                    subject=subject_name,
                    lesson_index=lesson_index,
                    min_duration_minutes=students_in_group[0].min_duration_mins,
                    max_duration_minutes=students_in_group[0].max_duration_mins,
                    meeting_link=existing_links.get(tuition_id) # Restore link if it existed
                )
                new_tuitions.append(new_tuition)
                
                for student in students_in_group:
                    new_charges.append(db_models.TuitionTemplateCharges(
                        tuition_id=tuition_id,
                        student_id=student.id,
                        parent_id=student.parent_id,
                        cost=student.cost
                    ))
            
            log.info(f"Generated {len(new_tuitions)} new tuitions and {len(new_charges)} charges.")

            # 5. Perform the database transaction
            # We must use `text()` for TRUNCATE with SQLAlchemy Core
            await self.db.execute(text("TRUNCATE TABLE tuitions, tuition_template_charges RESTART IDENTITY CASCADE"))
            
            # Add all new objects to the session
            self.db.add_all(new_tuitions)
            self.db.add_all(new_charges)
            
            log.info("Successfully regenerated all tuitions.")
            return True

        except Exception as e:
            log.error(f"A critical error occurred during tuition regeneration: {e}", exc_info=True)
            raise

    def _generate_deterministic_id(self, subject: str, lesson_index: int, teacher_id: UUID, student_ids: list[UUID]) -> UUID:
        """
        Creates a stable, deterministic UUID for a tuition based on its core properties.
        """
        id_string = f"{subject}:{lesson_index}:{teacher_id}:{','.join(map(str, sorted(student_ids)))}"
        hasher = hashlib.sha256(id_string.encode('utf-8'))
        return UUID(bytes=hasher.digest()[:16])
