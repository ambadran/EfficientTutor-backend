'''

'''
from typing import Optional, Annotated, Dict
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from fastapi import Depends, HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database.engine import get_db_session
from ..database import models as db_models
from ..database.db_enums import UserRole, LogStatusEnum, TuitionLogCreateTypeEnum, PaidStatus
from ..models import finance as finance_models
from ..common.logger import log
from ..common.config import settings
from .user_service import UserService
from .tuition_service import TuitionsService

# --- Service 1: Tuition Log Management ---

class TuitionLogService:
    """Service for creating, reading, and managing tuition logs."""
    
    def __init__(
        self, 
        db: Annotated[AsyncSession, Depends(get_db_session)],
        user_service: Annotated[UserService, Depends(UserService)],
        tuitions_service: Annotated[TuitionsService, Depends(TuitionsService)]
    ):
        self.db = db
        self.user_service = user_service
        self.tuitions_service = tuitions_service

    async def get_tuition_log_by_id(self, log_id: UUID) -> db_models.TuitionLogs:
        """Fetches a single, fully-loaded tuition log by its ID."""
        log.info(f"Fetching tuition log by ID: {log_id}")
        stmt = select(db_models.TuitionLogs).options(
            selectinload(db_models.TuitionLogs.teacher),
            selectinload(db_models.TuitionLogs.tuition),
            selectinload(db_models.TuitionLogs.tuition_log_charges).options(
                selectinload(db_models.TuitionLogCharges.student).joinedload('*'),
                selectinload(db_models.TuitionLogCharges.parent).joinedload('*')
            )
        ).filter(db_models.TuitionLogs.id == log_id)
        
        result = await self.db.execute(stmt)
        log_obj = result.scalars().first()
        if not log_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tuition log not found.")
        return log_obj

    async def get_all_tuition_logs(self, current_user: db_models.Users, include_void: bool = False) -> list[db_models.TuitionLogs]:
        """Fetches all tuition logs relevant to the current user, fully loaded."""
        log.info(f"Fetching all tuition logs for user {current_user.id}")
        
        # Base query with all relationships eager-loaded
        stmt = select(db_models.TuitionLogs).options(
            selectinload(db_models.TuitionLogs.teacher),
            selectinload(db_models.TuitionLogs.tuition),
            selectinload(db_models.TuitionLogs.tuition_log_charges).options(
                selectinload(db_models.TuitionLogCharges.student).joinedload('*'),
                selectinload(db_models.TuitionLogCharges.parent).joinedload('*')
            )
        )
        
        # Add role-based filtering
        if current_user.role == UserRole.TEACHER.value:
            stmt = stmt.filter(db_models.TuitionLogs.teacher_id == current_user.id)
        elif current_user.role == UserRole.PARENT.value:
            subquery = select(db_models.TuitionLogCharges.tuition_log_id).distinct().filter(
                db_models.TuitionLogCharges.parent_id == current_user.id
            )
            stmt = stmt.filter(db_models.TuitionLogs.id.in_(subquery))
        elif current_user.role == UserRole.STUDENT.value:
            subquery = select(db_models.TuitionLogCharges.tuition_log_id).distinct().filter(
                db_models.TuitionLogCharges.student_id == current_user.id
            )
            stmt = stmt.filter(db_models.TuitionLogs.id.in_(subquery))
        else:
            return [] # Admins or other roles see no logs by default

        # Filter out VOID logs unless explicitly requested
        if not include_void:
            stmt = stmt.filter(db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value)
            
        stmt = stmt.order_by(db_models.TuitionLogs.start_time.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_tuition_log(self, log_data: finance_models.TuitionLogCreate, current_user: db_models.Users, corrected_from_log_id: Optional[UUID] = None) -> db_models.TuitionLogs:
        """Dispatcher method to create a new tuition log."""
        if log_data.log_type == TuitionLogCreateTypeEnum.SCHEDULED:
            return await self._create_from_scheduled(log_data, current_user, corrected_from_log_id)
        elif log_data.log_type == TuitionLogCreateTypeEnum.CUSTOM:
            return await self._create_from_custom(log_data, current_user, corrected_from_log_id)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid log_type.")

    async def _create_from_scheduled(self, data: finance_models.TuitionLogCreate, current_user: db_models.Users, corrected_from: Optional[UUID]) -> db_models.TuitionLogs:
        log.info(f"Creating SCHEDULED log from tuition ID {data.tuition_id}")
        tuition = await self.tuitions_service.get_tuition_by_id(data.tuition_id)
        if not tuition:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tuition template not found.")
        
        # Create the new log object
        new_log = db_models.TuitionLogs(
            teacher_id=tuition.teacher_id,
            subject=tuition.subject,
            start_time=data.start_time,
            end_time=data.end_time,
            create_type=TuitionLogCreateTypeEnum.SCHEDULED.value,
            tuition_id=tuition.id,
            lesson_index=tuition.lesson_index,
            corrected_from_log_id=corrected_from
        )
        self.db.add(new_log)
        
        # Copy charges from the template
        new_charges = [
            db_models.TuitionLogCharges(
                tuition_log=new_log,
                student_id=charge.student_id,
                parent_id=charge.parent_id,
                cost=charge.cost
            ) for charge in tuition.tuition_template_charges
        ]
        self.db.add_all(new_charges)
        
        await self.db.flush() # Flush to get the new_log.id before returning
        await self.db.refresh(new_log, ['teacher', 'tuition', 'tuition_log_charges'])
        return new_log

    async def _create_from_custom(self, data: finance_models.TuitionLogCreate, current_user: db_models.Users, corrected_from: Optional[UUID]) -> db_models.TuitionLogs:
        log.info(f"Creating CUSTOM log from user {current_user.id}")
        
        # Get all required student objects in one query
        student_ids = [charge.student_id for charge in data.charges]
        students = await self.user_service.get_users_by_ids(student_ids)
        students_dict = {user.id: user for user in students if user.role == UserRole.STUDENT.value}

        if len(students_dict) != len(student_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more students not found.")
            
        new_log = db_models.TuitionLogs(
            teacher_id=data.teacher_id,
            subject=data.subject,
            start_time=data.start_time,
            end_time=data.end_time,
            create_type=TuitionLogCreateTypeEnum.CUSTOM.value,
            lesson_index=data.lesson_index,
            corrected_from_log_id=corrected_from
        )
        self.db.add(new_log)
        
        new_charges = []
        for charge_input in data.charges:
            student = students_dict.get(charge_input.student_id)
            new_charges.append(db_models.TuitionLogCharges(
                tuition_log=new_log,
                student_id=student.id,
                parent_id=student.parent_id, # Fetched via the student object
                cost=charge_input.cost
            ))
        self.db.add_all(new_charges)

        await self.db.flush()
        await self.db.refresh(new_log, ['teacher', 'tuition_log_charges'])
        return new_log

    async def void_tuition_log(self, log_id: UUID, current_user: db_models.Users) -> bool:
        """'Deletes' a tuition log by setting its status to VOID."""
        log.info(f"Voiding tuition log {log_id} by user {current_user.id}")
        log_obj = await self.get_tuition_log_by_id(log_id)
        # TODO: Add ownership check (e.g., if user is the teacher of the log)
        log_obj.status = LogStatusEnum.VOID.value
        self.db.add(log_obj)
        return True

    async def correct_tuition_log(self, old_log_id: UUID, log_data: finance_models.TuitionLogCreate, current_user: db_models.Users) -> db_models.TuitionLogs:
        """Edits a log by voiding the old one and creating a new one."""
        log.info(f"Correcting tuition log {old_log_id} by user {current_user.id}")
        await self.void_tuition_log(old_log_id, current_user)
        new_log = await self.create_tuition_log(log_data, current_user, corrected_from_log_id=old_log_id)
        return new_log

    async def _get_earliest_log_date(self) -> datetime:
        """Fetches the earliest log start time for week number calculations."""
        result = await self.db.execute(
            select(func.min(db_models.TuitionLogs.start_time)).filter(
                db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
            )
        )
        return result.scalars().first() or datetime.now()

    async def get_all_tuition_logs_for_api(self, current_user: db_models.Users) -> list[finance_models.TuitionLogReadForTeacher | finance_models.TuitionLogReadForGuardian]:
        """Dispatcher to fetch and format tuition logs for the API."""
        rich_logs = await self.get_all_tuition_logs(current_user)
        if not rich_logs:
            return []
            
        earliest_date = await self._get_earliest_log_date()
        
        if current_user.role == UserRole.TEACHER.value:
            parent_ids = {charge.parent_id for log in rich_logs for charge in log.tuition_log_charges}
            paid_statuses = await self._get_paid_statuses_for_parents(list(parent_ids))
            return [self._format_for_teacher_api(log, earliest_date, paid_statuses) for log in rich_logs]
        else: # Parent or Student
            parent_id = current_user.id if current_user.role == UserRole.PARENT.value else current_user.parent_id
            paid_statuses = await self._get_paid_statuses_for_parents([parent_id])
            return [self._format_for_guardian_api(log, earliest_date, paid_statuses, current_user.id) for log in rich_logs]

    def _format_for_teacher_api(self, log: db_models.TuitionLogs, earliest_date: datetime, statuses: Dict) -> finance_models.TuitionLogReadForTeacher:
        """Formats a single log for a teacher's view."""
        return finance_models.TuitionLogReadForTeacher(
            id=log.id,
            subject=log.subject,
            start_time=log.start_time,
            end_time=log.end_time,
            status=log.status,
            create_type=log.create_type,
            tuition_id=log.tuition_id,
            lesson_index=log.lesson_index,
            corrected_from_log_id=log.corrected_from_log_id,
            paid_status=statuses.get(log.tuition_log_charges[0].parent_id, PaidStatus.UNPAID),
            charges=[finance_models.LogChargeRead(
                student_id=c.student.id,
                student_name=f"{c.student.first_name or ''} {c.student.last_name or ''}".strip(),
                cost=c.cost
            ) for c in log.tuition_log_charges],
            _earliest_log_date=earliest_date
        )
    
    def _format_for_guardian_api(self, log: db_models.TuitionLogs, earliest_date: datetime, statuses: Dict, viewer_id: UUID) -> finance_models.TuitionLogReadForGuardian:
        """Formats a single log for a guardian's view."""
        my_charge = Decimal(0)
        for c in log.tuition_log_charges:
            if c.parent_id == viewer_id or c.student_id == viewer_id:
                my_charge = c.cost
                break
                
        return finance_models.TuitionLogReadForGuardian(
            id=log.id,
            subject=log.subject,
            start_time=log.start_time,
            end_time=log.end_time,
            status=log.status,
            create_type=log.create_type,
            tuition_id=log.tuition_id,
            lesson_index=log.lesson_index,
            corrected_from_log_id=log.corrected_from_log_id,
            paid_status=statuses.get(log.tuition_log_charges[0].parent_id, PaidStatus.UNPAID),
            cost=my_charge,
            attendee_names=[
                f"{c.student.first_name or ''} {c.student.last_name or ''}".strip()
                for c in log.tuition_log_charges
            ],
            _earliest_log_date=earliest_date
        )

    async def _get_paid_statuses_for_parents(self, parent_ids: list[UUID]) -> Dict[UUID, PaidStatus]:
        """Performs the FIFO paid status calculation for a list of parents."""
        if not parent_ids:
            return {}
            
        # 1. Get total payments for all parents
        payment_stmt = select(
            db_models.PaymentLogs.parent_id,
            func.sum(db_models.PaymentLogs.amount_paid)
        ).filter(
            db_models.PaymentLogs.parent_id.in_(parent_ids),
            db_models.PaymentLogs.status == LogStatusEnum.ACTIVE.value
        ).group_by(db_models.PaymentLogs.parent_id)
        
        payment_results = await self.db.execute(payment_stmt)
        parent_credits = {row.parent_id: row[1] for row in payment_results}
        
        # 2. Get all ACTIVE logs for these parents, sorted OLD-to-NEW
        log_stmt = select(db_models.TuitionLogs).options(
            selectinload(db_models.TuitionLogs.tuition_log_charges)
        ).join(db_models.TuitionLogCharges).filter(
            db_models.TuitionLogCharges.parent_id.in_(parent_ids),
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
        ).order_by(db_models.TuitionLogs.start_time.asc())
        
        log_results = await self.db.execute(log_stmt)
        logs = log_results.scalars().all()
        
        # 3. Apply FIFO logic
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

    async def get_payment_log_by_id(self, log_id: UUID) -> db_models.PaymentLogs:
        """Fetches a single, fully-loaded payment log by its ID."""
        log.info(f"Fetching payment log by ID: {log_id}")
        stmt = select(db_models.PaymentLogs).options(
            selectinload(db_models.PaymentLogs.parent).joinedload('*'),
            selectinload(db_models.PaymentLogs.teacher)
        ).filter(db_models.PaymentLogs.id == log_id)
        
        result = await self.db.execute(stmt)
        log_obj = result.scalars().first()
        if not log_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment log not found.")
        return log_obj

    async def get_all_payment_logs(self, current_user: db_models.Users) -> list[db_models.PaymentLogs]:
        """Fetches all payment logs relevant to the current user, fully loaded."""
        log.info(f"Fetching all payment logs for user {current_user.id}")
        
        stmt = select(db_models.PaymentLogs).options(
            selectinload(db_models.PaymentLogs.parent).joinedload('*'),
            selectinload(db_models.PaymentLogs.teacher)
        )
        
        if current_user.role == UserRole.TEACHER.value:
            stmt = stmt.filter(db_models.PaymentLogs.teacher_id == current_user.id)
        elif current_user.role == UserRole.PARENT.value:
            stmt = stmt.filter(db_models.PaymentLogs.parent_id == current_user.id)
        else:
            return [] # Students cannot see payment logs
            
        stmt = stmt.order_by(db_models.PaymentLogs.payment_date.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_payment_log(self, log_data: finance_models.PaymentLogCreate, current_user: db_models.Users, corrected_from_log_id: Optional[UUID] = None) -> db_models.PaymentLogs:
        """Creates a new payment log."""
        log.info(f"Creating payment log by user {current_user.id}")
        
        new_log = db_models.PaymentLogs(
            parent_id=log_data.parent_id,
            teacher_id=log_data.teacher_id,
            amount_paid=log_data.amount_paid,
            payment_date=log_data.payment_date,
            notes=log_data.notes,
            corrected_from_log_id=corrected_from_log_id
        )
        self.db.add(new_log)
        await self.db.flush()
        await self.db.refresh(new_log, ['parent', 'teacher'])
        return new_log

    async def void_payment_log(self, log_id: UUID, current_user: db_models.Users) -> bool:
        """'Deletes' a payment log by setting its status to VOID."""
        log.info(f"Voiding payment log {log_id} by user {current_user.id}")
        log_obj = await self.get_payment_log_by_id(log_id)
        # TODO: Add ownership check
        log_obj.status = LogStatusEnum.VOID.value
        self.db.add(log_obj)
        return True

    async def correct_payment_log(self, old_log_id: UUID, log_data: finance_models.PaymentLogCreate, current_user: db_models.Users) -> db_models.PaymentLogs:
        """Edits a log by voiding the old one and creating a new one."""
        log.info(f"Correcting payment log {old_log_id} by user {current_user.id}")
        await self.void_payment_log(old_log_id, current_user)
        new_log = await self.create_payment_log(log_data, current_user, corrected_from_log_id=old_log_id)
        return new_log

    async def get_all_payment_logs_for_api(self, current_user: db_models.Users) -> list[finance_models.PaymentLogRead]:
        """Fetches and formats all payment logs for the API."""
        rich_logs = await self.get_all_payment_logs(current_user)
        return [self._format_payment_log_for_api(log) for log in rich_logs]
        
    def _format_payment_log_for_api(self, log: db_models.PaymentLogs) -> finance_models.PaymentLogRead:
        """Formats a single payment log for the API."""
        parent = log.parent
        teacher = log.teacher
        return finance_models.PaymentLogRead(
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

# --- Service 3: Financial Summary ---

class FinancialSummaryService:
    """Service for calculating financial summaries."""
    
    def __init__(self, db: Annotated[AsyncSession, Depends(get_db_session)]):
        self.db = db

    async def get_financial_summary(self, current_user: db_models.Users) -> finance_models.FinancialSummaryForParent | finance_models.FinancialSummaryForTeacher:
        """Public dispatcher for financial summaries."""
        log.info(f"Generating financial summary for user {current_user.id}")
        if current_user.role == UserRole.PARENT.value:
            return await self._get_summary_for_parent(current_user.id)
        elif current_user.role == UserRole.TEACHER.value:
            return await self._get_summary_for_teacher(current_user.id)
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role not authorized for financial summaries.")

    async def _get_summary_for_parent(self, parent_id: UUID) -> finance_models.FinancialSummaryForParent:
        """Calculates and returns the financial summary for a parent."""
        
        # 1. Get total charges and total payments in parallel
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
        
        total_charges_res, total_payments_res = await self.db.execute(charges_stmt), await self.db.execute(payments_stmt)
        total_charges = total_charges_res.scalar()
        total_payments = total_payments_res.scalar()
        
        balance = total_payments - total_charges
        total_due = max(Decimal(0), -balance)
        credit_balance = max(Decimal(0), balance)
        
        # 3. Get unpaid count
        unpaid_count = 0
        if total_due > 0:
            count_stmt = select(func.count(db_models.TuitionLogs.id.distinct())).join(
                db_models.TuitionLogCharges, 
                db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
            ).filter(
                db_models.TuitionLogCharges.parent_id == parent_id,
                db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value
            )
            unpaid_count_res = await self.db.execute(count_stmt)
            unpaid_count = unpaid_count_res.scalar()
            
        return finance_models.FinancialSummaryForParent(
            total_due=total_due,
            credit_balance=credit_balance,
            unpaid_count=unpaid_count
        )

    async def _get_summary_for_teacher(self, teacher_id: UUID) -> finance_models.FinancialSummaryForTeacher:
        """Calculates and returns the financial summary for a teacher."""
        
        # 1. Get per-parent balances
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
        
        parent_balances = (await self.db.execute(balance_stmt)).all()
        
        total_owed_to_teacher = Decimal(0)
        total_credit_held = Decimal(0)
        for row in parent_balances:
            if row.balance < 0:
                total_owed_to_teacher += -row.balance
            elif row.balance > 0:
                total_credit_held += row.balance
        
        # 2. Get lessons this month
        month_count_stmt = select(func.count(db_models.TuitionLogs.id)).filter(
            db_models.TuitionLogs.teacher_id == teacher_id,
            db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value,
            db_models.TuitionLogs.start_time >= func.date_trunc('month', func.now()),
            db_models.TuitionLogs.start_time < (func.date_trunc('month', func.now()) + func.interval('1 month'))
        )
        lessons_this_month = (await self.db.execute(month_count_stmt)).scalar()

        return finance_models.FinancialSummaryForTeacher(
            total_owed_to_teacher=total_owed_to_teacher,
            total_credit_held=total_credit_held,
            total_lessons_given_this_month=lessons_this_month
        )
