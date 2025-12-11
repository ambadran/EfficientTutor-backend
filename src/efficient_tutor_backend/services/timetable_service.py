'''
Timetable Service
'''
from typing import Annotated, Optional
from uuid import UUID
from datetime import datetime, time, timedelta, date
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database.engine import get_db_session
from ..database import models as db_models
from ..database.db_enums import UserRole, RunStatusEnum
from ..models import timetable as timetable_models
from ..common.logger import log
from .user_service import UserService


class TimeTableService:
    """
    Service for viewing the generated timetable solution.
    Fetches the latest valid timetable run and filters it based on the user's role and permissions.
    """
    def __init__(
        self, 
        db: Annotated[AsyncSession, Depends(get_db_session)],
        user_service: Annotated[UserService, Depends(UserService)]
    ):
        self.db = db
        self.user_service = user_service

    # --- Authorization Helper ---

    async def _authorize_view_access(self, current_user: db_models.Users, target_user_id: UUID) -> db_models.Users:
        """
        Validates if the current_user is allowed to view the timetable of target_user_id.
        Returns the target_user object if authorized.
        """
        # 1. Self-View: Always allowed
        if current_user.id == target_user_id:
            return current_user

        # Fetch target user to check role/relationships
        target_user = await self.user_service.get_user_by_id(target_user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

        # 2. Role-Based Rules
        if current_user.role == UserRole.TEACHER.value:
            # Teacher can view any STUDENT's timetable
            if target_user.role == UserRole.STUDENT.value:
                return target_user
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="Teachers can only view timetables for students."
                )

        elif current_user.role == UserRole.PARENT.value:
            # Parent can ONLY view their OWN students
            # Ensure 'students' relationship is loaded on current_user
            if not isinstance(current_user, db_models.Parents):
                 # Force reload as Parent if needed, though get_user_by_id typically handles polymorphism
                 # but for safety let's assume 'students' attribute exists or check via ID
                 pass
            
            # Using the relationship loaded by UserService
            # (UserService.get_user_by_id eager loads students for Parents)
            my_student_ids = [s.id for s in getattr(current_user, 'students', [])]
            
            if target_user_id in my_student_ids:
                return target_user
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="Parents can only view timetables for their own children."
                )
        
        elif current_user.role == UserRole.STUDENT.value:
            # Students can only view themselves (handled by Self-View check above)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Students cannot view other users' timetables."
            )
        
        # Admin or others?
        if current_user.role == UserRole.ADMIN.value:
             # Admins can view anyone theoretically, but let's restrict to Student/Teacher for now
             # based on requirements "Teachers can view Student", "Parent can view Student".
             # Assuming Admin can view all for debugging.
             return target_user

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    # --- Date/Time Helper ---

    def _calculate_next_occurrence(
        self, 
        day_of_week: int, 
        start_time: time, 
        end_time: time, 
        user_timezone: str
    ) -> tuple[datetime, datetime]:
        """
        Calculates the next occurrence of a slot relative to the user's timezone.
        db.day_of_week: 1 (Mon) to 7 (Sun).
        Python weekday: 0 (Mon) to 6 (Sun).
        """
        try:
            tz = ZoneInfo(user_timezone)
        except Exception:
            log.warning(f"Invalid timezone '{user_timezone}', defaulting to UTC.")
            tz = ZoneInfo("UTC")

        now = datetime.now(tz)
        today_idx = now.weekday() # 0=Mon, 6=Sun
        
        # Convert DB (1-7) to Python (0-6)
        target_idx = day_of_week - 1
        
        # Calculate days ahead
        days_ahead = (target_idx - today_idx + 7) % 7
        
        # If it's today, we need to check if the time has passed. 
        # For simplicity in a timetable view, we usually just show "This Week's" occurrence.
        # If today is Monday and the slot is Monday 8am, and it's currently Monday 9am,
        # usually we still show today's date (as it is the current week's slot), 
        # or we could show next week's.
        # Let's stick to "Upcoming or Today" logic:
        # If days_ahead is 0 (today) and end_time < now.time(), maybe move to next week?
        # A static timetable view usually wants the *current week's* instance representation.
        # Let's just find the date for the "current/next" day_of_week instance.
        
        target_date = now.date() + timedelta(days=days_ahead)
        
        # Construct timezone-aware datetimes
        start_dt = datetime.combine(target_date, start_time).replace(tzinfo=tz)
        end_dt = datetime.combine(target_date, end_time).replace(tzinfo=tz)
        
        # Handle overnight slots (end_time < start_time)
        if end_time <= start_time:
            end_dt += timedelta(days=1)
            
        return start_dt, end_dt

    def _get_day_name(self, day_of_week: int) -> str:
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if 1 <= day_of_week <= 7:
            return days[day_of_week - 1]
        raise ValueError("day_of_week must be between 1 and 7")

    # --- Main API Method ---

    async def get_timetable_for_api(
        self, 
        current_user: db_models.Users, 
        target_user_id: Optional[UUID] = None
    ) -> list[timetable_models.TimeTableSlot]:
        """
        Fetches the latest timetable solution for the target user (or self).
        Applies masking based on the relationship between current_user and target_user.
        """
        # 1. Determine Target and Authorize
        actual_target_id = target_user_id if target_user_id else current_user.id
        target_user = await self._authorize_view_access(current_user, actual_target_id)
        
        log.info(f"User {current_user.id} fetching timetable for {target_user.id} (Role: {target_user.role})")

        # 2. Fetch Latest Successful Run
        run_stmt = select(db_models.TimetableRuns.id).filter(
            db_models.TimetableRuns.status.in_([
                RunStatusEnum.SUCCESS.value, 
                RunStatusEnum.MANUAL.value
            ])
        ).order_by(db_models.TimetableRuns.id.desc()).limit(1)
        
        run_result = await self.db.execute(run_stmt)
        run_id = run_result.scalar()
        
        if not run_id:
            log.warning("No successful timetable runs found.")
            return []

        # 3. Fetch User Solution & Slots
        solution_stmt = select(db_models.TimetableRunUserSolutions).options(
            selectinload(db_models.TimetableRunUserSolutions.timetable_solution_slots)
        ).filter(
            db_models.TimetableRunUserSolutions.timetable_run_id == run_id,
            db_models.TimetableRunUserSolutions.user_id == target_user.id
        )
        
        sol_result = await self.db.execute(solution_stmt)
        user_solution = sol_result.scalars().first()
        
        if not user_solution:
            log.info(f"No timetable solution found for user {target_user.id} in run {run_id}.")
            return []

        # 4. Process Slots
        api_slots = []
        
        # Determine if we are in "Parent Proxy" mode
        # (Viewer is Parent, Target is Child -> Parent sees everything Child sees)
        is_parent_proxy = (
            current_user.role == UserRole.PARENT.value and 
            target_user.role == UserRole.STUDENT.value and 
            target_user.parent_id == current_user.id # Assuming relationship validation passed in authorize
        )

        for slot_orm in user_solution.timetable_solution_slots:
            
            # --- VISIBILITY CHECK ---
            is_visible = False
            
            # Scenario A: Viewer is a direct participant
            if current_user.id in slot_orm.participant_ids:
                is_visible = True
            
            # Scenario B: Parent Proxy (Viewer is Parent of the Student who is a participant)
            # Since this is the *Student's* solution, the Student IS a participant in their own slots.
            # So checking if target_user.id is in participant_ids is redundant but safe.
            elif is_parent_proxy:
                 is_visible = True
            
            # Scenario C: Self View
            elif current_user.id == target_user.id:
                is_visible = True

            # --- MASKING LOGIC ---
            if is_visible:
                slot_name = slot_orm.name
                
                # Determine Type
                if slot_orm.tuition_id:
                    s_type = timetable_models.TimeTableSlotType.TUITION
                    obj_uuid = slot_orm.tuition_id
                elif slot_orm.availability_interval_id:
                    s_type = timetable_models.TimeTableSlotType.AVAILABILITY
                    obj_uuid = slot_orm.availability_interval_id
                else:
                    s_type = timetable_models.TimeTableSlotType.OTHER
                    obj_uuid = None
            else:
                # MASKED
                slot_name = "Others"
                s_type = timetable_models.TimeTableSlotType.OTHER
                obj_uuid = None

            # --- DATE CALCULATION ---
            # Use the viewer's timezone for display
            start_dt, end_dt = self._calculate_next_occurrence(
                day_of_week=slot_orm.day_of_week,
                start_time=slot_orm.start_time,
                end_time=slot_orm.end_time,
                user_timezone=current_user.timezone
            )

            api_slots.append(timetable_models.TimeTableSlot(
                id=slot_orm.id,
                name=slot_name,
                slot_type=s_type,
                day_of_week=slot_orm.day_of_week,
                day_name=self._get_day_name(slot_orm.day_of_week),
                start_time=slot_orm.start_time,
                end_time=slot_orm.end_time,
                object_uuid=obj_uuid,
                next_occurrence_start=start_dt,
                next_occurrence_end=end_dt
            ))

        # Sort by day and time for convenience
        api_slots.sort(key=lambda x: (x.day_of_week, x.start_time))
        
        return api_slots
