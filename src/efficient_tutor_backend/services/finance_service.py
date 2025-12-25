'''

'''
from typing import Optional, Annotated, Any
from collections import defaultdict
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

    async def _authorize_for_filtering(
        self, 
        current_user: db_models.Users, 
        student_id: Optional[UUID], 
        parent_id: Optional[UUID], 
        teacher_id: Optional[UUID]
    ) -> None:
        """
        Validates filtering parameters against the current user's role and permissions.
        Raises HTTPException(403) if the user attempts to filter by an ID they are not
        authorized to access or view.
        """
        # 1. Admin: Full Access
        if current_user.role == UserRole.ADMIN.value:
            return

        # 2. Teacher Rules
        elif current_user.role == UserRole.TEACHER.value:
            # Identity Check
            if teacher_id and teacher_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teachers can only filter by their own ID.")
            
            # Relationship Check: Student
            if student_id:
                # Check if student is in any of this teacher's tuitions
                stmt = select(db_models.TuitionTemplateCharges.id).join(
                    db_models.Tuitions
                ).filter(
                    db_models.Tuitions.teacher_id == current_user.id,
                    db_models.TuitionTemplateCharges.student_id == student_id
                ).limit(1)
                result = await self.db.execute(stmt)
                if not result.scalars().first():
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not associated with this student.")

            # Relationship Check: Parent
            if parent_id:
                # Check if parent is in any of this teacher's tuitions
                stmt = select(db_models.TuitionTemplateCharges.id).join(
                    db_models.Tuitions
                ).filter(
                    db_models.Tuitions.teacher_id == current_user.id,
                    db_models.TuitionTemplateCharges.parent_id == parent_id
                ).limit(1)
                result = await self.db.execute(stmt)
                if not result.scalars().first():
                     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not associated with this parent.")

        # 3. Parent Rules
        elif current_user.role == UserRole.PARENT.value:
            # Identity Check
            if parent_id and parent_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Parents can only filter by their own ID.")

            # Relationship Check: Student (In-Memory)
            if student_id:
                # UserService ensures 'students' relationship is loaded for Parents
                if not any(s.id == student_id for s in current_user.students):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only filter by your own children.")

            # Relationship Check: Teacher (DB Check)
            if teacher_id:
                # Check if this teacher teaches any of the parent's children
                stmt = select(db_models.Tuitions.id).join(
                    db_models.TuitionTemplateCharges
                ).filter(
                    db_models.TuitionTemplateCharges.parent_id == current_user.id,
                    db_models.Tuitions.teacher_id == teacher_id
                ).limit(1)
                result = await self.db.execute(stmt)
                if not result.scalars().first():
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not associated with this teacher.")

        # 4. Student Rules
        elif current_user.role == UserRole.STUDENT.value:
            # Strict Ban on Parent/Teacher filters
            if parent_id is not None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students cannot filter by parent_id.")
            if teacher_id is not None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students cannot filter by teacher_id.")
            
            # Identity Check
            if student_id and student_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only filter by their own ID.")

        else:
            # Fallback for unknown roles
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized role.")

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

    async def get_all_tuition_logs_orm(
        self, 
        current_user: db_models.Users, 
        include_void: bool = False,
        target_student_id: Optional[UUID] = None,
        target_parent_id: Optional[UUID] = None,
        target_teacher_id: Optional[UUID] = None
    ) -> list[db_models.TuitionLogs]:
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
        
        # 1. MANDATORY ROLE FILTER (The "NO MATTER WHAT" clause)
        charges_joined = False
        if current_user.role == UserRole.TEACHER.value:
            stmt = stmt.filter(db_models.TuitionLogs.teacher_id == current_user.id)
        elif current_user.role == UserRole.PARENT.value:
            # Parent can only access logs where they are in the charges
            stmt = stmt.join(db_models.TuitionLogCharges).filter(
                db_models.TuitionLogCharges.parent_id == current_user.id
            )
            charges_joined = True
        elif current_user.role == UserRole.STUDENT.value:
             # Student can only access logs where they are in the charges
            stmt = stmt.join(db_models.TuitionLogCharges).filter(
                db_models.TuitionLogCharges.student_id == current_user.id
            )
            charges_joined = True
        else:
            return [] # Other roles see no logs

        # 2. OPTIONAL TARGET FILTERS
        if target_teacher_id:
            stmt = stmt.filter(db_models.TuitionLogs.teacher_id == target_teacher_id)
        
        # If we need to filter by student or parent, and we haven't joined yet (i.e., for a Teacher)
        if (target_student_id or target_parent_id) and not charges_joined:
            stmt = stmt.join(db_models.TuitionLogCharges)

        if target_student_id:
             stmt = stmt.filter(
                 db_models.TuitionLogCharges.student_id == target_student_id
             )

        if target_parent_id:
             stmt = stmt.filter(
                 db_models.TuitionLogCharges.parent_id == target_parent_id
             )

        # Only filter out void logs for Parent users
        if current_user.role == UserRole.PARENT.value:
            stmt = stmt.filter(db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value)
            
        stmt = stmt.order_by(db_models.TuitionLogs.start_time.desc()).distinct()
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
                ledger = await self._calculate_teacher_ledger(current_user.id)
                # Note: _build_teacher_api_log needs to be updated to accept the full ledger
                return self._build_teacher_api_log(log_obj, earliest_date, ledger)
                
            elif current_user.role == UserRole.PARENT.value:
                ledger = await self._calculate_parent_ledger(current_user.id)
                status = ledger.get(log_obj.id, PaidStatus.UNPAID)
                return self._build_parent_api_log(log_obj, earliest_date, status, current_user.id)
            else: # Student
                return self._build_student_api_log(log_obj, earliest_date, current_user.id)

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            log.error(f"Error in get_tuition_log_by_id_for_api: {e}", exc_info=True)
            raise

    async def get_all_tuition_logs_for_api(
        self, 
        current_user: db_models.Users,
        student_id: Optional[UUID] = None,
        parent_id: Optional[UUID] = None,
        teacher_id: Optional[UUID] = None
    ) -> list[finance_models.TuitionLogReadRoleBased]:
        """
        REFACTORED: API-facing method.
        1. Authorizes Filtering Rules (Identity & Relationship checks)
        2. Fetches Data with Filters
        3. Formats
        """
        log.info(f"User {current_user.id} (Role: {current_user.role}) requesting all tuition logs for API.")
        try:
            # 1. Authorize Filtering Rules (Strict Security Check)
            await self._authorize_for_filtering(current_user, student_id, parent_id, teacher_id)
            
            # 2. Fetch Data (uses the internal fetcher with filters)
            rich_logs = await self.get_all_tuition_logs_orm(
                current_user=current_user,
                target_student_id=student_id,
                target_parent_id=parent_id,
                target_teacher_id=teacher_id
            )
            if not rich_logs:
                return []
                
            earliest_date = await self._get_earliest_log_date()
            
            # 3. Get paid statuses and Format
            api_logs = []
            
            if current_user.role == UserRole.TEACHER.value:
                ledger = await self._calculate_teacher_ledger(current_user.id)
                for rich_log in rich_logs:
                    # Pass the full ledger to the builder
                    api_logs.append(self._build_teacher_api_log(rich_log, earliest_date, ledger))
            
            elif current_user.role == UserRole.PARENT.value:
                ledger = await self._calculate_parent_ledger(current_user.id)
                for rich_log in rich_logs:
                    status = ledger.get(rich_log.id, PaidStatus.UNPAID)
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
            
            # Recalculate ledger to reflect the new log's status immediately
            ledger = await self._calculate_teacher_ledger(current_user.id)
            
            return self._build_teacher_api_log(
                log=new_log_object,
                earliest_date=earliest_date,
                ledger=ledger
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

    async def _calculate_teacher_ledger(self, teacher_id: UUID) -> dict[tuple[UUID, UUID], PaidStatus]:
        """
        Calculates the payment status for every student charge in every log for a teacher.
        Returns a map: {(log_id, student_id): PaidStatus}
        """
        # 1. Fetch all parent wallets (Total Paid)
        payment_stmt = select(
            db_models.PaymentLogs.parent_id,
            func.sum(db_models.PaymentLogs.amount_paid)
        ).filter(
            db_models.PaymentLogs.teacher_id == teacher_id,
            db_models.PaymentLogs.status == LogStatusEnum.ACTIVE.value
        ).group_by(db_models.PaymentLogs.parent_id)
        
        payment_results = await self.db.execute(payment_stmt)
        parent_wallets = {row.parent_id: row[1] for row in payment_results}

        # 2. Fetch all logs chronologically
        log_stmt = select(db_models.TuitionLogs).options(
            selectinload(db_models.TuitionLogs.tuition_log_charges)
        ).filter(
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        ).order_by(db_models.TuitionLogs.start_time.asc())

        log_results = await self.db.execute(log_stmt)
        logs = log_results.scalars().unique().all()

        # 3. FIFO Allocation
        ledger_map = {}
        
        for log_entry in logs:
            for charge in log_entry.tuition_log_charges:
                current_wallet = parent_wallets.get(charge.parent_id, Decimal(0))
                
                if current_wallet >= charge.cost:
                    ledger_map[(log_entry.id, charge.student_id)] = PaidStatus.PAID
                    parent_wallets[charge.parent_id] = current_wallet - charge.cost
                else:
                    ledger_map[(log_entry.id, charge.student_id)] = PaidStatus.UNPAID
                    # Even if partial payment exists, we mark as UNPAID for simplicity,
                    # or we could drain the wallet to 0. Let's drain it.
                    parent_wallets[charge.parent_id] = max(Decimal(0), current_wallet - charge.cost)
                    
        return ledger_map

    async def _calculate_parent_ledger(self, parent_id: UUID) -> dict[UUID, PaidStatus]:
        """
        Calculates the payment status for every log for a specific parent.
        Returns a map: {log_id: PaidStatus}
        """
        # 1. Fetch Parent's Total Paid
        payment_stmt = select(func.sum(db_models.PaymentLogs.amount_paid)).filter(
            db_models.PaymentLogs.parent_id == parent_id,
            db_models.PaymentLogs.status == LogStatusEnum.ACTIVE.value
        )
        payment_res = await self.db.execute(payment_stmt)
        wallet = payment_res.scalar() or Decimal(0)

        # 2. Fetch relevant logs chronologically
        # We need logs where this parent is involved (via student charges)
        log_stmt = select(db_models.TuitionLogs).join(
            db_models.TuitionLogCharges
        ).options(
             selectinload(db_models.TuitionLogs.tuition_log_charges)
        ).filter(
            db_models.TuitionLogCharges.parent_id == parent_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        ).order_by(db_models.TuitionLogs.start_time.asc()).distinct()

        log_results = await self.db.execute(log_stmt)
        logs = log_results.scalars().unique().all()

        # 3. FIFO Allocation
        ledger_map = {}

        for log_entry in logs:
            # Calculate total cost FOR THIS PARENT in this log
            my_cost = sum(c.cost for c in log_entry.tuition_log_charges if c.parent_id == parent_id)
            
            if wallet >= my_cost:
                ledger_map[log_entry.id] = PaidStatus.PAID
                wallet -= my_cost
            else:
                ledger_map[log_entry.id] = PaidStatus.UNPAID
                wallet = max(Decimal(0), wallet - my_cost)

        return ledger_map

    def _build_teacher_api_log(
        self, 
        log: db_models.TuitionLogs, 
        earliest_date: datetime, 
        ledger: dict[tuple[UUID, UUID], PaidStatus]
    ) -> finance_models.TuitionLogReadForTeacher:
        """
        Private helper to build the ApiTuitionLogForTeacher model
        from a raw ORM object using the granular ledger.
        """
        charges_list = []
        all_charges_paid = True
        
        for c in log.tuition_log_charges:
            # Look up status for this specific (log_id, student_id) combo
            status = ledger.get((log.id, c.student_id), PaidStatus.UNPAID)
            
            if status == PaidStatus.UNPAID:
                all_charges_paid = False
            
            charges_list.append(
                finance_models.LogChargeRead(
                    student_id=c.student.id,
                    student_name=f"{c.student.first_name or ''} {c.student.last_name or ''}".strip(),
                    cost=c.cost,
                    paid_status=status
                )
            )
        
        top_level_status = PaidStatus.PAID if all_charges_paid and charges_list else PaidStatus.UNPAID

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
            paid_status=top_level_status,
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
            teacher_name=f"{log.teacher.first_name or ''} {log.teacher.last_name or ''}".strip(),
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

    async def _authorize_for_filtering(
        self, 
        current_user: db_models.Users, 
        parent_id: Optional[UUID], 
        teacher_id: Optional[UUID]
    ) -> None:
        """
        Validates filtering parameters against the current user's role and permissions.
        Raises HTTPException(403) for unauthorized access or relationship mismatches.
        """
        # 1. Admin: Full Access
        if current_user.role == UserRole.ADMIN.value:
            return

        # 2. Teacher Rules
        elif current_user.role == UserRole.TEACHER.value:
            # Identity Check
            if teacher_id and teacher_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teachers can only filter by their own ID.")
            
            # Relationship Check: Parent
            if parent_id:
                # Check if parent has a student in this teacher's tuitions
                stmt = select(db_models.TuitionTemplateCharges.id).join(
                    db_models.Tuitions
                ).filter(
                    db_models.Tuitions.teacher_id == current_user.id,
                    db_models.TuitionTemplateCharges.parent_id == parent_id
                ).limit(1)
                result = await self.db.execute(stmt)
                if not result.scalars().first():
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not associated with this parent.")

        # 3. Parent Rules
        elif current_user.role == UserRole.PARENT.value:
            # Identity Check
            if parent_id and parent_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Parents can only filter by their own ID.")

            # Relationship Check: Teacher
            if teacher_id:
                # Check if this teacher teaches any of the parent's children
                stmt = select(db_models.Tuitions.id).join(
                    db_models.TuitionTemplateCharges
                ).filter(
                    db_models.TuitionTemplateCharges.parent_id == current_user.id,
                    db_models.Tuitions.teacher_id == teacher_id
                ).limit(1)
                result = await self.db.execute(stmt)
                if not result.scalars().first():
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not associated with this teacher.")

        # 4. Student Rules
        elif current_user.role == UserRole.STUDENT.value:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students cannot access payment logs.")

        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized role.")
    
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

    async def get_all_payment_logs(
        self, 
        current_user: db_models.Users,
        target_parent_id: Optional[UUID] = None,
        target_teacher_id: Optional[UUID] = None
    ) -> list[db_models.PaymentLogs]:
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
            
            # 1. MANDATORY ROLE FILTER
            if current_user.role == UserRole.TEACHER.value:
                stmt = stmt.filter(db_models.PaymentLogs.teacher_id == current_user.id)
            elif current_user.role == UserRole.PARENT.value:
                stmt = stmt.filter(db_models.PaymentLogs.parent_id == current_user.id)
            elif current_user.role == UserRole.ADMIN.value:
                pass # Admin sees all
            else:
                # CHANGED: Raise an error instead of returning []
                log.warning(f"User {current_user.id} (Role: {current_user.role}) is not authorized to get payment logs.")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User with role '{current_user.role}' is not authorized to view payment logs."
                )

            # 2. OPTIONAL TARGET FILTERS
            if target_parent_id:
                stmt = stmt.filter(db_models.PaymentLogs.parent_id == target_parent_id)
            if target_teacher_id:
                stmt = stmt.filter(db_models.PaymentLogs.teacher_id == target_teacher_id)
                
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

    async def get_all_payment_logs_for_api(
        self, 
        current_user: db_models.Users,
        parent_id: Optional[UUID] = None,
        teacher_id: Optional[UUID] = None
    ) -> list[finance_models.PaymentLogRead]:
        """
        REFACTORED: API-facing method to get all logs.
        The authorization logic is now handled by the get_all_payment_logs method.
        """
        try:
            # 1. Authorize Filtering Rules (Strict Security Check)
            await self._authorize_for_filtering(current_user, parent_id, teacher_id)
            
            # 2. Fetch data (this will raise 403 for Students)
            rich_logs = await self.get_all_payment_logs(
                current_user=current_user,
                target_parent_id=parent_id,
                target_teacher_id=teacher_id
            )
            
            # 3. Format and return
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
    
    def __init__(
        self, 
        db: Annotated[AsyncSession, Depends(get_db_session)],
        tuition_log_service: Annotated[TuitionLogService, Depends(TuitionLogService)]
    ):
        self.db = db
        self.tuition_log_service = tuition_log_service

    async def _authorize_for_filtering(
        self, 
        current_user: db_models.Users, 
        parent_id: Optional[UUID], 
        student_id: Optional[UUID], 
        teacher_id: Optional[UUID]
    ) -> None:
        """
        Validates filtering parameters for financial summaries.
        Raises HTTPException(403) for unauthorized access.
        """
        # 1. Teacher Rules
        if current_user.role == UserRole.TEACHER.value:
            # Target Check: Parent
            if parent_id:
                stmt = select(db_models.TuitionTemplateCharges.id).join(
                    db_models.Tuitions
                ).filter(
                    db_models.Tuitions.teacher_id == current_user.id,
                    db_models.TuitionTemplateCharges.parent_id == parent_id
                ).limit(1)
                result = await self.db.execute(stmt)
                if not result.scalars().first():
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not associated with this parent.")

            # Target Check: Student
            if student_id:
                stmt = select(db_models.TuitionTemplateCharges.id).join(
                    db_models.Tuitions
                ).filter(
                    db_models.Tuitions.teacher_id == current_user.id,
                    db_models.TuitionTemplateCharges.student_id == student_id
                ).limit(1)
                result = await self.db.execute(stmt)
                if not result.scalars().first():
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not associated with this student.")

        # 2. Parent Rules
        elif current_user.role == UserRole.PARENT.value:
            # Target Check: Teacher
            if teacher_id:
                stmt = select(db_models.Tuitions.id).join(
                    db_models.TuitionTemplateCharges
                ).filter(
                    db_models.TuitionTemplateCharges.parent_id == current_user.id,
                    db_models.Tuitions.teacher_id == teacher_id
                ).limit(1)
                result = await self.db.execute(stmt)
                if not result.scalars().first():
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not associated with this teacher.")

            # Target Check: Student (In-Memory)
            if student_id:
                if not any(s.id == student_id for s in current_user.students):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view summaries for your own children.")

        # 3. Unauthorized Roles (Student, Admin, etc.)
        else:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role not authorized for financial summaries.")

    async def get_financial_summary_for_api(
        self, 
        current_user: db_models.Users,
        parent_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        teacher_id: Optional[UUID] = None
    ) -> finance_models.FinancialSummaryReadRoleBased:
        """
        Public API-facing dispatcher for financial summaries.
        Returns a JSON-serializable dictionary.
        """
        log.info(f"Generating financial summary for user {current_user.id}")
        
        try:
            # 1. Authorize Filtering Rules (Strict Security Check)
            await self._authorize_for_filtering(current_user, parent_id, student_id, teacher_id)

            summary_model: Optional[finance_models.FinancialSummaryForParent | finance_models.FinancialSummaryForTeacher] = None
            
            if current_user.role == UserRole.PARENT.value:
                if teacher_id:
                    summary_model = await self._get_summary_for_parent_for_specific_teacher(current_user.id, teacher_id)
                elif student_id:
                    summary_model = await self._get_summary_for_parent_for_specific_student(current_user.id, student_id)
                else:
                    summary_model = await self._get_summary_for_parent(current_user.id)

            elif current_user.role == UserRole.TEACHER.value:
                if parent_id:
                    summary_model = await self._get_summary_for_teacher_for_specific_parent(current_user.id, parent_id)
                elif student_id:
                    summary_model = await self._get_summary_for_teacher_for_specific_student(current_user.id, student_id)
                else:
                    summary_model = await self._get_summary_for_teacher(current_user.id)
            else:
                # This branch is technically unreachable now due to _authorize_for_filtering, 
                # but good to keep as a fallback safety net.
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
        Calculates and returns the summary Pydantic model for a parent.
        Aggregates per-teacher balances to avoid "Global Netting" errors.
        """
        
        # 1. Calculate Total Charges Per Teacher
        charges_stmt = select(
            db_models.TuitionLogs.teacher_id,
            func.sum(db_models.TuitionLogCharges.cost).label("total_charges")
        ).join(
            db_models.TuitionLogCharges,
            db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
        ).filter(
            db_models.TuitionLogCharges.parent_id == parent_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        ).group_by(db_models.TuitionLogs.teacher_id)
        
        # 2. Calculate Total Payments Per Teacher
        payments_stmt = select(
            db_models.PaymentLogs.teacher_id,
            func.sum(db_models.PaymentLogs.amount_paid).label("total_payments")
        ).filter(
            db_models.PaymentLogs.parent_id == parent_id,
            db_models.PaymentLogs.status == LogStatusEnum.ACTIVE.value
        ).group_by(db_models.PaymentLogs.teacher_id)
        
        charges_res = await self.db.execute(charges_stmt)
        payments_res = await self.db.execute(payments_stmt)
        
        charges_map = {row.teacher_id: row.total_charges for row in charges_res}
        payments_map = {row.teacher_id: row.total_payments for row in payments_res}
        
        # --- NEW STEP: Fetch Detailed Logs for Unpaid Count Calculation ---
        # We need the chronological list of charges per teacher to run the FIFO check
        details_stmt = select(
            db_models.TuitionLogs.teacher_id,
            db_models.TuitionLogCharges.cost
        ).join(
            db_models.TuitionLogCharges,
            db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
        ).filter(
            db_models.TuitionLogCharges.parent_id == parent_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        ).order_by(db_models.TuitionLogs.start_time.asc())

        details_res = await self.db.execute(details_stmt)
        
        # Group charges by teacher: { teacher_id: [cost1, cost2, ...] }
        logs_by_teacher = defaultdict(list)
        for row in details_res:
            logs_by_teacher[row.teacher_id].append(row.cost)

        # 3. Calculate Balance Per Teacher
        all_teachers = set(charges_map.keys()) | set(payments_map.keys())
        
        total_due = Decimal(0)
        credit_balance = Decimal(0)
        unpaid_count = 0
        
        for teacher_id in all_teachers:
            c = charges_map.get(teacher_id, Decimal(0))
            p = payments_map.get(teacher_id, Decimal(0))
            balance = p - c
            
            if balance < 0:
                # Debt Exists
                total_due += (-balance)
                
                # --- NEW LOGIC: Calculate Unpaid Count via FIFO ---
                # We simulate the wallet for this teacher
                wallet = p 
                teacher_charges = logs_by_teacher.get(teacher_id, [])
                
                for charge_cost in teacher_charges:
                    if wallet >= charge_cost:
                        # Fully covered
                        wallet -= charge_cost
                    else:
                        # Not fully covered (Partial or Zero payment)
                        # This counts as 1 unpaid lesson
                        unpaid_count += 1
                        # Wallet is empty or used up
                        wallet = max(Decimal(0), wallet - charge_cost)

            elif balance > 0:
                credit_balance += balance
                # If balance is positive, unpaid_count is 0 for this teacher.
            
        return finance_models.FinancialSummaryForParent(
            total_due=total_due,
            credit_balance=credit_balance,
            unpaid_count=unpaid_count
        )

    async def _get_summary_for_parent_for_specific_teacher(self, parent_id: UUID, teacher_id: UUID) -> finance_models.FinancialSummaryForParent:
        """
        Calculates summary for a parent specific to ONE teacher.
        """
        # 1. Total Charges for this Teacher
        charges_stmt = select(func.sum(db_models.TuitionLogCharges.cost)).join(
            db_models.TuitionLogs
        ).filter(
            db_models.TuitionLogCharges.parent_id == parent_id,
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        )
        total_charges = (await self.db.execute(charges_stmt)).scalar() or Decimal(0)

        # 2. Total Payments to this Teacher
        payments_stmt = select(func.sum(db_models.PaymentLogs.amount_paid)).filter(
            db_models.PaymentLogs.parent_id == parent_id,
            db_models.PaymentLogs.teacher_id == teacher_id,
            db_models.PaymentLogs.status == LogStatusEnum.ACTIVE.value
        )
        total_payments = (await self.db.execute(payments_stmt)).scalar() or Decimal(0)

        balance = total_payments - total_charges
        
        total_due = Decimal(0)
        credit_balance = Decimal(0)
        unpaid_count = 0

        if balance < 0:
            total_due = -balance
            
            # CORRECTED: Use ledger to get accurate unpaid count
            ledger = await self.tuition_log_service._calculate_teacher_ledger(teacher_id)
            
            logs_stmt = select(
                db_models.TuitionLogCharges.tuition_log_id,
                db_models.TuitionLogCharges.student_id
            ).join(db_models.TuitionLogs).filter(
                db_models.TuitionLogs.teacher_id == teacher_id,
                db_models.TuitionLogCharges.parent_id == parent_id,
                db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
            )
            log_charges = (await self.db.execute(logs_stmt)).all()

            for log_id, student_id in log_charges:
                if ledger.get((log_id, student_id), PaidStatus.UNPAID) == PaidStatus.UNPAID:
                    unpaid_count += 1
        else:
            credit_balance = balance

        return finance_models.FinancialSummaryForParent(
            total_due=total_due,
            credit_balance=credit_balance,
            unpaid_count=unpaid_count
        )

    async def _get_summary_for_parent_for_specific_student(self, parent_id: UUID, student_id: UUID) -> finance_models.FinancialSummaryForParent:
        """
        Calculates summary for a parent specific to ONE student.
        Note: Credit is global per teacher-parent, so we can't easily attribute credit to a student.
        We will show Total Due for this student's classes. Credit will be 0.
        """
        # 1. We need to iterate over all teachers this student has, because ledger is per-teacher.
        # Actually, simpler: We iterate over all logs for this student, check their status via the ledger.
        
        # Fetch all teachers involved with this student
        teachers_stmt = select(db_models.TuitionLogs.teacher_id).distinct().join(
            db_models.TuitionLogCharges
        ).filter(
            db_models.TuitionLogCharges.student_id == student_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        )
        teacher_ids = (await self.db.execute(teachers_stmt)).scalars().all()

        total_unpaid_cost = Decimal(0)
        unpaid_count = 0
        
        for tid in teacher_ids:
            # Get ledger for this teacher
            ledger = await self.tuition_log_service._calculate_teacher_ledger(tid)
            
            # Fetch all logs for this student & teacher
            logs_stmt = select(db_models.TuitionLogs).join(
                db_models.TuitionLogCharges
            ).options(
                selectinload(db_models.TuitionLogs.tuition_log_charges) # FIX: Eager load charges
            ).filter(
                db_models.TuitionLogs.teacher_id == tid,
                db_models.TuitionLogCharges.student_id == student_id,
                db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
            ).distinct()
            
            logs = (await self.db.execute(logs_stmt)).scalars().all()
            
            for l in logs:
                status = ledger.get((l.id, student_id), PaidStatus.UNPAID)
                if status == PaidStatus.UNPAID:
                    unpaid_count += 1
                    # Find the cost for this student in this log
                    # (Optimization: could fetch cost in query, but list is usually small)
                    for c in l.tuition_log_charges:
                        if c.student_id == student_id:
                            total_unpaid_cost += c.cost
                            break
        
        return finance_models.FinancialSummaryForParent(
            total_due=total_unpaid_cost,
            credit_balance=Decimal(0), # Cannot attribute credit to specific student easily
            unpaid_count=unpaid_count
        )

    async def _get_summary_for_teacher(self, teacher_id: UUID) -> finance_models.FinancialSummaryForTeacher:
        """
        Calculates and returns the summary for a teacher.
        Includes per-parent breakdown and uses Ledger Logic for counts.
        """
        # 1. Get Total Charges Per Parent
        charges_stmt = select(
            db_models.TuitionLogCharges.parent_id,
            func.sum(db_models.TuitionLogCharges.cost).label("total_charges")
        ).join(
            db_models.TuitionLogs,
            db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
        ).filter(
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        ).group_by(db_models.TuitionLogCharges.parent_id)

        # 2. Get Total Payments Per Parent
        payments_stmt = select(
            db_models.PaymentLogs.parent_id,
            func.sum(db_models.PaymentLogs.amount_paid).label("total_payments")
        ).filter(
            db_models.PaymentLogs.teacher_id == teacher_id,
            db_models.PaymentLogs.status == LogStatusEnum.ACTIVE.value
        ).group_by(db_models.PaymentLogs.parent_id)

        charges_res = await self.db.execute(charges_stmt)
        payments_res = await self.db.execute(payments_stmt)
        
        charges_map = {row.parent_id: row.total_charges for row in charges_res}
        payments_map = {row.parent_id: row.total_payments for row in payments_res}
        
        all_parent_ids = list(set(charges_map.keys()) | set(payments_map.keys()))
        
        # 3. Aggregate Final Results
        total_owed_to_teacher = Decimal(0)
        total_credit_held = Decimal(0)

        for parent_id in all_parent_ids:
            c = charges_map.get(parent_id, Decimal(0))
            p = payments_map.get(parent_id, Decimal(0))
            balance = p - c # Positive = Credit, Negative = Owed
            
            if balance < 0:
                total_owed_to_teacher += (-balance)
            elif balance > 0:
                total_credit_held += balance
            
        # 4. Lessons this month
        month_count_stmt = select(func.count(db_models.TuitionLogs.id)).filter(
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value,
            db_models.TuitionLogs.start_time >= func.date_trunc('month', func.now()),
            db_models.TuitionLogs.start_time < (func.date_trunc('month', func.now()) + text("interval '1 month'"))
        )
        lessons_this_month = (await self.db.execute(month_count_stmt)).scalar()

        # 5. Calculate Unpaid Lessons (Total unique logs that are not fully paid)
        ledger = await self.tuition_log_service._calculate_teacher_ledger(teacher_id)
        
        # We need to find logs where ANY student is UNPAID.
        # The ledger keys are (log_id, student_id).
        unpaid_log_ids = set()
        for (log_id, _), status in ledger.items():
            if status == PaidStatus.UNPAID:
                unpaid_log_ids.add(log_id)
        
        unpaid_lessons_count = len(unpaid_log_ids)

        return finance_models.FinancialSummaryForTeacher(
            total_owed_to_teacher=total_owed_to_teacher,
            total_credit_held=total_credit_held,
            total_lessons_given_this_month=lessons_this_month,
            unpaid_lessons_count=unpaid_lessons_count
        )

    async def _get_summary_for_teacher_for_specific_parent(self, teacher_id: UUID, target_parent_id: UUID) -> finance_models.FinancialSummaryForTeacher:
        """
        Calculates summary for a teacher specific to ONE parent.
        """
        # 1. Charges for this parent
        charges_stmt = select(func.sum(db_models.TuitionLogCharges.cost)).join(
            db_models.TuitionLogs
        ).filter(
            db_models.TuitionLogCharges.parent_id == target_parent_id,
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        )
        total_charges = (await self.db.execute(charges_stmt)).scalar() or Decimal(0)

        # 2. Payments from this parent
        payments_stmt = select(func.sum(db_models.PaymentLogs.amount_paid)).filter(
            db_models.PaymentLogs.parent_id == target_parent_id,
            db_models.PaymentLogs.teacher_id == teacher_id,
            db_models.PaymentLogs.status == LogStatusEnum.ACTIVE.value
        )
        total_payments = (await self.db.execute(payments_stmt)).scalar() or Decimal(0)

        balance = total_payments - total_charges
        total_owed = Decimal(0)
        total_credit = Decimal(0)

        if balance < 0:
            total_owed = -balance
        else:
            total_credit = balance

        # 3. Lessons this month (for this parent's students)
        month_count_stmt = select(func.count(db_models.TuitionLogs.id.distinct())).join(
            db_models.TuitionLogCharges
        ).filter(
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogCharges.parent_id == target_parent_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value,
            db_models.TuitionLogs.start_time >= func.date_trunc('month', func.now()),
            db_models.TuitionLogs.start_time < (func.date_trunc('month', func.now()) + text("interval '1 month'"))
        )
        lessons_this_month = (await self.db.execute(month_count_stmt)).scalar() or 0

        # 4. Calculate Unpaid Lessons for this Parent
        ledger = await self.tuition_log_service._calculate_teacher_ledger(teacher_id)
        
        # We need all (log_id, student_id) pairs for this parent
        log_charges_stmt = select(
            db_models.TuitionLogCharges.tuition_log_id,
            db_models.TuitionLogCharges.student_id
        ).join(db_models.TuitionLogs).filter(
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogCharges.parent_id == target_parent_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        )
        log_charges = (await self.db.execute(log_charges_stmt)).all()
        
        unpaid_log_ids = set()
        for log_id, student_id in log_charges:
             if ledger.get((log_id, student_id), PaidStatus.UNPAID) == PaidStatus.UNPAID:
                 unpaid_log_ids.add(log_id)

        unpaid_lessons_count = len(unpaid_log_ids)

        return finance_models.FinancialSummaryForTeacher(
            total_owed_to_teacher=total_owed,
            total_credit_held=total_credit,
            total_lessons_given_this_month=lessons_this_month,
            unpaid_lessons_count=unpaid_lessons_count
        )

    async def _get_summary_for_teacher_for_specific_student(self, teacher_id: UUID, target_student_id: UUID) -> finance_models.FinancialSummaryForTeacher:
        """
        Calculates summary for a teacher specific to ONE student.
        Note: Payments are not linked to students. Credit balance is 0.
        Total Owed is sum of cost of unpaid logs.
        """
        # 1. Use Ledger to determine unpaid logs for this student
        ledger = await self.tuition_log_service._calculate_teacher_ledger(teacher_id)
        
        logs_stmt = select(
            db_models.TuitionLogs.id,
            db_models.TuitionLogCharges.cost,
            db_models.TuitionLogCharges.parent_id
        ).join(
            db_models.TuitionLogs,
            db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
        ).filter(
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogCharges.student_id == target_student_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        )
        
        logs_res = await self.db.execute(logs_stmt)
        rows = logs_res.all() # [(log_id, cost, parent_id), ...]

        total_unpaid_cost = Decimal(0)
        unpaid_lessons_count = 0

        for log_id, cost, pid in rows:
            status = ledger.get((log_id, target_student_id), PaidStatus.UNPAID)
            if status == PaidStatus.UNPAID:
                total_unpaid_cost += cost
                unpaid_lessons_count += 1
        
        # 2. Lessons this month for this student
        month_count_stmt = select(func.count(db_models.TuitionLogs.id)).join(
            db_models.TuitionLogCharges
        ).filter(
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogCharges.student_id == target_student_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value,
            db_models.TuitionLogs.start_time >= func.date_trunc('month', func.now()),
            db_models.TuitionLogs.start_time < (func.date_trunc('month', func.now()) + text("interval '1 month'"))
        )
        lessons_this_month = (await self.db.execute(month_count_stmt)).scalar() or 0

        return finance_models.FinancialSummaryForTeacher(
            total_owed_to_teacher=total_unpaid_cost,
            total_credit_held=Decimal(0),
            total_lessons_given_this_month=lessons_this_month,
            unpaid_lessons_count=unpaid_lessons_count
        )



