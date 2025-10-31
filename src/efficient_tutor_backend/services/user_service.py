'''

'''
from typing import Optional, Annotated
from uuid import UUID
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from ..database.engine import get_db_session
from ..database import models as db_models
from ..database.db_enums import UserRole
from ..common.logger import log

class UserService:
    """
    Base service for user-related database operations, handling the 'Users' table
    and providing methods to fetch full, polymorphic user objects.
    """
    def __init__(self, db: Annotated[AsyncSession, Depends(get_db_session)]):
        self.db = db

    async def get_full_user_by_email(self, email: str) -> db_models.Users | None:
        """
        Fetches the complete user object (Parent, Student, or Teacher)
        by their email.
        
        This uses SQLAlchemy's joinedload to fetch the base 'Users'
        record and the data from the specific role table (e.g., 'parents')
        in a single, efficient query.
        """
        log.info(f"Fetching full user profile for email: {email}")
        try:
            # 1. Fetch the base user. SQLAlchemy's polymorphic setup
            # will automatically return the correct (Parent, Student, Teacher)
            # subclass with its direct attributes (e.g., .currency, .cost).
            stmt = select(db_models.Users).filter(db_models.Users.email == email)
            
            result = await self.db.execute(stmt)
            user = result.scalars().first()
            
            # 2. If the user is a student, we must also fetch their parent.
            # This is a fast, targeted 1+1 query.
            if user and user.role == UserRole.STUDENT.value:
                # We use selectinload on the *relationship name* ('parent')
                await self.db.refresh(user, ['parent'])
                
            return user
        except Exception as e:
            log.error(f"Database error fetching full user by email {email}: {e}", exc_info=True)
            raise

    async def get_user_by_id(self, user_id: UUID) -> db_models.Users | None:
        """
        Fetches the complete user object (Parent, Student, or Teacher) by ID.
        """
        log.info(f"Fetching full user profile for ID: {user_id}")
        try:
            stmt = select(db_models.Users).options(
                joinedload('*')
            ).filter(db_models.Users.id == user_id)
            
            result = await self.db.execute(stmt)
            user = result.scalars().first()
            
            if user:
                if user.role == UserRole.STUDENT.value:
                    await self.db.refresh(user, ['parent'])
            
            return user
        except Exception as e:
            log.error(f"Database error fetching full user by ID {user_id}: {e}", exc_info=True)
            raise

    async def get_users_by_ids(self, user_ids: list[UUID]) -> list[db_models.Users]:
        """
        Fetches a list of complete user objects (Parent, Student, or Teacher)
        by a list of IDs.
        """
        if not user_ids:
            return []
        log.info(f"Fetching {len(user_ids)} full user profiles by ID list.")
        try:
            stmt = select(db_models.Users).options(
                joinedload('*')
            ).filter(db_models.Users.id.in_(user_ids))
            
            result = await self.db.execute(stmt)
            users = result.scalars().all()
            
            # Eagerly load parents for all students in the list
            for user in users:
                if user.role == UserRole.STUDENT.value:
                    await self.db.refresh(user, ['parent'])
                    
            return list(users)
        except Exception as e:
            log.error(f"Database error fetching full users by ID list: {e}", exc_info=True)
            raise

    async def _get_user_by_email_with_password(self, email: str) -> db_models.Users | None:
        """
        NEW: Fetches the base user object including the password hash.
        This is for internal authentication use ONLY.
        It does NOT fetch the full polymorphic object.
        """
        log.info(f"Fetching user with password for auth: {email}")
        try:
            # This is a simple query for the base Users table
            stmt = select(db_models.Users).filter(db_models.Users.email == email)
            result = await self.db.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            log.error(f"Database error fetching user with password for {email}: {e}", exc_info=True)
            raise

class ParentService(UserService):
    """
    Service for parent-specific logic.
    Inherits common user methods from UserService.
    """
    
    async def get_all(self, current_user: db_models.Users) -> list[db_models.Parents]:
        """
        Fetches a list of Parent objects.
        This action is restricted to TEACHERS only.
        
        - If the viewer is a Teacher, returns all parents they are linked to.
        - If the viewer is a Parent or Student, raises a 403 Forbidden error.
        """
        log.info(f"Attempting to get parent list for user {current_user.id} (Role: {current_user.role}).")
        
        # 1. Authorization Check: Enforce the business rule
        if current_user.role != UserRole.TEACHER.value:
            log.warning(f"Unauthorized attempt to list parents by user {current_user.id} (Role: {current_user.role}).")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this list. Only teachers can list parents."
            )
        
        # 2. Existing Logic: Now executes only if the user is a teacher
        teacher_id = current_user.id
        log.info(f"Fetching parent list for teacher {teacher_id}.")
        try:
            # Use a subquery to find all parent IDs linked to the teacher
            # via tuition logs.
            subquery = select(db_models.TuitionLogCharges.parent_id).distinct().join(
                db_models.TuitionLogs, 
                db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
            ).filter(db_models.TuitionLogs.teacher_id == teacher_id)
            
            # Main query to fetch the full Parent objects
            stmt = select(db_models.Parents).filter(
                db_models.Parents.id.in_(subquery)
            ).order_by(db_models.Parents.first_name)
            
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        
        except Exception as e:
            log.error(f"Database error fetching parents for teacher {teacher_id}: {e}", exc_info=True)
            # Re-raise the exception to be handled by the main error handler
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
            if current_user.role == UserRole.PARENT.value:
                # We can use the relationship on the Parent object
                await self.db.refresh(current_user, ['students'])
                return current_user.students
            
            elif current_user.role == UserRole.TEACHER.value:
                # Find all student IDs linked to the teacher via logs
                subquery = select(db_models.TuitionLogCharges.student_id).distinct().join(
                    db_models.TuitionLogs, 
                    db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
                ).filter(db_models.TuitionLogs.teacher_id == current_user.id)
                
                # Fetch the full Student objects
                stmt = select(db_models.Students).options(
                    joinedload(db_models.Students.parent) # Eager load the parent
                ).filter(
                    db_models.Students.id.in_(subquery)
                ).order_by(db_models.Students.first_name)
                
                result = await self.db.execute(stmt)
                return list(result.scalars().all())
            
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to view this list. Only teachers can list parents."
                )
        except Exception as e:
            log.error(f"Database error fetching all students for user {current_user.id}: {e}", exc_info=True)
            raise

class TeachersService(UserService):
    """Service for teacher-specific logic."""
    pass
