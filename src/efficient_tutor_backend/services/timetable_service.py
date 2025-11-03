'''

'''
from typing import List, Annotated, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass

from ..database.engine import get_db_session
from ..database import models as db_models
from ..database.db_enums import UserRole, RunStatusEnum
from ..models import timetable as timetable_models
from ..models import tuition as tuition_models
from ..models import user as user_models
from ..common.logger import log
from .tuition_service import TuitionService

# --- Internal Data Structure ---
@dataclass
class ScheduledTuition:
    """An internal dataclass representing a scheduled tuition."""
    tuition: db_models.Tuitions
    start_time: datetime
    end_time: datetime

# --- Service Class ---

class TimeTableService:
    """
    Service for viewing the generated timetable.
    It fetches the latest valid timetable run and filters it based on the user.
    """
    def __init__(
        self, 
        db: Annotated[AsyncSession, Depends(get_db_session)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)]
    ):
        self.db = db
        self.tuition_service = tuition_service

    async def get_all(self, current_user: db_models.Users) -> List[ScheduledTuition]:
        """
        RENAMED: Fetches the latest successful timetable and returns a list of
        scheduled tuitions relevant to the specific viewer.
        """
        log.info(f"Fetching latest scheduled tuitions for user {current_user.id}")
        
        # 1. Fetch only the tuition objects relevant to the viewer.
        user_tuitions = await self.tuition_service.get_all_tuitions(current_user)
        if not user_tuitions:
            log.warning(f"No tuitions exist for user {current_user.id}. Cannot show timetable.")
            return []
        
        user_tuitions_dict = {t.id: t for t in user_tuitions}

        # 2. Get the raw solution data from the latest timetable run
        solution_data = await self._get_latest_solution_data()
        if not solution_data:
            return []

        scheduled_tuitions = []
        try:
            # 3. Filter and hydrate events against the user's tuitions
            for event in solution_data:
                if event.get('category') == 'Tuition' and 'id' in event:
                    tuition_id = UUID(event['id'])
                    tuition_obj = user_tuitions_dict.get(tuition_id)

                    if tuition_obj: # This check now also filters for the user
                        scheduled_tuitions.append(
                            ScheduledTuition(
                                tuition=tuition_obj,
                                start_time=event['start_time'],
                                end_time=event['end_time']
                            )
                        )
            
            log.info(f"Successfully constructed {len(scheduled_tuitions)} scheduled tuition events for user {current_user.id}.")
            return scheduled_tuitions
        
        except (TypeError, KeyError, ValueError) as e:
            log.error(f"Failed to parse timetable solution_data: {e}", exc_info=True)
            raise ValueError(f"Failed to parse timetable solution data.")

    async def get_all_for_api(self, current_user: db_models.Users) -> List:
        """
        REFACTORED: Public dispatcher that returns a lean list of scheduled
        tuitions formatted correctly for the viewer's role.
        """
        # 1. Get the rich, filtered ScheduledTuition dataclass objects
        rich_scheduled_tuitions = await self.get_all(current_user)
        
        # 2. Dispatch to the correct formatter based on the user's role
        if current_user.role == UserRole.TEACHER.value:
            return [self._format_for_teacher_api(st) for st in rich_scheduled_tuitions]
        elif current_user.role == UserRole.PARENT.value:
            return [self._format_for_parent_api(st, current_user) for st in rich_scheduled_tuitions]
        elif current_user.role == UserRole.STUDENT.value:
            return [self._format_for_student_api(st) for st in rich_scheduled_tuitions]
        else:
            return [] # Or raise 403 Forbidden

    # --- Private Formatters (Fix the ValidationError) ---

    def _get_common_names_and_link(self, tuition_data: db_models.Tuitions) -> (list[str], Optional[str]):
        """Helper to extract attendee names and the meeting link string."""
        # Extract meeting_link string correctly
        meeting_link_str = None
        if tuition_data.meeting_link and isinstance(tuition_data.meeting_link, dict):
            meeting_link_str = tuition_data.meeting_link.get('meeting_link')
            
        # Get all attendee names for context
        attendee_names = [
            f"{c.student.first_name or ''} {c.student.last_name or ''}".strip() or "Unknown"
            for c in tuition_data.tuition_template_charges
        ]
        return attendee_names, meeting_link_str

    def _format_for_teacher_api(self, scheduled_tuition: ScheduledTuition) -> timetable_models.ScheduledTuitionReadForTeacher:
        """
        Manually formats a single scheduled tuition for a TEACHER's view.
        This fixes the ValidationError.
        """
        tuition_data = scheduled_tuition.tuition
        attendee_names, meeting_link_str = self._get_common_names_and_link(tuition_data)

        # Manually create the detailed charge list for the teacher
        charges_list = [
            tuition_models.TuitionChargeDetailRead(
                cost=c.cost,
                student=user_models.UserRead.model_validate(c.student),
                parent=user_models.ParentRead.model_validate(c.parent)
            ) for c in tuition_data.tuition_template_charges
        ]

        # 1. Create the inner Pydantic model
        teacher_tuition_model = tuition_models.TuitionReadForTeacher(
            id=tuition_data.id,
            subject=tuition_data.subject,
            lesson_index=tuition_data.lesson_index,
            min_duration_minutes=tuition_data.min_duration_minutes,
            max_duration_minutes=tuition_data.max_duration_minutes,
            meeting_link=meeting_link_str,
            charges=charges_list
        )

        # 2. Create the outer (timetable) Pydantic model
        return timetable_models.ScheduledTuitionReadForTeacher(
            start_time=scheduled_tuition.start_time,
            end_time=scheduled_tuition.end_time,
            tuition=teacher_tuition_model
        )

    def _format_for_parent_api(self, scheduled_tuition: ScheduledTuition, current_user: db_models.Users) -> timetable_models.ScheduledTuitionReadForParent:
        """Manually formats a single scheduled tuition for a PARENT's view."""
        tuition_data = scheduled_tuition.tuition
        attendee_names, meeting_link_str = self._get_common_names_and_link(tuition_data)

        # Find the specific charge for this parent
        parent_charge = Decimal("0.00")
        for charge_orm in tuition_data.tuition_template_charges:
            if charge_orm.parent_id == current_user.id:
                parent_charge = charge_orm.cost
                break

        # 1. Create the inner Pydantic model
        parent_tuition_model = tuition_models.TuitionReadForParent(
            id=tuition_data.id,
            subject=tuition_data.subject,
            lesson_index=tuition_data.lesson_index,
            min_duration_minutes=tuition_data.min_duration_minutes,
            max_duration_minutes=tuition_data.max_duration_minutes,
            meeting_link=meeting_link_str,
            charge=parent_charge,
            attendee_names=attendee_names
        )

        # 2. Create the outer (timetable) Pydantic model
        return timetable_models.ScheduledTuitionReadForParent(
            start_time=scheduled_tuition.start_time,
            end_time=scheduled_tuition.end_time,
            tuition=parent_tuition_model
        )

    def _format_for_student_api(self, scheduled_tuition: ScheduledTuition) -> timetable_models.ScheduledTuitionReadForStudent:
        """Manually formats a single scheduled tuition for a STUDENT's view."""
        tuition_data = scheduled_tuition.tuition
        attendee_names, meeting_link_str = self._get_common_names_and_link(tuition_data)

        # 1. Create the inner Pydantic model
        student_tuition_model = tuition_models.TuitionReadForStudent(
            id=tuition_data.id,
            subject=tuition_data.subject,
            lesson_index=tuition_data.lesson_index,
            min_duration_minutes=tuition_data.min_duration_minutes,
            max_duration_minutes=tuition_data.max_duration_minutes,
            meeting_link=meeting_link_str,
            attendee_names=attendee_names
        )

        # 2. Create the outer (timetable) Pydantic model
        return timetable_models.ScheduledTuitionReadForStudent(
            start_time=scheduled_tuition.start_time,
            end_time=scheduled_tuition.end_time,
            tuition=student_tuition_model
        )

    async def _get_latest_solution_data(self) -> Optional[List[dict]]:
        """Fetches the 'solution_data' JSONB from the latest successful/manual run."""
        log.info("Fetching latest timetable solution from database...")
        try:
            stmt = select(db_models.TimetableRuns.solution_data).filter(
                db_models.TimetableRuns.status.in_([
                    RunStatusEnum.SUCCESS.value, 
                    RunStatusEnum.MANUAL.value
                ])
            ).order_by(db_models.TimetableRuns.id.desc()).limit(1)
            
            result = await self.db.execute(stmt)
            solution_data = result.scalars().first()
            
            if not solution_data:
                log.warning("No successful or manual timetable run found.")
                return None
            return solution_data
        except Exception as e:
            log.error(f"Database error fetching latest timetable: {e}", exc_info=True)
            raise
