'''

'''
import secrets
from typing import Optional, Annotated, List
import uuid # Added this import
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database.engine import get_db_session
from ..database import models as db_models
from ..database.db_enums import UserRole
from ..common.logger import log
from ..models import user as user_models
from ..common.security_utils import HashedPassword

# ... (UserService class remains unchanged) ...
class UserService:
    """
    Base service for user-related database operations.
    """
    def __init__(self, db: Annotated[AsyncSession, Depends(get_db_session)]):
        self.db = db

    async def get_user_by_email(self, email: str) -> db_models.Users | None:
        """
        Fetches the complete polymorphic user object
        (Parent, Student, or Teacher) by their email using an explicit two-step query.
        """
        log.info(f"Fetching full user profile for email: {email}")
        try:
            # 1. Fetch the base user to determine their role.
            base_stmt = select(db_models.Users).filter(db_models.Users.email == email)
            base_result = await self.db.execute(base_stmt)
            base_user = base_result.scalars().first()

            if not base_user:
                return None

            # 2. Based on the role, fetch the full, specific subclass.
            if base_user.role == UserRole.PARENT.value:
                stmt = select(db_models.Parents).options(
                    selectinload(db_models.Parents.students) # EAGER LOAD STUDENTS
                ).filter(db_models.Parents.id == base_user.id)
            elif base_user.role == UserRole.STUDENT.value:
                stmt = select(db_models.Students).options(
                    selectinload(db_models.Students.parent), # EAGER LOAD PARENT
                    selectinload(db_models.Students.student_subjects).selectinload(db_models.StudentSubjects.shared_with_student),
                    selectinload(db_models.Students.student_availability_intervals)
                ).filter(db_models.Students.id == base_user.id)
            elif base_user.role == UserRole.TEACHER.value:
                stmt = select(db_models.Teachers).filter(db_models.Teachers.id == base_user.id)
            else: # Admin or other role
                return base_user # Return the base object

            result = await self.db.execute(stmt)
            return result.scalars().first()

        except Exception as e:
            log.error(f"Database error fetching full user by email {email}: {e}", exc_info=True)
            raise

    async def get_user_by_id(self, user_id: UUID) -> db_models.Users | None:
        """
        Fetches the complete polymorphic user object by ID,
        eager-loading essential relationships.
        """
        log.info(f"Fetching full user profile for ID: {user_id}")
        try:
            # 1. Fetch base user role
            base_stmt = select(db_models.Users).filter(db_models.Users.id == user_id)
            base_result = await self.db.execute(base_stmt)
            base_user = base_result.scalars().first()

            if not base_user:
                return None
            
            # 2. Fetch the specific polymorphic object with relationships
            if base_user.role == UserRole.PARENT.value:
                stmt = select(db_models.Parents).options(
                    selectinload(db_models.Parents.students) # EAGER LOAD STUDENTS
                ).filter(db_models.Parents.id == base_user.id)
            elif base_user.role == UserRole.STUDENT.value:
                stmt = select(db_models.Students).options(
                    selectinload(db_models.Students.parent), # EAGER LOAD PARENT
                    selectinload(db_models.Students.student_subjects).selectinload(db_models.StudentSubjects.shared_with_student),
                    selectinload(db_models.Students.student_availability_intervals)
                ).filter(db_models.Students.id == base_user.id)
            elif base_user.role == UserRole.TEACHER.value:
                stmt = select(db_models.Teachers).filter(db_models.Teachers.id == base_user.id)
            else:
                return base_user

            result = await self.db.execute(stmt)
            return result.scalars().first()

        except Exception as e:
            log.error(f"Database error fetching full user by ID {user_id}: {e}", exc_info=True)
            raise

    async def get_users_by_ids(self, user_ids: list[UUID]) -> list[db_models.Users]:
        """
        Fetches a list of complete polymorphic user objects
        by a list of IDs in an efficient, role-batched way.
        """
        if not user_ids:
            return []
        log.info(f"Fetching {len(user_ids)} full user profiles by ID list.")
        try:
            # 1. Fetch all base users
            base_stmt = select(db_models.Users).filter(db_models.Users.id.in_(user_ids))
            base_result = await self.db.execute(base_stmt)
            base_users = base_result.scalars().all()
            
            # 2. Group IDs by role
            role_map = {
                UserRole.PARENT.value: [], UserRole.STUDENT.value: [],
                UserRole.TEACHER.value: [], UserRole.ADMIN.value: []
            }
            for user in base_users:
                role_map.get(user.role, []).append(user.id)

            final_users = []

            # 3. Run one efficient query per role, eager-loading relationships
            if role_map[UserRole.PARENT.value]:
                stmt = select(db_models.Parents).options(
                    selectinload(db_models.Parents.students) # EAGER LOAD STUDENTS
                ).filter(db_models.Parents.id.in_(role_map[UserRole.PARENT.value]))
                final_users.extend((await self.db.execute(stmt)).scalars().all())

            if role_map[UserRole.STUDENT.value]:
                stmt = select(db_models.Students).options(
                    selectinload(db_models.Students.parent), # EAGER LOAD PARENT
                    selectinload(db_models.Students.student_subjects).selectinload(db_models.StudentSubjects.shared_with_student),
                    selectinload(db_models.Students.student_availability_intervals)
                ).filter(db_models.Students.id.in_(role_map[UserRole.STUDENT.value]))
                final_users.extend((await self.db.execute(stmt)).scalars().all())

            if role_map[UserRole.TEACHER.value]:
                stmt = select(db_models.Teachers).filter(db_models.Teachers.id.in_(role_map[UserRole.TEACHER.value]))
                final_users.extend((await self.db.execute(stmt)).scalars().all())

            if role_map[UserRole.ADMIN.value]:
                stmt = select(db_models.Users).filter(db_models.Users.id.in_(role_map[UserRole.ADMIN.value]))
                final_users.extend((await self.db.execute(stmt)).scalars().all())
                
            return final_users
            
        except Exception as e:
            log.error(f"Database error fetching full users by ID list: {e}", exc_info=True)
            raise

    async def _get_user_by_email_with_password(self, email: str) -> db_models.Users | None:
        """ Fetches the base user object including the password hash. """
        log.info(f"Fetching user with password for auth: {email}")
        try:
            stmt = select(db_models.Users).filter(db_models.Users.email == email)
            result = await self.db.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            log.error(f"Database error fetching user with password for {email}: {e}", exc_info=True)
            raise

class ParentService(UserService):
    """Service for parent-specific logic."""
    
    async def get_all(self, current_user: db_models.Users) -> list[db_models.Parents]:
        """
        Fetches a list of Parent objects.
        This action is restricted to TEACHERS only.
        """
        log.info(f"Attempting to get parent list for user {current_user.id} (Role: {current_user.role}).")
        
        try:
            # 1. Authorization check now happens INSIDE the try block.
            if current_user.role != UserRole.TEACHER.value:
                log.warning(f"Unauthorized attempt to list parents by user {current_user.id} (Role: {current_user.role}).")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to view this list. Only teachers can list parents."
                )
            
            teacher_id = current_user.id
            log.info(f"Fetching parent list for teacher {teacher_id}.")
            
            # 2. Database logic
            subquery = select(db_models.TuitionLogCharges.parent_id).distinct().join(
                db_models.TuitionLogs, 
                db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
            ).filter(db_models.TuitionLogs.teacher_id == teacher_id)
            
            stmt = select(db_models.Parents).filter(
                db_models.Parents.id.in_(subquery)
            ).order_by(db_models.Parents.first_name)
            
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        
        # 3. CORRECTED: Catch HTTPException and re-raise it immediately.
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            # 4. This now only catches actual database/unexpected errors.
            log.error(f"Database error fetching parents for teacher {current_user.id}: {e}", exc_info=True)
            raise

class StudentService(UserService):
    """Service for student-specific logic."""

    async def get_all(self, current_user: db_models.Users) -> list[db_models.Students]:
        """
        Fetches all students relevant to the current user:
        - If user is a Parent, returns their children.
        - If user is a Teacher, returns all students they have taught.
        """
        log.info(f"Fetching all students for user {current_user.id} (Role: {current_user.role}).")
        
        try:
            # 1. Authorization and logic branching
            if current_user.role == UserRole.PARENT.value:
                await self.db.refresh(current_user, ['students'])
                return current_user.students
            
            elif current_user.role == UserRole.TEACHER.value:
                subquery = select(db_models.TuitionLogCharges.student_id).distinct().join(
                    db_models.TuitionLogs, 
                    db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
                ).filter(db_models.TuitionLogs.teacher_id == current_user.id)
                
                stmt = select(db_models.Students).options(
                    selectinload(db_models.Students.parent), # Eager load the parent
                    selectinload(db_models.Students.student_subjects).selectinload(db_models.StudentSubjects.shared_with_student),
                    selectinload(db_models.Students.student_availability_intervals)
                ).filter(
                    db_models.Students.id.in_(subquery)
                ).order_by(db_models.Students.first_name)
                
                result = await self.db.execute(stmt)
                return list(result.scalars().all())
            
            else:
                log.warning(f"User {current_user.id} with role {current_user.role} is not authorized to list students.")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User with role '{current_user.role}' is not authorized to list students."
                )
        
        # 2. CORRECTED: Catch HTTPException and re-raise it immediately.
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            # 3. This now only catches database/unexpected errors.
            log.error(f"Database error fetching all students for user {current_user.id}: {e}", exc_info=True)
            raise

    async def create_student(
        self,
        student_data: user_models.StudentCreate,
        current_user: db_models.Users
    ) -> user_models.StudentRead:
        """
        Creates a new student user.
        - Authorized for Teachers and Parents.
        - Auto-generates a password.
        - Creates all related subject and availability records.
        """
        log.info(f"User {current_user.id} attempting to create student {student_data.email}.")

        # 1. Authorization
        if current_user.role not in [UserRole.TEACHER.value, UserRole.PARENT.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create a student."
            )

        # 2. Check for existing user
        existing_user = await self.get_user_by_email(student_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered."
            )

        # 3. Validate parent
        parent = await self.get_user_by_id(student_data.parent_id)
        if not parent or parent.role != UserRole.PARENT.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent with id {student_data.parent_id} not found."
            )

        # 4. Generate password
        plain_password = secrets.token_urlsafe(6) # 8 characters
        hashed_password = HashedPassword.get_hash(plain_password)

        # 5. Create the Student ORM object
        new_student = db_models.Students(
            id=uuid.uuid4(), # Explicitly generate UUID for the primary key
            email=student_data.email,
            password=hashed_password,
            first_name=student_data.first_name,
            last_name=student_data.last_name,
            timezone=student_data.timezone,
            role=UserRole.STUDENT.value, # Hardcode role
            parent_id=student_data.parent_id,
            cost=student_data.cost,
            status=student_data.status.value,
            min_duration_mins=student_data.min_duration_mins,
            max_duration_mins=student_data.max_duration_mins,
            grade=student_data.grade,
            generated_password=plain_password # Store plain text password
        )

        # 6. Create related objects
        # Availability Intervals
        for interval_data in student_data.student_availability_intervals:
            new_interval = db_models.StudentAvailabilityIntervals(
                student=new_student,
                **interval_data.model_dump()
            )
            self.db.add(new_interval)

        # Subjects and their M2M relationships
        all_shared_student_ids = {
            student_id
            for subject_data in student_data.student_subjects
            for student_id in subject_data.shared_with_student_ids
        }

        shared_students_map = {}
        if all_shared_student_ids:
            shared_students = await self.get_users_by_ids(list(all_shared_student_ids))
            shared_students_map = {user.id: user for user in shared_students}


        for subject_data in student_data.student_subjects:
            new_subject = db_models.StudentSubjects(
                student=new_student,
                subject=subject_data.subject.value,
                lessons_per_week=subject_data.lessons_per_week
            )
            # Handle M2M relationship
            for shared_student_id in subject_data.shared_with_student_ids:
                shared_student = shared_students_map.get(shared_student_id)
                if shared_student:
                    new_subject.shared_with_student.append(shared_student)
            self.db.add(new_subject)

        # 7. Add student, commit, and refresh
        self.db.add(new_student)
        await self.db.flush()
        
        # Refresh the new student to load all relationships for the response model
        await self.db.refresh(
            new_student,
            ['parent', 'student_subjects', 'student_availability_intervals']
        )
        
        # Manually construct StudentSubjectRead objects to include shared_with_student_ids
        student_subjects_read = []
        for sub in new_student.student_subjects:
            student_subjects_read.append(user_models.StudentSubjectRead(
                id=sub.id,
                subject=sub.subject,
                lessons_per_week=sub.lessons_per_week,
                shared_with_student_ids=[s.id for s in sub.shared_with_student]
            ))

        # Construct the final StudentRead model
        return user_models.StudentRead(
            id=new_student.id,
            email=new_student.email,
            role=new_student.role,
            timezone=new_student.timezone,
            first_name=new_student.first_name,
            last_name=new_student.last_name,
            is_first_sign_in=new_student.is_first_sign_in,
            parent_id=new_student.parent_id,
            cost=new_student.cost,
            status=new_student.status,
            min_duration_mins=new_student.min_duration_mins,
            max_duration_mins=new_student.max_duration_mins,
            grade=new_student.grade,
            student_subjects=student_subjects_read,
            student_availability_intervals=[
                user_models.StudentAvailabilityIntervalRead.model_validate(interval)
                for interval in new_student.student_availability_intervals
            ]
        )


class TeacherService(UserService):
    """Service for teacher-specific logic."""
    pass
