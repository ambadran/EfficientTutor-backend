'''

'''
import hashlib
from typing import Optional, Annotated, Any
from uuid import UUID
from decimal import Decimal
from fastapi import Depends, HTTPException, status
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database.engine import get_db_session
from ..database import models as db_models
from ..database.db_enums import UserRole
from ..models import tuition as tuition_models
from ..models import user as user_models
from ..models import meeting_links as meeting_link_models
from ..common.logger import log
from .user_service import UserService


class TuitionService:
    """
    REFACTORED: Service for managing tuition templates, including authorization,
    read operations, and meeting link management.
    """
    def __init__(
        self, 
        db: Annotated[AsyncSession, Depends(get_db_session)],
        user_service: Annotated[UserService, Depends(UserService)]
    ):
        self.db = db
        self.user_service = user_service

    # --- 1. Authorization Helpers ---

    def _authorize_write_access(self, tuition: db_models.Tuitions, current_user: db_models.Users):
        """
        Checks if a user has write/delete permission (Teacher owner only).
        Raises 403 HTTPException if the user is not the owner.
        """
        if not (current_user.role == UserRole.TEACHER.value and tuition.teacher_id == current_user.id):
            log.warning(f"SECURITY: User {current_user.id} tried to write to tuition {tuition.id} owned by {tuition.teacher_id}.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this resource."
            )

    async def _authorize_read_access(self, tuition: db_models.Tuitions, current_user: db_models.Users):
        """
        Checks if a user (Teacher, Parent, or Student) has read permission
        for a *specific* tuition.
        """
        # 1. Check if Teacher is the owner
        if current_user.role == UserRole.TEACHER.value:
            if tuition.teacher_id == current_user.id:
                return  # Allow
        
        # 2. Check if Student is in the charges
        elif current_user.role == UserRole.STUDENT.value:
            if any(charge.student_id == current_user.id for charge in tuition.tuition_template_charges):
                return  # Allow
        
        # 3. Check if Parent is in the charges
        elif current_user.role == UserRole.PARENT.value:
            if any(charge.parent_id == current_user.id for charge in tuition.tuition_template_charges):
                return  # Allow
        
        # 4. If none passed, deny access
        log.warning(f"SECURITY: User <{current_user.id}-{current_user.first_name} {current_user.last_name}> tried to read tuition {tuition.id} without permission.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this resource."
        )

    # --- 2. Internal Fetchers (No Auth) ---

    async def _get_tuition_by_id_internal(self, tuition_id: UUID) -> db_models.Tuitions:
        # ... (this method is unchanged) ...
        log.info(f"Internal fetch for tuition by ID: {tuition_id}")
        try:
            stmt = select(db_models.Tuitions).options(
                selectinload(db_models.Tuitions.teacher),
                selectinload(db_models.Tuitions.meeting_link),
                selectinload(db_models.Tuitions.tuition_template_charges).options(
                    selectinload(db_models.TuitionTemplateCharges.student).joinedload('*'),
                    selectinload(db_models.TuitionTemplateCharges.parent).joinedload('*')
                )
            ).filter(db_models.Tuitions.id == tuition_id)
            
            result = await self.db.execute(stmt)
            tuition = result.scalars().first()
            if not tuition:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tuition not found.")
            return tuition
        except Exception as e:
            log.error(f"Error in _get_tuition_by_id_internal: {e}", exc_info=True)
            raise
    
    # --- 3. NEW Internal Logic Method ---
    
    async def get_all_tuitions_orm(self, current_user: db_models.Users) -> list[db_models.Tuitions]:
        """
        NEW: Internal-facing method. Fetches all ORM Tuition objects
        visible to the current user (Teacher, Parent, or Student).
        This method is used by other services (like TimeTableService).
        """
        log.info(f"Internal ORM fetch for all tuitions for user {current_user.id} (Role: {current_user.role}).")
        
        # 1. Base query with eager loading
        stmt = select(db_models.Tuitions).options(
            selectinload(db_models.Tuitions.teacher),
            selectinload(db_models.Tuitions.meeting_link),
            selectinload(db_models.Tuitions.tuition_template_charges).options(
                selectinload(db_models.TuitionTemplateCharges.student).joinedload('*'),
                selectinload(db_models.TuitionTemplateCharges.parent).joinedload('*')
            )
        ).order_by(db_models.Tuitions.subject, db_models.Tuitions.lesson_index).distinct()

        try:
            # 2. Build filter based on role (This *is* the read authorization)
            if current_user.role == UserRole.TEACHER.value:
                stmt = stmt.filter(db_models.Tuitions.teacher_id == current_user.id)
            
            elif current_user.role == UserRole.PARENT.value:
                # We must load the parent's students to filter
                await self.db.refresh(current_user, ['students'])
                student_ids = [student.id for student in current_user.students]
                if not student_ids:
                    return [] # This parent has no students
                
                stmt = stmt.join(db_models.TuitionTemplateCharges).filter(
                    db_models.TuitionTemplateCharges.student_id.in_(student_ids)
                )
            
            elif current_user.role == UserRole.STUDENT.value:
                stmt = stmt.join(db_models.TuitionTemplateCharges).filter(
                    db_models.TuitionTemplateCharges.student_id == current_user.id
                )
            
            else: 
                log.warning(f"User {current_user.id} with role {current_user.role} is not authorized to list tuitions.")
                return []
            
            # 3. Execute
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        
        except Exception as e:
            log.error(f"Database error in get_all_tuitions_orm for user {current_user.id}: {e}", exc_info=True)
            raise

    # --- 4. API-Facing Read Methods (With Auth) ---

    async def get_tuition_by_id_for_api(self, tuition_id: UUID, current_user: db_models.Users) -> tuition_models.TuitionReadRoleBased:
        """
        Fetches a single tuition by ID, formats it for the API,
        and verifies the user is authorized to read it.
        """
        log.info(f"User {current_user.id} requesting tuition {tuition_id}")
        try:
            tuition_orm = await self._get_tuition_by_id_internal(tuition_id)
            await self._authorize_read_access(tuition_orm, current_user)
            return self._format_tuition_for_api(tuition_orm, current_user)
        
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Error in get_tuition_by_id_for_api for tuition {tuition_id}: {e}", exc_info=True)
            raise

    async def get_all_tuitions_for_api(self, current_user: db_models.Users) -> tuition_models.TuitionReadRoleBased:
        """
        REFACTORED: API-facing method. Fetches all relevant tuitions
        and formats them into the correct API response.
        """
        try:
            # 1. Get the rich ORM objects
            tuitions_orm = await self.get_all_tuitions_orm(current_user)
            
            # 2. Format them for the API
            return [self._format_tuition_for_api(tuition, current_user) for tuition in tuitions_orm]
        
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Database error in get_all_tuitions_for_api for user {current_user.id}: {e}", exc_info=True)
            raise

    # --- 5. API-Facing Write Methods (With Auth) ---

    async def update_tuition_by_id(self, tuition_id: UUID, update_data: tuition_models.TuitionUpdate, current_user: db_models.Users) -> tuition_models.TuitionReadForTeacher:
        """
        Updates the editable fields of a tuition (durations and student costs).
        Restricted to the Teacher who owns the tuition.
        """
        log.info(f"User {current_user.id} attempting to update tuition {tuition_id}.")
        
        if not update_data.model_dump(exclude_unset=True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided."
            )
            
        try:
            # 1. Fetch the complete tuition object, which eager-loads charges
            tuition_orm = await self._get_tuition_by_id_internal(tuition_id)
            
            # 2. Authorize that the current user is the teacher owning this tuition
            self._authorize_write_access(tuition_orm, current_user)
            
            # 3. Update Durations
            min_updated = update_data.min_duration_minutes is not None
            max_updated = update_data.max_duration_minutes is not None

            # Start with the existing values
            new_min = tuition_orm.min_duration_minutes
            new_max = tuition_orm.max_duration_minutes

            # Overwrite with new values if they were provided
            if min_updated:
                new_min = update_data.min_duration_minutes
            if max_updated:
                new_max = update_data.max_duration_minutes

            # Validate consistency
            if new_max < new_min:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="max_duration_minutes cannot be less than min_duration_minutes."
                )
            
            # Apply the final, validated values
            tuition_orm.min_duration_minutes = new_min
            tuition_orm.max_duration_minutes = new_max

            # 4. Update Charges
            if update_data.charges is not None:
                charge_map = {charge.student_id: charge for charge in tuition_orm.tuition_template_charges}
                
                valid_student_ids = set(charge_map.keys())
                incoming_student_ids = {charge.student_id for charge in update_data.charges}
                
                invalid_ids = incoming_student_ids - valid_student_ids
                if invalid_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"One or more student IDs are not part of this tuition: {', '.join(map(str, invalid_ids))}"
                    )
                
                # Apply the cost updates
                for charge_update in update_data.charges:
                    charge_map[charge_update.student_id].cost = charge_update.cost

            # 5. Commit and Return
            self.db.add(tuition_orm)
            await self.db.flush()
            
            # The ORM object is now updated. We can format it for the response.
            return self._format_for_teacher_api(tuition_orm)

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Error in update_tuition_by_id for tuition {tuition_id}: {e}", exc_info=True)
            raise

    async def create_meeting_link_for_api(self, tuition_id: UUID, data: meeting_link_models.MeetingLinkCreate, current_user: db_models.Users) -> meeting_link_models.MeetingLinkRead:
        """
        Creates a new meeting link for a tuition.
        Restricted to the Teacher who owns the tuition.
        """
        log.info(f"User {current_user.id} attempting to create meeting link for tuition {tuition_id}.")
        try:
            # 1. Fetch parent tuition
            tuition = await self._get_tuition_by_id_internal(tuition_id)
            
            # 2. Authorize
            self._authorize_write_access(tuition, current_user)
            
            # 3. Check for existing link (1-to-1)
            if tuition.meeting_link:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A meeting link for this tuition already exists.")
            
            # 4. Create new link
            new_link = db_models.MeetingLinks(
                tuition_id=tuition_id,
                meeting_link_type=data.meeting_link_type.value, # Use .value
                meeting_link=str(data.meeting_link), # Cast HttpUrl to str
                meeting_id=data.meeting_id,
                meeting_password=data.meeting_password
            )
            self.db.add(new_link)
            await self.db.flush()
            
            # 5. Format and return
            return meeting_link_models.MeetingLinkRead.model_validate(new_link)

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Error in create_meeting_link_for_api for tuition {tuition_id}: {e}", exc_info=True)
            raise

    async def update_meeting_link_for_api(self, tuition_id: UUID, data: meeting_link_models.MeetingLinkUpdate, current_user: db_models.Users) -> meeting_link_models.MeetingLinkRead:
        """
        Updates an existing meeting link for a tuition.
        Restricted to the Teacher who owns the tuition.
        """
        log.info(f"User {current_user.id} attempting to update meeting link for tuition {tuition_id}.")
        try:
            # 1. Fetch parent tuition
            tuition = await self._get_tuition_by_id_internal(tuition_id)
            
            # 2. Authorize
            self._authorize_write_access(tuition, current_user)
            
            # 3. Check that link exists
            link_to_update = tuition.meeting_link
            if not link_to_update:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No meeting link found for this tuition to update.")
                
            # 4. Apply updates
            update_data = data.model_dump(exclude_unset=True)
            if not update_data:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update.")
            
            # 5. Apply updates manually, converting enums/HttpUrl
            for key, value in update_data.items():
                if value is None:
                    setattr(link_to_update, key, None)
                elif key == 'meeting_link_type':
                    setattr(link_to_update, key, value.value) # Use .value
                elif key == 'meeting_link':
                    setattr(link_to_update, key, str(value)) # Cast HttpUrl to str
                else:
                    setattr(link_to_update, key, value)
                
            self.db.add(link_to_update)
            await self.db.flush()
            
            # 5. Format and return
            return meeting_link_models.MeetingLinkRead.model_validate(link_to_update)            
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Error in update_meeting_link_for_api for tuition {tuition_id}: {e}", exc_info=True)
            raise

    async def delete_meeting_link(self, tuition_id: UUID, current_user: db_models.Users) -> bool:
        """
        Deletes a meeting link from a tuition.
        Restricted to the Teacher who owns the tuition.
        """
        log.info(f"User {current_user.id} attempting to delete meeting link for tuition {tuition_id}.")
        try:
            # 1. Fetch parent tuition
            tuition = await self._get_tuition_by_id_internal(tuition_id)
            
            # 2. Authorize
            self._authorize_write_access(tuition, current_user)
            
            # 3. Check that link exists
            if not tuition.meeting_link:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No meeting link found for this tuition to delete.")
            
            # 4. Set relationship to None. The ORM's "delete-orphan" cascade will handle the deletion.
            tuition.meeting_link = None
            await self.db.flush()
            
            # 5. Return (will be a 204 No Content in the API)
            #TODO: implement an actual check here.
            return True

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Error in delete_meeting_link for tuition {tuition_id}: {e}", exc_info=True)
            raise

    # --- 6. Internal Formatters ---

    def _format_tuition_for_api(self, tuition_orm: db_models.Tuitions, current_user: db_models.Users) -> tuition_models.TuitionReadRoleBased:
        """
        Dispatcher that formats a single ORM object into the correct
        Pydantic API model based on the viewer's role.
        """
        if current_user.role == UserRole.TEACHER.value:
            return self._format_for_teacher_api(tuition_orm)
        elif current_user.role == UserRole.PARENT.value:
            return self._format_for_parent_api(tuition_orm, current_user.id)
        elif current_user.role == UserRole.STUDENT.value:
            return self._format_for_student_api(tuition_orm, current_user.id)
        else:
            # This case should be impossible if get_all_tuitions_for_api is used
            raise HTTPException(status_code=403, detail="Unauthorized role.")

    def _format_for_teacher_api(self, tuition_orm: db_models.Tuitions) -> tuition_models.TuitionReadForTeacher:
        """Formats a tuition for a Teacher's view."""
        
        # Manually build the detailed charge list
        charges_list = [
            tuition_models.TuitionChargeDetailRead(
                cost=c.cost,
                student=user_models.UserRead.model_validate(c.student),
                parent=user_models.ParentRead.model_validate(c.parent)
            ) for c in tuition_orm.tuition_template_charges
        ]
        
        api_model = tuition_models.TuitionReadForTeacher(
            id=tuition_orm.id,
            subject=tuition_orm.subject,
            educational_system=tuition_orm.educational_system,
            lesson_index=tuition_orm.lesson_index,
            min_duration_minutes=tuition_orm.min_duration_minutes,
            max_duration_minutes=tuition_orm.max_duration_minutes,
            meeting_link=tuition_orm.meeting_link, # Pydantic will auto-validate
            charges=charges_list
        )
        return api_model
        
    def _format_for_parent_api(self, tuition_orm: db_models.Tuitions, parent_id: UUID) -> tuition_models.TuitionReadForParent:
        """Formats a tuition for a Parent's view."""
        
        # Find the specific charge for this parent
        parent_charge = Decimal("0.00")
        for charge in tuition_orm.tuition_template_charges:
            if charge.parent_id == parent_id:
                parent_charge = charge.cost
                break

        attendee_names = [
            f"{c.student.first_name or ''} {c.student.last_name or ''}".strip() or "Unknown"
            for c in tuition_orm.tuition_template_charges
        ]
        
        api_model = tuition_models.TuitionReadForParent(
            id=tuition_orm.id,
            subject=tuition_orm.subject,
            educational_system=tuition_orm.educational_system,
            lesson_index=tuition_orm.lesson_index,
            min_duration_minutes=tuition_orm.min_duration_minutes,
            max_duration_minutes=tuition_orm.max_duration_minutes,
            meeting_link=tuition_orm.meeting_link,
            charge=parent_charge,
            attendee_names=attendee_names
        )
        return api_model

    def _format_for_student_api(self, tuition_orm: db_models.Tuitions, student_id: UUID) -> tuition_models.TuitionReadForStudent:
        """Formats a tuition for a Student's view."""
        
        attendee_names = [
            f"{c.student.first_name or ''} {c.student.last_name or ''}".strip() or "Unknown"
            for c in tuition_orm.tuition_template_charges
        ]
        
        api_model = tuition_models.TuitionReadForStudent(
            id=tuition_orm.id,
            subject=tuition_orm.subject,
            educational_system=tuition_orm.educational_system,
            lesson_index=tuition_orm.lesson_index,
            min_duration_minutes=tuition_orm.min_duration_minutes,
            max_duration_minutes=tuition_orm.max_duration_minutes,
            meeting_link=tuition_orm.meeting_link,
            attendee_names=attendee_names
        )
        return api_model

    # --- 7. Regeneration Logic ---

    async def regenerate_all_tuitions(self) -> bool:
        """
        REFACTORED: Regenerates all tuition templates based on the new
        `StudentSubjects` and `student_subject_sharings` tables,
        and preserves associated meeting links and costs.
        """
        log.info("Starting regeneration of all tuitions...")
        
        try:
            # 1. Preserve old data in memory before deletion.
            old_links_stmt = select(db_models.MeetingLinks)
            old_links_result = await self.db.execute(old_links_stmt)
            old_links = old_links_result.scalars().all()
            old_links_dict = {link.tuition_id: link for link in old_links}
            log.info(f"Preserved {len(old_links_dict)} existing meeting links.")
            for link in old_links:
                self.db.expunge(link)

            old_charges_stmt = select(db_models.TuitionTemplateCharges)
            old_charges_result = await self.db.execute(old_charges_stmt)
            old_charges = old_charges_result.scalars().all()
            old_charges_dict = {
                (charge.tuition_id, charge.student_id): charge.cost 
                for charge in old_charges
            }
            log.info(f"Preserved {len(old_charges_dict)} existing tuition charges.")
            for charge in old_charges:
                self.db.expunge(charge)

            # 2. Fetch all student subject enrollments with necessary related data.
            stmt = select(db_models.StudentSubjects).options(
                selectinload(db_models.StudentSubjects.student).selectinload(db_models.Students.parent),
                selectinload(db_models.StudentSubjects.teacher),
                selectinload(db_models.StudentSubjects.shared_with_student).selectinload(db_models.Students.parent) # Critical for grouping
            )
            all_student_subjects = list((await self.db.execute(stmt)).scalars().all())
            
            if not all_student_subjects:
                log.warning("No student subjects found. Truncating tuitions and finishing.")
                await self.db.execute(delete(db_models.Tuitions))
                return True

            # 3. Group students and generate new ORM objects
            new_tuitions = []
            new_charges = []
            new_meeting_links = []
            # Use a set to track students already assigned to a group for a specific subject/teacher/system
            # to avoid creating duplicate tuitions. Key: (student_id, subject, teacher_id, educational_system)
            processed_students = set()

            for ss in all_student_subjects:
                process_key = (ss.student_id, ss.subject, ss.teacher_id, ss.educational_system)
                if process_key in processed_students:
                    continue # This student has already been added to a group for this subject/teacher/system

                # This is a new group. The group consists of the main student
                # plus all students they share this subject with.
                group_students = [ss.student] + ss.shared_with_student
                
                # The teacher, subject and educational_system are the same for the whole group
                teacher_id = ss.teacher_id
                subject_name = ss.subject
                educational_system = ss.educational_system

                # Calculate the max of min/max durations for the whole group
                min_duration_for_group = max(s.min_duration_mins for s in group_students)
                max_duration_for_group = max(s.max_duration_mins for s in group_students)

                student_ids_in_group = sorted([s.id for s in group_students])

                # Loop from 1 to lessons_per_week
                for lesson_index in range(1, ss.lessons_per_week + 1):
                    # Generate the deterministic ID based on all students in the group
                    tuition_id = self._generate_deterministic_id(
                        subject=subject_name,
                        educational_system=educational_system,
                        lesson_index=lesson_index, # Use the loop variable
                        teacher_id=teacher_id,
                        student_ids=student_ids_in_group
                    )

                    # Create the new Tuition object
                    new_tuition = db_models.Tuitions(
                        id=tuition_id,
                        teacher_id=teacher_id,
                        subject=subject_name,
                        educational_system=educational_system,
                        lesson_index=lesson_index, # Use the loop variable
                        min_duration_minutes=min_duration_for_group, # Use calculated value
                        max_duration_minutes=max_duration_for_group, # Use calculated value
                    )
                    new_tuitions.append(new_tuition)

                    # Create charges for every student in the group
                    for student_in_group in group_students:
                        # Use preserved cost if available, otherwise fall back to student's current cost
                        preserved_cost = old_charges_dict.get((tuition_id, student_in_group.id))
                        cost_to_use = preserved_cost if preserved_cost is not None else student_in_group.cost

                        new_charges.append(db_models.TuitionTemplateCharges(
                            tuition_id=tuition_id,
                            student_id=student_in_group.id,
                            parent_id=student_in_group.parent_id,
                            cost=cost_to_use
                        ))

                    # Check if a link existed for this deterministic ID and restore it
                    if tuition_id in old_links_dict:
                        old_link = old_links_dict[tuition_id]
                        new_meeting_links.append(db_models.MeetingLinks(
                            tuition_id=tuition_id, # Link to the new tuition
                            meeting_link_type=old_link.meeting_link_type,
                            meeting_link=old_link.meeting_link,
                            meeting_id=old_link.meeting_id,
                            meeting_password=old_link.meeting_password
                        ))

                # Mark all students in this group as processed for this subject/teacher combo
                # This happens *after* the lesson_index loop
                for student_in_group in group_students:
                    processed_students.add((student_in_group.id, subject_name, teacher_id, educational_system))

            log.info(f"Generated {len(new_tuitions)} tuitions, {len(new_charges)} charges, and restored {len(new_meeting_links)} links.")

            # 4. Perform the database transaction: wipe and recreate
            await self.db.execute(delete(db_models.Tuitions))
            
            self.db.add_all(new_tuitions)
            self.db.add_all(new_charges)
            self.db.add_all(new_meeting_links)
            
            await self.db.flush()
            log.info("Successfully regenerated all tuitions.")
            return True

        except Exception as e:
            log.error(f"A critical error occurred during tuition regeneration: {e}", exc_info=True)
            raise

    def _generate_deterministic_id(self, subject: str, educational_system: str, lesson_index: int, teacher_id: UUID, student_ids: list[UUID]) -> UUID:
        """
        Creates a stable, deterministic UUID for a tuition based on its core properties.
        """
        id_string = f"{subject}:{educational_system}:{lesson_index}:{teacher_id}:{','.join(map(str, sorted(student_ids)))}"
        hasher = hashlib.sha256(id_string.encode('utf-8'))
        return UUID(bytes=hasher.digest()[:16])
