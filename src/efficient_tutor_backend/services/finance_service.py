'''

'''
from typing import Optional, Annotated, Dict, Any
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from pydantic import ValidationError
from fastapi import Depends, HTTPException, status
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database.engine import get_db_session
from ..database import models as db_models
from ..database.db_enums import UserRole, LogStatusEnum, TuitionLogCreateTypeEnum, PaidStatus
from ..models import finance as finance_models
from ..common.logger import log
from ..common.config import settings
from .user_service import UserService
from .tuition_service import TuitionService

# --- Service 1: Tuition Log Management ---

class TuitionLogService:
    """
    Service for creating, reading, and managing tuition logs.
    Authorization is now handled in all API-facing methods.
    """
    
    def __init__(
        self, 
        db: Annotated[AsyncSession, Depends(get_db_session)],
        user_service: Annotated[UserService, Depends(UserService)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)]
    ):
        self.db = db
        self.user_service = user_service
        self.tuition_service = tuition_service

    # --- 1. Authorization Helpers ---

    def _authorize_role(self, current_user: db_models.Users, allowed_roles: list[UserRole]):
        """Helper to check general role permissions."""
        allowed_role_values = [role.value for role in allowed_roles]
        if current_user.role not in allowed_role_values:
            log.warning(f"Unauthorized action by user {current_user.id} (Role: {current_user.role}). Required one of: {allowed_role_values}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action."
            )

    async def _authorize_related_id(self, current_user: db_models.Users, log_obj: db_models.TuitionLogs):
        """
        Checks if the passed user is related to the log
        (is the Teacher, the Student, or the Student's Parent).
        """
        # 1. Check if Teacher is the owner
        if current_user.role == UserRole.TEACHER.value:
            if log_obj.teacher_id == current_user.id:
                return  # Allow

        # 2. Check if Student is in the charges
        elif current_user.role == UserRole.STUDENT.value:
            if any(charge.student_id == current_user.id for charge in log_obj.tuition_log_charges):
                return  # Allow
        
        # 3. Check if Parent is the parent of a student in the charges
        elif current_user.role == UserRole.PARENT.value:
            await self.db.refresh(current_user, ['students'])
            my_student_ids = {student.id for student in current_user.students}
            if any(charge.student_id in my_student_ids for charge in log_obj.tuition_log_charges):
                return  # Allow

        # 4. If none of the above passed, deny access
        log.warning(f"SECURITY: User {current_user.id} tried to access unrelated tuition log {log_obj.id}.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this log."
        )

    # --- 2. Internal Data-Fetching (No Auth) ---

    async def _get_log_by_id_internal(self, log_id: UUID) -> db_models.TuitionLogs:
        """
        RENAMED: Internal "dumb" fetcher.
        Fetches a single, fully-loaded tuition log by its ID.
        """
        log.info(f"Internal fetch for tuition log by ID: {log_id}")
        try:
            stmt = select(db_models.TuitionLogs).options(
                selectinload(db_models.TuitionLogs.teacher),
                selectinload(db_models.TuitionLogs.tuition),
                selectinload(db_models.TuitionLogs.tuition_log_charges).options(
selectinload(db_models.TuitionLogCharges.student),
                    selectinload(db_models.TuitionLogCharges.parent)
                )
            ).filter(db_models.TuitionLogs.id == log_id)
            
            result = await self.db.execute(stmt)
            log_obj = result.scalars().first()
            if not log_obj:
                log.warning(f"Tried to fetch non-existent log id: {log_id}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tuition log not found.")
            return log_obj
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Database error in _get_log_by_id_internal for {log_id}: {e}", exc_info=True)
            raise

    async def get_all_tuition_logs_orm(self, current_user: db_models.Users, include_void: bool = False) -> list[db_models.TuitionLogs]:
        """
        RENAMED: Internal "dumb" fetcher.
        Fetches all tuition logs relevant to the current user, fully loaded.
        This method is "dumb" and only filters data; it does not raise auth errors.
        """
        log.info(f"Internal ORM fetch for all tuition logs for user {current_user.id}")
        
        # Base query with all relationships eager-loaded
        stmt = select(db_models.TuitionLogs).options(
            selectinload(db_models.TuitionLogs.teacher),
            selectinload(db_models.TuitionLogs.tuition),
            selectinload(db_models.TuitionLogs.tuition_log_charges).options(
selectinload(db_models.TuitionLogCharges.student),
                selectinload(db_models.TuitionLogCharges.parent)
            )
        )
        
        # Add role-based filtering
        if current_user.role == UserRole.TEACHER.value:
            stmt = stmt.filter(db_models.TuitionLogs.teacher_id == current_user.id)
        elif current_user.role == UserRole.PARENT.value:
            await self.db.refresh(current_user, ['students'])
            student_ids = {s.id for s in current_user.students}
            if not student_ids:
                return []
            subquery = select(db_models.TuitionLogCharges.tuition_log_id).distinct().filter(
                db_models.TuitionLogCharges.student_id.in_(student_ids)
            )
            stmt = stmt.filter(db_models.TuitionLogs.id.in_(subquery))
        elif current_user.role == UserRole.STUDENT.value:
            subquery = select(db_models.TuitionLogCharges.tuition_log_id).distinct().filter(
                db_models.TuitionLogCharges.student_id == current_user.id
            )
            stmt = stmt.filter(db_models.TuitionLogs.id.in_(subquery))
        else:
            return [] # Other roles see no logs

        # Only filter out void logs for Parent users
        if current_user.role == UserRole.PARENT.value:
            stmt = stmt.filter(db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value)
            
        stmt = stmt.order_by(db_models.TuitionLogs.start_time.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # --- 3. API-Facing Read Methods (With Auth) ---
    
    async def get_tuition_log_by_id_for_api(self, log_id: UUID, current_user: db_models.Users) -> finance_models.TuitionLogReadRoleBased:
        """
        API-facing method to get a single log.
        1. Authorizes Role
        2. Fetches Data
        3. Authorizes Object-Level Access
        4. Formats
        """
        log.info(f"User {current_user.id} requesting tuition log {log_id} for API.")
        try:
            # 1. Authorize Role (Teacher, Parent, Student can read)
            self._authorize_role(current_user, [UserRole.TEACHER, UserRole.PARENT])
            
            # 2. Fetch
            log_obj = await self._get_log_by_id_internal(log_id)
            
            # 3. Authorize Object-Level Access
            await self._authorize_related_id(current_user, log_obj)
            
            # 4. Format and Return
            earliest_date = await self._get_earliest_log_date()
            if current_user.role == UserRole.TEACHER.value:
                # This check is just for mypy, auth helper already confirmed
                parent_id = log_obj.tuition_log_charges[0].parent_id
                statuses = await self._get_paid_statuses_for_parents([parent_id])
                return self._build_teacher_api_log(log_obj, earliest_date, statuses.get(parent_id, PaidStatus.UNPAID))
            elif current_user.role == UserRole.PARENT.value:
                statuses = await self._get_paid_statuses_for_parents([current_user.id])
                return self._build_parent_api_log(log_obj, earliest_date, statuses.get(current_user.id, PaidStatus.UNPAID), current_user.id)
            else: # Student
                return self._build_student_api_log(log_obj, earliest_date, current_user.id)

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Error in get_tuition_log_by_id_for_api: {e}", exc_info=True)
            raise

    async def get_all_tuition_logs_for_api(self, current_user: db_models.Users) -> list[finance_models.TuitionLogReadRoleBased]:
        """
        REFACTORED: API-facing method.
        1. Authorizes Role
        2. Fetches Data
        3. Formats
        """
        log.info(f"User {current_user.id} (Role: {current_user.role}) requesting all tuition logs for API.")
        try:
            # 1. Authorize Role (Teacher, Parent, Student can read)
            self._authorize_role(current_user, [UserRole.TEACHER, UserRole.PARENT])
            
            # 2. Fetch Data (uses the dumb, internal fetcher)
            rich_logs = await self.get_all_tuition_logs_orm(current_user)
            if not rich_logs:
                return []
                
            earliest_date = await self._get_earliest_log_date()
            
            # 3. Get paid statuses
            if current_user.role == UserRole.TEACHER.value:
                parent_ids = {charge.parent_id for log in rich_logs for charge in log.tuition_log_charges}
                paid_statuses = await self._get_paid_statuses_for_parents(list(parent_ids))
            else: # Parent or Student
                parent_id = current_user.id if current_user.role == UserRole.PARENT.value else current_user.parent_id
                paid_statuses = await self._get_paid_statuses_for_parents([parent_id])

            # 4. Format based on role
            api_logs = []
            if current_user.role == UserRole.TEACHER.value:
                for rich_log in rich_logs:
                    parent_id = rich_log.tuition_log_charges[0].parent_id
                    status = paid_statuses.get(parent_id, PaidStatus.UNPAID)
                    api_logs.append(self._build_teacher_api_log(rich_log, earliest_date, status))
            
            elif current_user.role == UserRole.PARENT.value:
                for rich_log in rich_logs:
                    status = paid_statuses.get(current_user.id, PaidStatus.UNPAID)
                    api_logs.append(self._build_parent_api_log(rich_log, earliest_date, status, current_user.id))
            
            elif current_user.role == UserRole.STUDENT.value:
                for rich_log in rich_logs:
                    api_logs.append(self._build_student_api_log(rich_log, earliest_date, current_user.id))
            
            return api_logs
            
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Error in get_all_tuition_logs_for_api: {e}", exc_info=True)
            raise

    # --- 4. API-Facing Write Methods (With Auth) ---

    async def create_tuition_log(
        self, 
        log_data: dict, 
        current_user: db_models.Users,
        corrected_from_log_id: Optional[UUID] = None
    ) -> finance_models.TuitionLogReadForTeacher:
        """
        Creates a new tuition log. Restricted to Teachers only.
        Returns the final, JSON-serializable dictionary.
        """
        log.info(f"User {current_user.id} attempting to create tuition log.")
        
        # 1. Authorize Role: Must be a Teacher
        self._authorize_role(current_user, [UserRole.TEACHER])
        
        try:
            input_model = finance_models.TuitionLogCreateValidator.validate_python(log_data)
            
            new_log_object: Optional[db_models.TuitionLogs] = None

            if isinstance(input_model, finance_models.ScheduledLogInput):
                new_log_object = await self._create_from_scheduled(
                    input_model, current_user, corrected_from_log_id
                )
            elif isinstance(input_model, finance_models.CustomLogInput):
                new_log_object = await self._create_from_custom(
                    input_model, current_user, corrected_from_log_id
                )
        
            if not new_log_object:
                 raise Exception("Tuition log creation did not return a valid object.")

            # Format for API response
            earliest_date = await self._get_earliest_log_date()
            return self._build_teacher_api_log(
                log=new_log_object,
                earliest_date=earliest_date,
                paid_status=PaidStatus.UNPAID
            )

        except (ValidationError, ValueError) as e:
            log.error(f"Validation failed for creating tuition log. Data: {log_data}, Error: {e}")
            raise
        except HTTPException as http_exc:
            raise http_exc # Re-raise 404s/403s from helpers
        except Exception as e:
            log.error(f"Error in create_tuition_log: {e}", exc_info=True)
            raise

    async def _create_from_scheduled(
        self, 
        data: finance_models.ScheduledLogInput, 
        current_user: db_models.Users, 
        corrected_from_log_id: Optional[UUID]
    ) -> db_models.TuitionLogs:
        """
        Private helper to create a log from a scheduled tuition.
        Authorization (that user is a Teacher) is assumed to be done.
        """
        log.info(f"Creating SCHEDULED log from tuition ID {data.tuition_id} by user {current_user.id}")
        
        # 1. Fetch tuition
        tuition = await self.tuition_service._get_tuition_by_id_internal(data.tuition_id)
        
        # 2. Object-Level Auth: Verify ownership
        if tuition.teacher_id != current_user.id:
            log.warning(f"SECURITY: User {current_user.id} tried to log tuition {tuition.id} owned by {tuition.teacher_id}.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to log this tuition.")

        # ... (rest of the method is correct) ...
        charges_to_create = [
            {'student_id': c.student_id, 'parent_id': c.parent_id, 'cost': c.cost} 
            for c in tuition.tuition_template_charges
        ]
        new_log = db_models.TuitionLogs(
            teacher_id=current_user.id,
            subject=tuition.subject,
            educational_system=tuition.educational_system,
            grade=tuition.grade,
            start_time=data.start_time,
            end_time=data.end_time,
            create_type=TuitionLogCreateTypeEnum.SCHEDULED.value,
            tuition_id=tuition.id,
            lesson_index=tuition.lesson_index,
            corrected_from_log_id=corrected_from_log_id,
            status=LogStatusEnum.ACTIVE.value
        )
        self.db.add(new_log)
        new_charges = [
            db_models.TuitionLogCharges(tuition_log=new_log, **charge)
            for charge in charges_to_create
        ]
        self.db.add_all(new_charges)
        await self.db.flush()
        await self.db.refresh(new_log, ['teacher', 'tuition_log_charges', 'tuition'])
        for charge in new_log.tuition_log_charges:
            await self.db.refresh(charge, ['student'])
        return new_log

    async def _create_from_custom(
        self, 
        data: finance_models.CustomLogInput, 
        current_user: db_models.Users, 
        corrected_from_log_id: Optional[UUID]
    ) -> db_models.TuitionLogs:
        """
        Private helper to create a log from custom data.
        Authorization (that user is a Teacher) is assumed to be done.
        """
        log.info(f"Creating CUSTOM log for teacher {current_user.id}.")
        
        # 1. Fetch students
        student_ids = [charge.student_id for charge in data.charges]
        students_orm = await self.user_service.get_users_by_ids(student_ids)
        students_dict = {user.id: user for user in students_orm if user.role == UserRole.STUDENT.value}

        if len(students_dict) != len(student_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more students not found.")
            
        # 2. Create log
        new_log = db_models.TuitionLogs(
            teacher_id=current_user.id, # IDOR security
            subject=data.subject.value,
            educational_system=data.educational_system.value,
            grade=data.grade,
            start_time=data.start_time,
            end_time=data.end_time,
            create_type=TuitionLogCreateTypeEnum.CUSTOM.value,
            lesson_index=data.lesson_index,
            corrected_from_log_id=corrected_from_log_id,
            status=LogStatusEnum.ACTIVE.value
        )
        self.db.add(new_log)
        
        # ... (rest of the method is correct) ...
        new_charges = []
        for charge_input in data.charges:
            student = students_dict.get(charge_input.student_id)
            new_charges.append(db_models.TuitionLogCharges(
                tuition_log=new_log,
                student_id=student.id,
                parent_id=student.parent_id,
                cost=charge_input.cost
            ))
        self.db.add_all(new_charges)
        await self.db.flush()
        await self.db.refresh(new_log, ['teacher', 'tuition_log_charges'])
        for charge in new_log.tuition_log_charges:
            await self.db.refresh(charge, ['student'])
        return new_log

    async def correct_tuition_log(
        self, 
        old_log_id: UUID, 
        new_log_data: dict[str, Any], 
        current_user: db_models.Users
    ) -> finance_models.TuitionLogReadForTeacher:
        """
        Edits a tuition log by voiding the old one and creating a new one.
        Restricted to the Teacher owner.
        """
        log.info(f"User {current_user.id} attempting to correct tuition log {old_log_id}.")
        
        # 1. Authorize Role: Must be a Teacher
        self._authorize_role(current_user, [UserRole.TEACHER])
        
        # 2. Fetch the old log
        old_log = await self._get_log_by_id_internal(old_log_id)
        
        # 3. Authorize Object-Level Access: Must be the owner
        if old_log.teacher_id != current_user.id:
            log.warning(f"SECURITY: User {current_user.id} tried to edit log {old_log_id} owned by {old_log.teacher_id}.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to edit this log.")

        # 4. Void the old log
        if not await self.void_tuition_log(old_log_id, current_user, skip_auth=True):
            raise Exception(f"Failed to void old tuition log {old_log_id}. Aborting edit.")
        
        # 5. Create the new log (this will also auth and return the API dict)
        return await self.create_tuition_log(new_log_data, current_user, corrected_from_log_id=old_log_id)

    async def void_tuition_log(self, log_id: UUID, current_user: db_models.Users, skip_auth: bool = False) -> bool:
        """
        'Deletes' a tuition log by setting its status to VOID.
        Restricted to the Teacher owner.
        """
        log.info(f"User {current_user.id} attempting to void tuition log {log_id}.")
        
        # 1. Fetch the log
        log_obj = await self._get_log_by_id_internal(log_id)
        
        # 2. Authorize (skip if called from another authed method)
        if not skip_auth:
            self._authorize_role(current_user, [UserRole.TEACHER])
            if log_obj.teacher_id != current_user.id:
                log.warning(f"SECURITY: User {current_user.id} tried to void log {log_id} owned by {log_obj.teacher_id}.")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to void this log.")
            
        # 3. Perform the action
        log_obj.status = LogStatusEnum.VOID.value
        self.db.add(log_obj)
        await self.db.flush()
        return True

    # --- 5. Internal Formatters & Helpers ---

    async def _get_earliest_log_date(self) -> datetime:
        """Fetches the earliest log start time for week number calculations."""
        # ... (this method is correct and unchanged) ...
        log.info("Fetching earliest log start time for week calculation.")
        try:
            result = await self.db.execute(
                select(func.min(db_models.TuitionLogs.start_time)).filter(
                    db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
                )
            )
            earliest = result.scalars().first()
            return earliest if earliest else datetime.now()
        except Exception as e:
            log.error(f"Database error fetching earliest log date: {e}", exc_info=True)
            raise

    async def _get_paid_statuses_for_parents(self, parent_ids: list[UUID]) -> Dict[UUID, PaidStatus]:
        """Performs the FIFO paid status calculation for a list of parents."""
        # ... (this method is correct and unchanged) ...
        if not parent_ids:
            return {}
        
        payment_stmt = select(
            db_models.PaymentLogs.parent_id,
            func.sum(db_models.PaymentLogs.amount_paid)
        ).filter(
            db_models.PaymentLogs.parent_id.in_(parent_ids),
            db_models.PaymentLogs.status == LogStatusEnum.ACTIVE.value
        ).group_by(db_models.PaymentLogs.parent_id)
        
        payment_results = await self.db.execute(payment_stmt)
        parent_credits = {row.parent_id: row[1] for row in payment_results}
        
        log_stmt = select(db_models.TuitionLogs).options(
            selectinload(db_models.TuitionLogs.tuition_log_charges)
        ).join(db_models.TuitionLogCharges).filter(
            db_models.TuitionLogCharges.parent_id.in_(parent_ids),
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        ).order_by(db_models.TuitionLogs.start_time.asc())
        
        log_results = await self.db.execute(log_stmt)
        logs = log_results.scalars().unique().all() # Use .unique()
        
        log_statuses = {}
        for log in logs:
            parent_id = log.tuition_log_charges[0].parent_id
            log_cost = sum(c.cost for c in log.tuition_log_charges if c.parent_id == parent_id)
            
            remaining_credit = parent_credits.get(parent_id, Decimal(0))
            if remaining_credit >= log_cost:
                log_statuses[log.id] = PaidStatus.PAID
                parent_credits[parent_id] = remaining_credit - log_cost
            else:
                log_statuses[log.id] = PaidStatus.UNPAID
                parent_credits[parent_id] = Decimal(0)
                
        return log_statuses

    def _build_teacher_api_log(
        self, 
        log: db_models.TuitionLogs, 
        earliest_date: datetime, 
        paid_status: PaidStatus
    ) -> finance_models.TuitionLogReadForTeacher:
        """
        Private helper to build the ApiTuitionLogForTeacher model
        from a raw ORM object.
        """
        # ... (this method is correct and unchanged) ...
        charges_list = [
            finance_models.LogChargeRead(
                student_id=c.student.id,
                student_name=f"{c.student.first_name or ''} {c.student.last_name or ''}".strip(),
                cost=c.cost
            ) for c in log.tuition_log_charges
        ]
        
        api_model = finance_models.TuitionLogReadForTeacher(
            id=log.id,
            teacher=log.teacher,
            subject=log.subject,
            educational_system=log.educational_system,
            grade=log.grade,
            start_time=log.start_time,
            end_time=log.end_time,
            status=log.status,
            create_type=log.create_type,
            tuition_id=log.tuition_id,
            lesson_index=log.lesson_index,
            corrected_from_log_id=log.corrected_from_log_id,
            paid_status=paid_status,
            charges=charges_list,
            earliest_log_date=earliest_date
        )
        return api_model

    def _build_parent_api_log(
        self,
        log: db_models.TuitionLogs,
        earliest_date: datetime,
        paid_status: PaidStatus,
        parent_id: UUID
    ) -> finance_models.TuitionLogReadForParent:
        """Private helper to build the ApiTuitionLogForParent model."""
        # ... (this method is correct and unchanged) ...
        my_charge = Decimal(0)
        for c in log.tuition_log_charges:
            if c.parent_id == parent_id:
                my_charge = c.cost
                break
                
        api_model = finance_models.TuitionLogReadForParent(
            id=log.id,
            subject=log.subject,
            educational_system=log.educational_system,
            grade=log.grade,
            start_time=log.start_time,
            end_time=log.end_time,
            status=log.status,
            create_type=log.create_type,
            tuition_id=log.tuition_id,
            lesson_index=log.lesson_index,
            corrected_from_log_id=log.corrected_from_log_id,
            paid_status=paid_status,
            cost=my_charge,
            attendee_names=[
                f"{c.student.first_name or ''} {c.student.last_name or ''}".strip()
                for c in log.tuition_log_charges
            ],
            earliest_log_date=earliest_date
        )
        return api_model

    def _build_student_api_log(
        self,
        log: db_models.TuitionLogs,
        earliest_date: datetime,
        student_id: UUID
    ) -> finance_models.TuitionLogReadForStudent:
        """Private helper to build the ApiTuitionLogForStudent model."""
        # ... (this method is correct and unchanged) ...
        api_model = finance_models.TuitionLogReadForStudent(
            id=log.id,
            subject=log.subject,
            educational_system=log.educational_system,
            grade=log.grade,
            start_time=log.start_time,
            end_time=log.end_time,
            status=log.status,
            create_type=log.create_type,
            tuition_id=log.tuition_id,
            lesson_index=log.lesson_index,
            corrected_from_log_id=log.corrected_from_log_id,
            attendee_names=[
                f"{c.student.first_name or ''} {c.student.last_name or ''}".strip()
                for c in log.tuition_log_charges
            ],
            earliest_log_date=earliest_date
        )
        return api_model

# --- Service 2: Payment Log Management ---

class PaymentLogService:
    """Service for creating, reading, and managing payment logs."""
    
    def __init__(
        self, 
        db: Annotated[AsyncSession, Depends(get_db_session)],
        user_service: Annotated[UserService, Depends(UserService)]
    ):
        self.db = db
        self.user_service = user_service

    # --- Private Authorization Helper ---
    
    def _authorize(self, current_user: db_models.Users, allowed_roles: list[UserRole]):
        """
        A simple, private helper to check roles.
        Raises a 403 HTTPException if the user's role is not in the list.
        """
        allowed_role_values = [role.value for role in allowed_roles]
        
        if current_user.role not in allowed_role_values:
            log.warning(f"Unauthorized action by user {current_user.id} (Role: {current_user.role}). Required one of: {allowed_role_values}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action."
            )

    def _authorize_log_viewership(self, log_obj: db_models.PaymentLogs, current_user: db_models.Users):
        """
        Private helper to authorize if a user can *view* a specific log.
        Raises 403 HTTPException if they are not the associated parent or teacher.
        """
        is_teacher_owner = (
            current_user.role == UserRole.TEACHER.value and
            log_obj.teacher_id == current_user.id
        )
        is_parent_owner = (
            current_user.role == UserRole.PARENT.value and
            log_obj.parent_id == current_user.id
        )
        
        # If the user is neither the teacher nor the parent on the log, deny access.
        if not (is_teacher_owner or is_parent_owner):
             log.warning(f"SECURITY: User {current_user.id} tried to access payment log {log_obj.id} they do not own.")
             raise HTTPException(
                 status_code=status.HTTP_403_FORBIDDEN,
                 detail="You do not have permission to view this log."
             )

    # --- Private Data-Fetching Helpers (No Auth) ---
    
    async def _get_log_by_id_internal(self, log_id: UUID) -> db_models.PaymentLogs:
        """
        Internal helper to fetch a log by ID *without* authorization.
        Raises 404 if not found.
        """
        log.info(f"Internal fetch for payment log by ID: {log_id}")
        try:
            stmt = select(db_models.PaymentLogs).options(
selectinload(db_models.PaymentLogs.parent),
                selectinload(db_models.PaymentLogs.teacher)
            ).filter(db_models.PaymentLogs.id == log_id)
            
            result = await self.db.execute(stmt)
            log_obj = result.scalars().first()
            if not log_obj:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment log not found.")
            return log_obj
        except Exception as e:
            log.error(f"Database error fetching payment log by ID {log_id}: {e}", exc_info=True)
            raise

    async def get_all_payment_logs(self, current_user: db_models.Users) -> list[db_models.PaymentLogs]:
        """
        Internal data-fetching method.
        Fetches all payment logs relevant to the current user's role.
        NOW RAISES an error for unauthorized roles.
        """
        log.info(f"Internal fetch for all payment logs for user {current_user.id}")
        
        try:
            stmt = select(db_models.PaymentLogs).options(
selectinload(db_models.PaymentLogs.parent),
                selectinload(db_models.PaymentLogs.teacher)
            )
            
            if current_user.role == UserRole.TEACHER.value:
                stmt = stmt.filter(db_models.PaymentLogs.teacher_id == current_user.id)
            elif current_user.role == UserRole.PARENT.value:
                stmt = stmt.filter(db_models.PaymentLogs.parent_id == current_user.id)
            else:
                # CHANGED: Raise an error instead of returning []
                log.warning(f"User {current_user.id} (Role: {current_user.role}) is not authorized to get payment logs.")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User with role '{current_user.role}' is not authorized to view payment logs."
                )
                
            stmt = stmt.order_by(db_models.PaymentLogs.payment_date.desc())
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
            
        except HTTPException as http_exc:
            raise http_exc # Re-raise the auth error
        except Exception as e:
            log.error(f"Database error fetching all payment logs for user {current_user.id}: {e}", exc_info=True)
            raise

    # --- Public API-Facing Read Methods (With Auth) ---

    async def get_payment_log_by_id_for_api(self, log_id: UUID, current_user: db_models.Users) -> finance_models.PaymentLogRead:
        """
        API-facing method to get a single log.
        Uses the new _authorize_log_viewership helper.
        """
        try:
            # 1. Fetch the log
            log_obj = await self._get_log_by_id_internal(log_id)
            
            # 2. Authorize the user (checks if they are the parent OR teacher)
            self._authorize_log_viewership(log_obj, current_user)
            
            # 3. Format and return
            return self._format_payment_log_for_api(log_obj)
            
        except HTTPException as http_exc:
            raise http_exc # Re-raise 404s and 403s
        except Exception as e:
            log.error(f"Error in get_payment_log_by_id_for_api for log {log_id}: {e}", exc_info=True)
            raise

    async def get_all_payment_logs_for_api(self, current_user: db_models.Users) -> list[finance_models.PaymentLogRead]:
        """
        REFACTORED: API-facing method to get all logs.
        The authorization logic is now handled by the get_all_payment_logs method.
        """
        try:
            # 1. Fetch data (this will raise 403 for Students)
            rich_logs = await self.get_all_payment_logs(current_user)
            
            # 2. Format and return
            return [self._format_payment_log_for_api(log) for log in rich_logs]
            
        except HTTPException as http_exc:
            raise http_exc # Re-raise auth errors
        except Exception as e:
            log.error(f"Error in get_all_payment_logs_for_api for user {current_user.id}: {e}", exc_info=True)
            raise

    # --- Public Write Methods (With Auth) ---

    async def create_payment_log(self, log_data: dict, current_user: db_models.Users, corrected_from_log_id: Optional[UUID] = None) -> finance_models.PaymentLogRead:
        """
        REVISED: Creates a new payment log. Restricted to Teachers only.
        Returns it in the API format.
        """
        log.info(f"Attempting to create payment log by user {current_user.id}")
        
        # 1. Authorize: Only teachers can create payment logs
        self._authorize(current_user, [UserRole.TEACHER])
        
        try:
            # 2. Validate the raw dictionary
            input_model = finance_models.PaymentLogCreate.model_validate(log_data)
            
            # 3. IDOR Security Check
            if input_model.teacher_id != current_user.id:
                 log.warning(f"SECURITY: Teacher {current_user.id} tried to create a payment log for {input_model.teacher_id}.")
                 raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only create payment logs for yourself.")

            # 4. Validate parent_id
            parent = await self.user_service.get_user_by_id(input_model.parent_id)
            if not parent or parent.role != UserRole.PARENT.value:
                log.warning(f"Attempted to create payment log with non-existent or non-parent parent_id: {input_model.parent_id}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found.")

            # --- START OF FIX ---
            # 5. Create the ORM object directly, don't call a non-existent db method
            new_log_object = db_models.PaymentLogs(
                parent_id=input_model.parent_id,
                teacher_id=input_model.teacher_id,
                amount_paid=input_model.amount_paid,
                payment_date=input_model.payment_date,
                notes=input_model.notes,
                corrected_from_log_id=corrected_from_log_id,
                status=LogStatusEnum.ACTIVE.value  # Explicitly set status
            )
            
            # 5. Add to session and flush to get the new ID and other DB defaults
            self.db.add(new_log_object)
            await self.db.flush()
            
            # 6. Refresh to load the relationships (parent, teacher)
            #    that the formatter needs.
            await self.db.refresh(new_log_object, ['parent', 'teacher'])
            # --- END OF FIX ---
            
            # 7. Format for the API and return
            return self._format_payment_log_for_api(new_log_object)

        except (ValidationError, ValueError) as e:
            log.error(f"Pydantic validation failed for creating payment log. Data: {log_data}, Error: {e}")
            raise
        except HTTPException as http_exc:
            raise http_exc # Re-raise auth errors
        except Exception as e:
            log.error(f"Error in create_payment_log: {e}", exc_info=True)
            raise

    async def void_payment_log(self, log_id: UUID, current_user: db_models.Users) -> bool:
        """'Deletes' a payment log by setting its status to VOID. Restricted to Teachers."""
        log.info(f"Attempting to void payment log {log_id} by user {current_user.id}")
        
        # 1. Authorize: Only teachers can void logs
        self._authorize(current_user, [UserRole.TEACHER])
        
        try:
            # 2. FIXED: Call the internal, non-auth helper
            log_obj = await self._get_log_by_id_internal(log_id)
            
            # 3. Authorization Check (Ownership)
            if log_obj.teacher_id != current_user.id:
                 log.warning(f"SECURITY: User {current_user.id} tried to void payment log {log_id} they do not own.")
                 raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to void this log.")
            
            log_obj.status = LogStatusEnum.VOID.value
            self.db.add(log_obj)
            await self.db.flush()
            return True
        except HTTPException as http_exc:
            raise http_exc # Re-raise 404s
        except Exception as e:
            log.error(f"Database error voiding payment log {log_id}: {e}", exc_info=True)
            raise

    async def correct_payment_log(self, old_log_id: UUID, new_log_data: dict, current_user: db_models.Users) -> finance_models.PaymentLogRead:
        """
        Edits a log by voiding the old one and creating a new one. Restricted to Teachers.
        Returns the new, API-formatted log.
        """
        log.info(f"Attempting to correct payment log {old_log_id} by user {current_user.id}")
        
        # 1. Authorize: Only teachers can correct logs (this is redundant,
        #    as the methods it calls are already authorized, but good for clarity).
        self._authorize(current_user, [UserRole.TEACHER])
        
        # 2. Void the old log (this includes the ownership check)
        await self.void_payment_log(old_log_id, current_user)
        
        # 3. Create the new log, which returns the API-formatted dict
        return await self.create_payment_log(new_log_data, current_user, corrected_from_log_id=old_log_id)

    # --- API Formatting Method ---
        
    def _format_payment_log_for_api(self, log: db_models.PaymentLogs) -> finance_models.PaymentLogRead:
        """Formats a single payment log for the API."""
        if type(log) != db_models.PaymentLogs:
            raise TypeError(f"log must be type {db_models.PaymentLogs}, instead got {type(log)}")

        parent = log.parent
        teacher = log.teacher
        
        api_model = finance_models.PaymentLogRead(
            id=log.id,
            payment_date=log.payment_date,
            amount_paid=log.amount_paid,
            status=log.status,
            notes=log.notes,
            corrected_from_log_id=log.corrected_from_log_id,
            parent_name=f"{parent.first_name or ''} {parent.last_name or ''}".strip(),
            teacher_name=f"{teacher.first_name or ''} {teacher.last_name or ''}".strip(),
            currency=parent.currency
        )
        
        return api_model

# --- Service 3: Financial Summary ---

class FinancialSummaryService:
    """Service for calculating financial summaries."""
    
    def __init__(self, db: Annotated[AsyncSession, Depends(get_db_session)]):
        self.db = db

    async def get_financial_summary_for_api(self, current_user: db_models.Users) -> finance_models.FinancialSummaryReadRoleBased:
        """
        Public API-facing dispatcher for financial summaries.
        Returns a JSON-serializable dictionary.
        """
        log.info(f"Generating financial summary for user {current_user.id}")
        
        try:
            summary_model: Optional[finance_models.FinancialSummaryForParent | finance_models.FinancialSummaryForTeacher] = None
            
            if current_user.role == UserRole.PARENT.value:
                summary_model = await self._get_summary_for_parent(current_user.id)
            elif current_user.role == UserRole.TEACHER.value:
                summary_model = await self._get_summary_for_teacher(current_user.id)
            else:
                log.warning(f"SECURITY: User {current_user.id} tried to get financial summary. ")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role not authorized for financial summaries.")
            
            return summary_model
            
        except HTTPException as http_exc:
            raise http_exc # Re-raise auth errors
        except Exception as e:
            log.error(f"Error in get_financial_summary_for_api for user {current_user.id}: {e}", exc_info=True)
            raise

    async def _get_summary_for_parent(self, parent_id: UUID) -> finance_models.FinancialSummaryForParent:
        """
        REFACTORED: Calculates and returns the summary Pydantic model for a parent.
        Runs queries sequentially.
        """
        
        # 1. Define all the queries we need
        charges_stmt = select(func.coalesce(func.sum(db_models.TuitionLogCharges.cost), Decimal(0))).join(
            db_models.TuitionLogs, 
            db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
        ).filter(
            db_models.TuitionLogCharges.parent_id == parent_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        )
        
        payments_stmt = select(func.coalesce(func.sum(db_models.PaymentLogs.amount_paid), Decimal(0))).filter(
            db_models.PaymentLogs.parent_id == parent_id,
            db_models.PaymentLogs.status == LogStatusEnum.ACTIVE.value
        )
        
        count_stmt = select(func.count(db_models.TuitionLogs.id.distinct())).join(
            db_models.TuitionLogCharges, 
            db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
        ).filter(
            db_models.TuitionLogCharges.parent_id == parent_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        )
        
        # 2. FIXED: Run the charge and payment queries SEQUENTIALLY
        total_charges_res = await self.db.execute(charges_stmt)
        total_payments_res = await self.db.execute(payments_stmt)
        
        total_charges = total_charges_res.scalar()
        total_payments = total_payments_res.scalar()
        
        balance = total_payments - total_charges
        total_due = max(Decimal(0), -balance)
        credit_balance = max(Decimal(0), balance)
        
        # 3. Only run the count query if the parent actually owes money
        unpaid_count = 0
        if total_due > 0:
            unpaid_count_res = await self.db.execute(count_stmt)
            unpaid_count = unpaid_count_res.scalar()
            
        return finance_models.FinancialSummaryForParent(
            total_due=total_due,
            credit_balance=credit_balance,
            unpaid_count=unpaid_count
        )

    async def _get_summary_for_teacher(self, teacher_id: UUID) -> finance_models.FinancialSummaryForTeacher:
        """
        REFACTORED: Calculates and returns the summary Pydantic model for a teacher.
        Fixes the interval syntax.
        """
        # 1. Get per-parent balances (this query is correct)
        charges_subq = select(
            db_models.TuitionLogCharges.parent_id,
            func.sum(db_models.TuitionLogCharges.cost).label("total_charges")
        ).join(db_models.TuitionLogs).filter(
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        ).group_by(db_models.TuitionLogCharges.parent_id).subquery()

        payments_subq = select(
            db_models.PaymentLogs.parent_id,
            func.sum(db_models.PaymentLogs.amount_paid).label("total_payments")
        ).filter(
            db_models.PaymentLogs.teacher_id == teacher_id,
            db_models.PaymentLogs.status == LogStatusEnum.ACTIVE.value
        ).group_by(db_models.PaymentLogs.parent_id).subquery()

        balance_stmt = select(
            charges_subq.c.parent_id,
            (func.coalesce(payments_subq.c.total_payments, Decimal(0)) - charges_subq.c.total_charges).label("balance")
        ).join(
            payments_subq, charges_subq.c.parent_id == payments_subq.c.parent_id, isouter=True
        )
        
        # 2. Get lessons this month (FIXED QUERY)
        month_count_stmt = select(func.count(db_models.TuitionLogs.id)).filter(
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value,
            db_models.TuitionLogs.start_time >= func.date_trunc('month', func.now()),
            # --- THIS IS THE FIX ---
            # We use text() to prevent SQLAlchemy from parameterizing '1 month'
            db_models.TuitionLogs.start_time < (func.date_trunc('month', func.now()) + text("interval '1 month'"))
            # --- END OF FIX ---
        )
        
        # 3. Run queries sequentially (as we fixed before)
        parent_balances_res = await self.db.execute(balance_stmt)
        lessons_this_month_res = await self.db.execute(month_count_stmt)
        
        parent_balances = parent_balances_res.all()
        lessons_this_month = lessons_this_month_res.scalar()

        # 4. Calculate final values
        total_owed_to_teacher = Decimal(0)
        total_credit_held = Decimal(0)
        for row in parent_balances:
            if row.balance < 0:
                total_owed_to_teacher += -row.balance
            elif row.balance > 0:
                total_credit_held += row.balance
        
        return finance_models.FinancialSummaryForTeacher(
            total_owed_to_teacher=total_owed_to_teacher,
            total_credit_held=total_credit_held,
            total_lessons_given_this_month=lessons_this_month
        )
