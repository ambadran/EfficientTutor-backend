'''

'''
import secrets
from typing import Optional, Annotated
import uuid # Added this import
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database.engine import get_db_session
from ..database import models as db_models
from ..database.db_enums import UserRole, LogStatusEnum, AdminPrivilegeType
from ..common.logger import log
from ..models import user as user_models
from ..common.security_utils import HashedPassword
from .geo_service import GeoService


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
                    selectinload(db_models.Students.student_subjects).options(
                        selectinload(db_models.StudentSubjects.shared_with_student),
                        selectinload(db_models.StudentSubjects.teacher)
                    ),
                    selectinload(db_models.Students.student_availability_intervals)
                ).filter(db_models.Students.id == base_user.id)
            elif base_user.role == UserRole.TEACHER.value:
                stmt = select(db_models.Teachers).options(
                    selectinload(db_models.Teachers.teacher_specialties)
                ).filter(db_models.Teachers.id == base_user.id)
            elif base_user.role == UserRole.ADMIN.value:
                stmt = select(db_models.Admins).filter(db_models.Admins.id == base_user.id)
            else: # Other role
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
                    selectinload(db_models.Students.student_subjects).options(
                        selectinload(db_models.StudentSubjects.shared_with_student),
                        selectinload(db_models.StudentSubjects.teacher)
                    ),
                    selectinload(db_models.Students.student_availability_intervals)
                ).filter(db_models.Students.id == base_user.id)
            elif base_user.role == UserRole.TEACHER.value:
                stmt = select(db_models.Teachers).options(
                    selectinload(db_models.Teachers.teacher_specialties)
                ).filter(db_models.Teachers.id == base_user.id)
            elif base_user.role == UserRole.ADMIN.value:
                stmt = select(db_models.Admins).filter(db_models.Admins.id == base_user.id)
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
                    selectinload(db_models.Students.student_subjects).options(
                        selectinload(db_models.StudentSubjects.shared_with_student),
                        selectinload(db_models.StudentSubjects.teacher)
                    ),
                    selectinload(db_models.Students.student_availability_intervals)
                ).filter(db_models.Students.id.in_(role_map[UserRole.STUDENT.value]))
                final_users.extend((await self.db.execute(stmt)).scalars().all())

            if role_map[UserRole.TEACHER.value]:
                stmt = select(db_models.Teachers).options(
                    selectinload(db_models.Teachers.teacher_specialties)
                ).filter(db_models.Teachers.id.in_(role_map[UserRole.TEACHER.value]))
                final_users.extend((await self.db.execute(stmt)).scalars().all())

            if role_map[UserRole.ADMIN.value]:
                stmt = select(db_models.Admins).filter(db_models.Admins.id.in_(role_map[UserRole.ADMIN.value]))
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
    
    def __init__(self, db: Annotated[AsyncSession, Depends(get_db_session)], geo_service: Annotated[GeoService, Depends()]):
        super().__init__(db)
        self.geo_service = geo_service

    async def create_parent(
        self,
        parent_data: user_models.ParentCreate,
        ip_address: str # Add ip_address argument
    ) -> user_models.ParentRead:
        """
        Creates a new parent user (for sign-up).
        - Checks for existing email.
        - Hashes the provided password.
        - Automatically determines timezone and currency from IP address.
        """
        log.info(f"Attempting to create parent {parent_data.email} from IP {ip_address}.")

        # 1. Check for existing user
        existing_user = await self.get_user_by_email(parent_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered."
            )

        # 2. Get timezone and currency from IP address
        location_info = await self.geo_service.get_location_info(ip_address)
        timezone = location_info["timezone"]
        currency = location_info["currency"]

        # 3. Hash password
        hashed_password = HashedPassword.get_hash(parent_data.password)

        # 4. Create the Parent ORM object
        new_parent = db_models.Parents(
            id=uuid.uuid4(), # Explicitly generate UUID for the primary key
            email=parent_data.email,
            password=hashed_password,
            first_name=parent_data.first_name,
            last_name=parent_data.last_name,
            timezone=timezone, # Use determined timezone
            role=UserRole.PARENT.value, # Hardcode role
            currency=currency # Use determined currency
        )

        # 5. Add parent, commit, and refresh
        self.db.add(new_parent)
        await self.db.flush()
        
        # Refresh the new parent to load all relationships for the response model
        await self.db.refresh(new_parent, ['students']) # Eager load students for ParentRead

        # Construct the final ParentRead model
        return user_models.ParentRead(
            id=new_parent.id,
            email=new_parent.email,
            role=new_parent.role,
            timezone=new_parent.timezone,
            first_name=new_parent.first_name,
            last_name=new_parent.last_name,
            is_first_sign_in=new_parent.is_first_sign_in,
            currency=new_parent.currency
        )

    async def update_parent(
        self,
        parent_id: UUID,
        update_data: user_models.ParentUpdate,
        current_user: db_models.Users
    ) -> user_models.ParentRead:
        """
        Updates a parent's profile.
        - Authorized for the parent themselves or any teacher.
        - Allows partial updates.
        - Hashes the password if a new one is provided.
        """
        log.info(f"User {current_user.id} attempting to update parent {parent_id}.")

        # 1. Fetch parent to update
        parent_to_update = await self.get_user_by_id(parent_id)
        if not parent_to_update or parent_to_update.role != UserRole.PARENT.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent not found."
            )

        # 2. Authorization
        is_owner = parent_to_update.id == current_user.id
        is_teacher = current_user.role == UserRole.TEACHER.value
        
        if not is_owner and not is_teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to update this profile."
            )

        # 3. Apply updates
        update_dict = update_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            if key == "password":
                if value: # Ensure password is not empty
                    setattr(parent_to_update, key, HashedPassword.get_hash(value))
            elif hasattr(parent_to_update, key):
                setattr(parent_to_update, key, value)

        self.db.add(parent_to_update)
        await self.db.flush()
        await self.db.refresh(parent_to_update)

        # 4. Return updated data using the read model
        return user_models.ParentRead.model_validate(parent_to_update)

    async def delete_parent(self, parent_id: UUID, current_user: db_models.Users) -> bool:
        """
        Deletes a parent user.
        - Authorized for the parent themselves or any teacher.
        - Fails if the parent has associated students.
        """
        log.info(f"User {current_user.id} attempting to delete parent {parent_id}.")

        # 1. Fetch parent to delete
        parent_to_delete = await self.get_user_by_id(parent_id)
        if not parent_to_delete or parent_to_delete.role != UserRole.PARENT.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent not found."
            )

        # 2. Authorization
        is_owner = parent_to_delete.id == current_user.id
        is_teacher = current_user.role == UserRole.TEACHER.value
        
        if not is_owner and not is_teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this profile."
            )

        # 3. Check for associated students
        # The get_user_by_id method eager loads students, so this check is efficient.
        if parent_to_delete.students:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete a parent with associated students. Please reassign or delete the students first."
            )

        # 4. Delete the parent
        await self.db.delete(parent_to_delete)
        await self.db.flush()
        
        log.info(f"Successfully deleted parent {parent_id}.")
        return True

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
                stmt = select(db_models.Students).options(
                    selectinload(db_models.Students.student_subjects),
                    selectinload(db_models.Students.student_availability_intervals)
                ).filter(db_models.Students.parent_id == current_user.id)
                
                result = await self.db.execute(stmt)
                return list(result.scalars().all())
            
            elif current_user.role == UserRole.TEACHER.value:
                subquery = select(db_models.TuitionLogCharges.student_id).distinct().join(
                    db_models.TuitionLogs, 
                    db_models.TuitionLogs.id == db_models.TuitionLogCharges.tuition_log_id
                ).filter(db_models.TuitionLogs.teacher_id == current_user.id)
                
                stmt = select(db_models.Students).options(
                    selectinload(db_models.Students.parent), # Eager load the parent
                    selectinload(db_models.Students.student_subjects).options(
                        selectinload(db_models.StudentSubjects.shared_with_student),
                        selectinload(db_models.StudentSubjects.teacher)
                    ),
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
        log.info(f"User {current_user.id} attempting to create student {student_data.first_name} {student_data.last_name}.")

        # 1. Authorization
        if current_user.role not in [UserRole.TEACHER.value, UserRole.PARENT.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create a student."
            )
        
        # If the current user is a parent, they can only create a student for themselves.
        if current_user.role == UserRole.PARENT.value and student_data.parent_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Parents can only create students for themselves."
            )

        # 2. Validate parent
        parent = await self.get_user_by_id(student_data.parent_id)
        if not parent or parent.role != UserRole.PARENT.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent with id {student_data.parent_id} not found."
            )

        # 3. Generate unique email
        # Using parent's email domain and a unique identifier
        parent_email_domain = parent.email.split('@')[1]
        generated_email = f"{student_data.first_name.lower()}.{student_data.last_name.lower()}.{secrets.token_hex(2)}@{parent_email_domain}"
        
        # Ensure the generated email is truly unique (highly unlikely to collide, but good practice)
        while await self.get_user_by_email(generated_email):
            generated_email = f"{student_data.first_name.lower()}.{student_data.last_name.lower()}.{secrets.token_hex(4)}@{parent_email_domain}"

        # 4. Generate password
        plain_password = secrets.token_urlsafe(6) # 8 characters
        hashed_password = HashedPassword.get_hash(plain_password)

        # 5. Create the Student ORM object
        new_student = db_models.Students(
            id=uuid.uuid4(), # Explicitly generate UUID for the primary key
            email=generated_email, # Use generated email
            password=hashed_password,
            first_name=student_data.first_name,
            last_name=student_data.last_name,
            timezone=parent.timezone, # Set timezone from parent
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

        # Subjects, M2M relationships, and Teacher validation
        all_teacher_ids = {sub.teacher_id for sub in student_data.student_subjects}
        all_shared_student_ids = {
            student_id
            for subject_data in student_data.student_subjects
            for student_id in subject_data.shared_with_student_ids
        }
        
        # Fetch all relevant users (teachers and shared students) in one go
        all_related_user_ids = list(all_teacher_ids | all_shared_student_ids)
        related_users = await self.get_users_by_ids(all_related_user_ids)
        
        # Create maps for quick lookup and validation
        teachers_map = {u.id: u for u in related_users if u.role == UserRole.TEACHER.value}
        shared_students_map = {u.id: u for u in related_users if u.role == UserRole.STUDENT.value}

        # Validate that all provided teacher_ids are valid teachers
        if len(teachers_map) != len(all_teacher_ids):
            invalid_ids = all_teacher_ids - set(teachers_map.keys())
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invalid teacher_id(s) provided: {', '.join(map(str, invalid_ids))}"
            )

        for subject_data in student_data.student_subjects:
            new_subject = db_models.StudentSubjects(
                student=new_student,
                subject=subject_data.subject.value,
                lessons_per_week=subject_data.lessons_per_week,
                teacher_id=subject_data.teacher_id,
                educational_system=subject_data.educational_system.value,
                grade=subject_data.grade
            )
            # Handle M2M relationship for shared subjects
            for shared_student_id in subject_data.shared_with_student_ids:
                shared_student = shared_students_map.get(shared_student_id)
                if shared_student:
                    new_subject.shared_with_student.append(shared_student)
            self.db.add(new_subject)

        # 7. Add student, commit, and refresh
        self.db.add(new_student)
        await self.db.flush()
        
        # Re-fetch the new student with all necessary relationships eagerly loaded
        new_student = await self.db.execute(
            select(db_models.Students)
            .options(
                selectinload(db_models.Students.parent),
                selectinload(db_models.Students.student_subjects).options(
                    selectinload(db_models.StudentSubjects.shared_with_student)
                ),
                selectinload(db_models.Students.student_availability_intervals)
            )
            .filter(db_models.Students.id == new_student.id)
        )
        new_student = new_student.scalars().first()
        if not new_student:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve newly created student.")
        
        # Manually construct StudentSubjectRead objects to include the new teacher_id
        student_subjects_read = []
        for sub in new_student.student_subjects:
            student_subjects_read.append(user_models.StudentSubjectRead(
                id=sub.id,
                subject=sub.subject,
                lessons_per_week=sub.lessons_per_week,
                teacher_id=sub.teacher_id,
                educational_system=sub.educational_system,
                grade=sub.grade,
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
            generated_password=new_student.generated_password, # Include generated password
            student_subjects=student_subjects_read,
            student_availability_intervals=[
                user_models.StudentAvailabilityIntervalRead.model_validate(interval)
                for interval in new_student.student_availability_intervals
            ]
        )

    async def update_student(
        self,
        student_id: UUID,
        update_data: user_models.StudentUpdate,
        current_user: db_models.Users
    ) -> user_models.StudentRead:
        """
        Updates an existing student user.
        - Authorized for Teachers and Parents (only their own children).
        - Allows partial updates.
        - Replaces nested subject and availability records.
        """
        log.info(f"User {current_user.id} attempting to update student {student_id}.")

        # 1. Fetch existing student and authorize
        student_to_update = await self.get_user_by_id(student_id)
        if not student_to_update or student_to_update.role != UserRole.STUDENT.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found."
            )

        if current_user.role == UserRole.TEACHER.value:
            # Teachers can update any student
            pass
        elif current_user.role == UserRole.PARENT.value:
            # Parents can only update their own children
            if student_to_update.parent_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Parents can only update their own children."
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to update students."
            )
        
        # Ensure student_to_update is fully loaded if coming from get_user_by_id
        # which might only load base student fields without relationships.
        # This is crucial for accessing relationships later for deletion/replacement
        student_to_update = await self.get_user_by_id(student_id) # Re-fetch to ensure eager loading

        # 2. Apply updates to simple fields (on Users and Students tables)
        update_dict = update_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            if key in ['email', 'first_name', 'last_name', 'timezone']:
                setattr(student_to_update, key, value)
            elif key in ['cost', 'status', 'min_duration_mins', 'max_duration_mins', 'grade', 'parent_id']:
                if key == 'status' and value is not None:
                    setattr(student_to_update, key, value.value) # Handle Enum value
                elif key == 'parent_id' and value is not None: # Validate new parent_id
                    new_parent = await self.get_user_by_id(value)
                    if not new_parent or new_parent.role != UserRole.PARENT.value:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="New parent not found or is not a parent.")
                    setattr(student_to_update, key, value)
                elif value is not None:
                    setattr(student_to_update, key, value)
                
        # 3. Handle nested list updates (delete and replace strategy)
        if update_data.student_availability_intervals is not None:
            # Delete existing intervals from DB
            await self.db.execute(
                delete(db_models.StudentAvailabilityIntervals).filter_by(student_id=student_to_update.id)
            )
            # Clear the in-memory collection and flush deletions
            student_to_update.student_availability_intervals.clear()
            await self.db.flush()

            # Create new intervals and append them
            for interval_data in update_data.student_availability_intervals:
                new_interval = db_models.StudentAvailabilityIntervals(
                    **interval_data.model_dump()
                )
                student_to_update.student_availability_intervals.append(new_interval)

        if update_data.student_subjects is not None:
            # Delete existing subjects and their M2M links from DB
            await self.db.execute(
                delete(db_models.t_student_subject_sharings).where(
                    db_models.t_student_subject_sharings.c.student_subject_id.in_(
                        select(db_models.StudentSubjects.id).where(db_models.StudentSubjects.student_id == student_to_update.id)
                    )
                )
            )
            await self.db.execute(
                delete(db_models.StudentSubjects).filter_by(student_id=student_to_update.id)
            )
            # Clear the in-memory collection and flush deletions
            student_to_update.student_subjects.clear()
            await self.db.flush()
            
            # Create new subjects, M2M relationships, and validate teachers
            all_teacher_ids = {sub.teacher_id for sub in update_data.student_subjects}
            all_shared_student_ids = {
                student_id
                for subject_data in update_data.student_subjects
                for student_id in subject_data.shared_with_student_ids
            }

            all_related_user_ids = list(all_teacher_ids | all_shared_student_ids)
            related_users = await self.get_users_by_ids(all_related_user_ids)

            teachers_map = {u.id: u for u in related_users if u.role == UserRole.TEACHER.value}
            shared_students_map = {u.id: u for u in related_users if u.role == UserRole.STUDENT.value}

            if len(teachers_map) != len(all_teacher_ids):
                invalid_ids = all_teacher_ids - set(teachers_map.keys())
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Invalid teacher_id(s) provided: {', '.join(map(str, invalid_ids))}"
                )

            for subject_data in update_data.student_subjects:
                new_subject = db_models.StudentSubjects(
                    subject=subject_data.subject.value,
                    lessons_per_week=subject_data.lessons_per_week,
                    teacher_id=subject_data.teacher_id,
                    educational_system=subject_data.educational_system.value,
                    grade=subject_data.grade
                )
                for shared_student_id in subject_data.shared_with_student_ids:
                    shared_student = shared_students_map.get(shared_student_id)
                    if shared_student:
                        new_subject.shared_with_student.append(shared_student)
                student_to_update.student_subjects.append(new_subject)

        self.db.add(student_to_update)
        await self.db.flush()

        # Re-fetch the student to get all updated relationships
        updated_student = await self.get_user_by_id(student_id)
        if not updated_student:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve updated student.")

        # Manually construct StudentSubjectRead objects to include the new teacher_id
        student_subjects_read = []
        for sub in updated_student.student_subjects:
            student_subjects_read.append(user_models.StudentSubjectRead(
                id=sub.id,
                subject=sub.subject,
                lessons_per_week=sub.lessons_per_week,
                teacher_id=sub.teacher_id,
                educational_system=sub.educational_system,
                grade=sub.grade,
                shared_with_student_ids=[s.id for s in sub.shared_with_student]
            ))

        # Construct the final StudentRead model
        return user_models.StudentRead(
            id=updated_student.id,
            email=updated_student.email,
            role=updated_student.role,
            timezone=updated_student.timezone,
            first_name=updated_student.first_name,
            last_name=updated_student.last_name,
            is_first_sign_in=updated_student.is_first_sign_in,
            parent_id=updated_student.parent_id,
            cost=updated_student.cost,
            status=updated_student.status, # ORM will return string here correctly
            min_duration_mins=updated_student.min_duration_mins,
            max_duration_mins=updated_student.max_duration_mins,
            grade=updated_student.grade,
            student_subjects=student_subjects_read,
            student_availability_intervals=[
                user_models.StudentAvailabilityIntervalRead.model_validate(interval)
                for interval in updated_student.student_availability_intervals
            ]
        )

    async def delete_student(
        self,
        student_id: UUID,
        current_user: db_models.Users
    ) -> bool:
        """
        Deletes a student user.
        - Authorized for Teachers and Parents (only their own children).
        """
        log.info(f"User {current_user.id} attempting to delete student {student_id}.")

        # 1. Fetch existing student and authorize
        student_to_delete = await self.get_user_by_id(student_id)
        if not student_to_delete or student_to_delete.role != UserRole.STUDENT.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found."
            )

        if current_user.role == UserRole.TEACHER.value:
            # Teachers can delete any student
            pass
        elif current_user.role == UserRole.PARENT.value:
            # Parents can only delete their own children
            if student_to_delete.parent_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Parents can only delete their own children."
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete students."
            )
        
        # 2. Delete the student
        await self.db.delete(student_to_delete)
        await self.db.flush()
        
        return True


class TeacherService(UserService):
    """Service for teacher-specific logic."""

    def __init__(self, db: Annotated[AsyncSession, Depends(get_db_session)], geo_service: Annotated[GeoService, Depends(GeoService)]):
        super().__init__(db)
        self.geo_service = geo_service

    async def get_all(self, current_user: db_models.Users) -> list[db_models.Teachers]:
        """
        Fetches a list of all Teacher objects.
        This action is restricted to ADMINS only.
        """
        log.info(f"User {current_user.id} attempting to get all teachers.")
        if current_user.role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this list."
            )
        
        stmt = select(db_models.Teachers).options(
            selectinload(db_models.Teachers.teacher_specialties)
        ).order_by(db_models.Teachers.first_name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_for_student_subject(self, query: user_models.TeacherSpecialtyQuery, current_user: db_models.Users) -> list[db_models.Teachers]:
        """
        Fetches a list of all Teacher objects that have a specialty matching the query.
        This action is restricted to ADMINS and PARENTS only.
        Returns ORM models directly.
        """
        log.info(f"User {current_user.id} attempting to get all teachers for subject {query.subject}.")
        if current_user.role not in [UserRole.ADMIN.value, UserRole.PARENT.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this list."
            )

        stmt = select(db_models.Teachers).join(db_models.TeacherSpecialties).filter(
            db_models.TeacherSpecialties.subject == query.subject.value,
            db_models.TeacherSpecialties.educational_system == query.educational_system.value,
            db_models.TeacherSpecialties.grade == query.grade
        ).options(selectinload(db_models.Teachers.teacher_specialties)).distinct()

        result = await self.db.execute(stmt)
        teachers = result.scalars().all()
        return teachers

    async def get_all_for_student_subject_for_api(self, query: user_models.TeacherSpecialtyQuery, current_user: db_models.Users) -> list[user_models.TeacherRead]:
        """
        API-facing method: Fetches a list of all Teacher objects that have a specialty matching the query.
        This action is restricted to ADMINS and PARENTS only.
        Returns Pydantic models for API response.
        """
        teachers_orm = await self.get_all_for_student_subject(query, current_user)
        return [user_models.TeacherRead.model_validate(teacher) for teacher in teachers_orm]

    async def get_specialties(self, teacher_id: UUID, current_user: db_models.Users) -> list[user_models.TeacherSpecialtyRead]:
        """
        Fetches the specialties for a specific teacher.
        - Authorized for the teacher themselves or an admin.
        """
        log.info(f"User {current_user.id} attempting to get specialties for teacher {teacher_id}.")

        teacher = await self.get_user_by_id(teacher_id)
        if not teacher or teacher.role != UserRole.TEACHER.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher not found."
            )

        is_owner = current_user.id == teacher_id
        is_admin = current_user.role == UserRole.ADMIN.value
        
        if not is_owner and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view these specialties."
            )

        return [user_models.TeacherSpecialtyRead.model_validate(specialty) for specialty in teacher.teacher_specialties]

    async def create_teacher(
            self,
            teacher_data: user_models.TeacherCreate,
            ip_address: str
        ) -> user_models.TeacherRead:
        """
        Creates a new teacher user (for sign-up).
        - Checks for existing email.
        - Hashes password.
        - Determines timezone and currency from IP.
        """
        log.info(f"Attempting to create teacher {teacher_data.email} from IP {ip_address}.")

        existing_user = await self.get_user_by_email(teacher_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered."
            )

        location_info = await self.geo_service.get_location_info(ip_address)
        hashed_password = HashedPassword.get_hash(teacher_data.password)

        new_teacher = db_models.Teachers(
            id=uuid.uuid4(),
            email=teacher_data.email,
            password=hashed_password,
            first_name=teacher_data.first_name,
            last_name=teacher_data.last_name,
            timezone=location_info["timezone"],
            currency=location_info["currency"],
            role=UserRole.TEACHER.value
        )
        
        # Create and associate specialty objects
        for specialty_data in teacher_data.teacher_specialties:
            new_specialty = db_models.TeacherSpecialties(
                teacher=new_teacher,
                subject=specialty_data.subject.value,
                educational_system=specialty_data.educational_system.value,
                grade=specialty_data.grade
            )
            self.db.add(new_specialty)

        self.db.add(new_teacher)
        await self.db.flush()
        
        # Refresh to load relationships, including the new specialties
        await self.db.refresh(new_teacher, ['teacher_specialties'])

        return user_models.TeacherRead.model_validate(new_teacher)

    async def update_teacher(
        self,
        teacher_id: UUID,
        update_data: user_models.TeacherUpdate,
        current_user: db_models.Users
    ) -> user_models.TeacherRead:
        """
        Updates a teacher's profile.
        - Authorized for the teacher themselves or an admin.
        """
        log.info(f"User {current_user.id} attempting to update teacher {teacher_id}.")

        is_owner = teacher_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN.value
        
        if not is_owner and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to update this profile."
            )

        teacher_to_update = await self.get_user_by_id(teacher_id)
        if not teacher_to_update or teacher_to_update.role != UserRole.TEACHER.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher not found."
            )

        update_dict = update_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            if key == "password" and value:
                setattr(teacher_to_update, key, HashedPassword.get_hash(value))
            elif hasattr(teacher_to_update, key):
                setattr(teacher_to_update, key, value)

        self.db.add(teacher_to_update)
        await self.db.flush()
        await self.db.refresh(teacher_to_update, ['teacher_specialties'])

        return user_models.TeacherRead.model_validate(teacher_to_update)

    async def delete_teacher(self, teacher_id: UUID, current_user: db_models.Users) -> bool:
        """
        Deletes a teacher user.
        - Authorized for the teacher themselves or an admin.
        - Fails if the teacher has any active tuition logs.
        """
        log.info(f"User {current_user.id} attempting to delete teacher {teacher_id}.")

        teacher_to_delete = await self.get_user_by_id(teacher_id)
        if not teacher_to_delete or teacher_to_delete.role != UserRole.TEACHER.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher not found."
            )

        is_owner = teacher_to_delete.id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN.value
        
        if not is_owner and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this profile."
            )

        # Safety check for active tuition logs
        active_logs_check = await self.db.execute(
            select(db_models.TuitionLogs.id)
            .filter(db_models.TuitionLogs.teacher_id == teacher_id)
            .filter(db_models.TuitionLogs.status == LogStatusEnum.ACTIVE.value)
            .limit(1)
        )
        if active_logs_check.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete a teacher with active tuition logs. Please void or reassign them first."
            )

        await self.db.delete(teacher_to_delete)
        await self.db.flush()

        # Verify the deletion
        check_user = await self.get_user_by_id(teacher_id)
        if check_user is None:
            log.info(f"Successfully deleted teacher {teacher_id}.")
            return True
        else:
            log.error(f"Failed to delete teacher {teacher_id}, record still exists after flush.")
            await self.db.rollback()
            return False

    async def add_specialty_to_teacher(
        self,
        teacher_id: UUID,
        specialty_data: user_models.TeacherSpecialtyWrite,
        current_user: db_models.Users
    ) -> user_models.TeacherRead:
        """
        Adds a new specialty to a teacher.
        - Authorized for the teacher themselves or an admin.
        - Prevents adding duplicate specialties.
        """
        log.info(f"User {current_user.id} attempting to add specialty to teacher {teacher_id}.")

        is_owner = teacher_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN.value

        if not is_owner and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this profile."
            )

        teacher = await self.get_user_by_id(teacher_id)
        if not teacher or teacher.role != UserRole.TEACHER.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher not found."
            )

        # Check if the specialty already exists
        for existing_specialty in teacher.teacher_specialties:
            if (existing_specialty.subject == specialty_data.subject.value and
                    existing_specialty.educational_system == specialty_data.educational_system.value and
                    existing_specialty.grade == specialty_data.grade):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This specialty already exists for this teacher."
                )

        # Create and add the new specialty
        new_specialty = db_models.TeacherSpecialties(
            teacher_id=teacher_id,
            subject=specialty_data.subject.value,
            educational_system=specialty_data.educational_system.value,
            grade=specialty_data.grade
        )
        self.db.add(new_specialty)
        await self.db.flush()
        await self.db.refresh(teacher, ['teacher_specialties'])

        return user_models.TeacherRead.model_validate(teacher)

    async def delete_teacher_specialty(
        self,
        teacher_id: UUID,
        specialty_id: UUID,
        current_user: db_models.Users
    ) -> bool:
        """
        Deletes a specialty from a teacher.
        - Authorized for the teacher themselves or an admin.
        """
        log.info(f"User {current_user.id} attempting to delete specialty {specialty_id} from teacher {teacher_id}.")

        is_owner = teacher_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN.value

        if not is_owner and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this profile."
            )

        # Fetch the specific specialty, and its relationships, to ensure it exists and belongs to the teacher
        stmt = select(db_models.TeacherSpecialties).options(
            selectinload(db_models.TeacherSpecialties.student_subjects),
            selectinload(db_models.TeacherSpecialties.tuitions)
        ).filter_by(id=specialty_id)
        result = await self.db.execute(stmt)
        specialty_to_delete = result.scalars().first()

        if not specialty_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specialty not found."
            )
        
        if specialty_to_delete.teacher_id != teacher_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This specialty does not belong to the specified teacher."
            )
        
        # Check to prevent deleting a specialty if it's currently in use.
        if specialty_to_delete.student_subjects or specialty_to_delete.tuitions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete specialty as it is currently in use by a student or a tuition template."
            )

        await self.db.delete(specialty_to_delete)
        await self.db.flush()
        
        # Verify the deletion
        check_stmt = select(db_models.TeacherSpecialties).filter_by(id=specialty_id)
        refetched_result = await self.db.execute(check_stmt)
        if refetched_result.scalars().first() is None:
            log.info(f"Successfully deleted specialty {specialty_id} from teacher {teacher_id}.")
            return True
        else:
            log.error(f"Failed to delete specialty {specialty_id}, record still exists after flush.")
            await self.db.rollback()
            return False


class AdminService(UserService):
    """Service for admin-specific logic, including privilege management."""

    def __init__(self, db: Annotated[AsyncSession, Depends(get_db_session)], geo_service: Annotated[GeoService, Depends(GeoService)]):
        super().__init__(db)
        self.geo_service = geo_service

    async def get_all(self, current_user: db_models.Users) -> list[user_models.AdminRead]:
        """
        Fetches a list of all Admin objects.
        This action is restricted to MASTER admins only.
        """
        log.info(f"User {current_user.id} attempting to get all admins.")
        
        if not isinstance(current_user, db_models.Admins):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this list."
            )

        if current_user.privileges != AdminPrivilegeType.MASTER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only a Master admin can view the list of all admins."
            )
        
        stmt = select(db_models.Admins).order_by(db_models.Admins.first_name)
        result = await self.db.execute(stmt)
        admins = result.scalars().all()
        return [user_models.AdminRead.model_validate(admin) for admin in admins]

    async def create_admin(
        self,
        admin_data: user_models.AdminCreate,
        current_user: db_models.Users,
        ip_address: str
    ) -> user_models.AdminRead:
        """
        Creates a new admin user.
        - Authorized for Master admins only.
        - New admin's privilege cannot be Master.
        - Determines timezone from IP.
        """
        log.info(f"User {current_user.id} attempting to create new admin {admin_data.email}.")

        if not isinstance(current_user, db_models.Admins):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create admins."
            )

        if current_user.privileges != AdminPrivilegeType.MASTER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only a Master admin can create new admins."
            )
        
        if admin_data.privileges == AdminPrivilegeType.MASTER.value or admin_data.privileges ==AdminPrivilegeType.MASTER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create another Master admin."
            )

        existing_user = await self.get_user_by_email(admin_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered."
            )

        location_info = await self.geo_service.get_location_info(ip_address)
        hashed_password = HashedPassword.get_hash(admin_data.password)

        new_admin = db_models.Admins(
            id=uuid.uuid4(),
            email=admin_data.email,
            password=hashed_password,
            first_name=admin_data.first_name,
            last_name=admin_data.last_name,
            timezone=location_info["timezone"],
            role=UserRole.ADMIN.value,
            privileges=admin_data.privileges.value
        )

        self.db.add(new_admin)
        await self.db.flush()
        await self.db.refresh(new_admin)

        return user_models.AdminRead.model_validate(new_admin)

    async def update_admin(
        self,
        admin_id: UUID,
        update_data: user_models.AdminUpdate,
        current_user: db_models.Users
    ) -> user_models.AdminRead:
        """
        Updates an admin's profile with complex authorization.
        """
        log.info(f"User {current_user.id} attempting to update admin {admin_id}.")

        if not isinstance(current_user, db_models.Admins):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to update admin profiles."
            )

        admin_to_update = await self.get_user_by_id(admin_id)
        if not admin_to_update or not isinstance(admin_to_update, db_models.Admins):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found.")

        is_self_update = admin_to_update.id == current_user.id
        update_dict = update_data.model_dump(exclude_unset=True)

        if is_self_update:
            if 'privileges' in update_dict:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot change your own privilege level.")
        else:
            if current_user.privileges != AdminPrivilegeType.MASTER.value:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a Master admin can update other admin profiles.")
            
            if update_data.privileges == AdminPrivilegeType.MASTER.value or update_data.privileges == AdminPrivilegeType.MASTER:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot assign Master privilege. This must be done via a dedicated transfer process.")

        for key, value in update_dict.items():
            if key == "password" and value:
                setattr(admin_to_update, key, HashedPassword.get_hash(value))
            elif key == "privileges" and value:
                setattr(admin_to_update, key, value.value)
            elif value is not None:
                setattr(admin_to_update, key, value)

        self.db.add(admin_to_update)
        await self.db.flush()
        await self.db.refresh(admin_to_update)

        return user_models.AdminRead.model_validate(admin_to_update)

    async def delete_admin(self, admin_id: UUID, current_user: db_models.Users) -> bool:
        """
        Deletes an admin user.
        - Authorized for Master admins only.
        - Prevents self-deletion.
        """
        log.info(f"User {current_user.id} attempting to delete admin {admin_id}.")

        if not isinstance(current_user, db_models.Admins):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete admins."
            )

        if current_user.privileges != AdminPrivilegeType.MASTER.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a Master admin can delete other admins.")

        if admin_id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account.")

        admin_to_delete = await self.get_user_by_id(admin_id)
        if not admin_to_delete or not isinstance(admin_to_delete, db_models.Admins):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found.")

        try:
            await self.db.delete(admin_to_delete)
            await self.db.flush()
            log.info(f"Successfully deleted admin {admin_id}.")
            return True
        except Exception as e:
            # Catch potential errors from the database trigger
            await self.db.rollback()
            log.error(f"Database error during admin deletion, possibly from trigger: {e}")
            # Check if the error message is from our trigger
            if "Cannot delete or change the last Master admin" in str(e):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the last Master admin.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected database error occurred.")


