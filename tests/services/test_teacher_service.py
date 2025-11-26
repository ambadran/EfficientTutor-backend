import pytest
from uuid import UUID
from fastapi import HTTPException
from datetime import time
from decimal import Decimal
from unittest.mock import MagicMock

# --- Import models and services ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.user_service import UserService, TeacherService
from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.database.db_enums import UserRole, SubjectEnum, EducationalSystemEnum
from src.efficient_tutor_backend.common.security_utils import HashedPassword

from pprint import pp as pprint


@pytest.mark.anyio
class TestTeacherServiceRead:

    # --- Tests for get_all ---

    async def test_get_all_as_admin_happy_path(
        self,
        teacher_service: TeacherService,
        test_admin_orm: db_models.Admins,
        test_teacher_orm: db_models.Teachers # Ensure at least one teacher exists
    ):
        """Tests that an ADMIN can get all teachers."""
        teachers_orm = await teacher_service.get_all(current_user=test_admin_orm)
        
        assert len(teachers_orm) >= 1
        assert any(t.id == test_teacher_orm.id for t in teachers_orm)
        assert all(isinstance(t, db_models.Teachers) for t in teachers_orm)

        print(f"\nFound {len(teachers_orm)} Teacher users")
        print("Example Teacher user:")
        pprint(teachers_orm[0].__dict__)

        # Convert ORM to Pydantic models for the actual API response check
        teachers_read = [user_models.TeacherRead.model_validate(t) for t in teachers_orm]

        assert len(teachers_read) >= 1
        assert all(isinstance(t, user_models.TeacherRead) for t in teachers_read)
        
        # Assert that teacher_specialties are loaded and are not empty
        first_teacher_with_specialties = next((t for t in teachers_read if t.teacher_specialties), None)
        assert first_teacher_with_specialties is not None
        assert isinstance(first_teacher_with_specialties.teacher_specialties, list)
        assert len(first_teacher_with_specialties.teacher_specialties) > 0
        assert isinstance(first_teacher_with_specialties.teacher_specialties[0], user_models.TeacherSpecialtyRead)
        pprint(first_teacher_with_specialties.teacher_specialties)

    async def test_get_all_as_teacher_forbidden(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that a TEACHER cannot get all teachers (HTTP 403)."""
        with pytest.raises(HTTPException) as e:
            await teacher_service.get_all(current_user=test_teacher_orm)
        
        assert e.value.status_code == 403
        assert "You do not have permission to view this list." in e.value.detail

    async def test_get_all_as_parent_forbidden(
        self,
        teacher_service: TeacherService,
        test_parent_orm: db_models.Parents
    ):
        """Tests that a PARENT cannot get all teachers (HTTP 403)."""
        with pytest.raises(HTTPException) as e:
            await teacher_service.get_all(current_user=test_parent_orm)
        
        assert e.value.status_code == 403
        assert "You do not have permission to view this list." in e.value.detail

        assert "You do not have permission to view this list." in e.value.detail


@pytest.mark.anyio
class TestTeacherServiceCreate:

    # --- Tests for create_teacher ---

    async def test_create_teacher_happy_path(
        self,
        teacher_service: TeacherService,
        user_service: UserService,
        mock_geo_service: MagicMock
    ):
        """Tests the successful creation of a new teacher user."""
        print("\n--- Testing create_teacher (Happy Path) ---")
        teacher_data = user_models.TeacherCreate(
            email="new.teacher@example.com",
            password="strongpassword123",
            first_name="New",
            last_name="Teacher",
            timezone="UTC", # This will be overridden by geo_service
            currency="USD",  # This will be overridden by geo_service
            teacher_specialties=[
                user_models.TeacherSpecialtyWrite(
                    subject=SubjectEnum.MATH,
                    educational_system=EducationalSystemEnum.NATIONAL_EG,
                    grade=8
                ),
                user_models.TeacherSpecialtyWrite(
                    subject=SubjectEnum.PHYSICS,
                    educational_system=EducationalSystemEnum.IGCSE,
                    grade=8
                )
            ]
        )
        ip_address = "1.2.3.4" # Dummy IP for testing

        # --- ACT ---
        created_teacher = await teacher_service.create_teacher(teacher_data, ip_address)

        # --- ASSERT ---
        # 1. Check the returned Pydantic model
        assert isinstance(created_teacher, user_models.TeacherRead)
        assert created_teacher.email == teacher_data.email
        assert created_teacher.first_name == teacher_data.first_name
        assert created_teacher.role == UserRole.TEACHER
        assert created_teacher.is_first_sign_in is True
        assert created_teacher.timezone == "America/New_York" # Assert against mocked value
        assert created_teacher.currency == "USD" # Assert against mocked value
        
        # New assertions for teacher_specialties
        assert created_teacher.teacher_specialties is not None
        assert isinstance(created_teacher.teacher_specialties, list)
        assert len(created_teacher.teacher_specialties) == 2
        assert isinstance(created_teacher.teacher_specialties[0], user_models.TeacherSpecialtyRead)
        
        created_specialties_subjects = {s.subject for s in created_teacher.teacher_specialties}
        created_specialties_systems = {s.educational_system for s in created_teacher.teacher_specialties}
        
        assert SubjectEnum.MATH in created_specialties_subjects
        assert SubjectEnum.PHYSICS in created_specialties_subjects
        assert EducationalSystemEnum.NATIONAL_EG in created_specialties_systems
        assert EducationalSystemEnum.IGCSE in created_specialties_systems

        # 2. Verify the user exists in the database
        db_user = await user_service.get_user_by_id(created_teacher.id)
        assert db_user is not None
        assert db_user.email == teacher_data.email
        assert isinstance(db_user, db_models.Teachers)
        assert db_user.timezone == "America/New_York" # Assert against mocked value
        assert db_user.currency == "USD" # Assert against mocked value
        assert db_user.teacher_specialties is not None
        assert len(db_user.teacher_specialties) == 2
        assert isinstance(db_user.teacher_specialties[0], db_models.TeacherSpecialties)

        # 3. Verify the password was hashed correctly
        assert HashedPassword.verify(teacher_data.password, db_user.password) is True
        assert db_user.password != teacher_data.password

        # 4. Verify geo_service was called
        mock_geo_service.get_location_info.assert_called_once_with(ip_address)

        print("--- Successfully created teacher ---")
        pprint(created_teacher.model_dump())

    async def test_create_teacher_duplicate_email(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        mock_geo_service: MagicMock
    ):
        """Tests that creating a teacher with a duplicate email raises a 400 error."""
        print("\n--- Testing create_teacher with duplicate email ---")
        teacher_data = user_models.TeacherCreate(
            email=test_teacher_orm.email,  # Use an existing email
            password="anotherpassword",
            first_name="Duplicate",
            last_name="Email",
            timezone="UTC",
            currency="EUR"
        )
        ip_address = "5.6.7.8" # Dummy IP

        # --- ACT & ASSERT ---
        with pytest.raises(HTTPException) as exc_info:
            await teacher_service.create_teacher(teacher_data, ip_address)   
        
        assert exc_info.value.status_code == 400
        assert "Email already registered" in exc_info.value.detail   
        print(f"--- Correctly raised HTTPException: {exc_info.value.status_code} ---")


@pytest.mark.anyio
class TestTeacherServiceUpdate:

    # --- Tests for update_teacher ---

    async def test_update_teacher_as_self_happy_path(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        user_service: UserService
    ):
        """Tests that a teacher can successfully update their own profile."""
        print("\n--- Testing update_teacher as self ---")
        update_data = user_models.TeacherUpdate(
            first_name="UpdatedTeacherFirstName",
            currency="EUR"
        )
        
        original_specialty_count = len(test_teacher_orm.teacher_specialties)
        assert original_specialty_count > 0

        updated_teacher = await teacher_service.update_teacher(
            teacher_id=test_teacher_orm.id,
            update_data=update_data,
            current_user=test_teacher_orm
        )

        assert isinstance(updated_teacher, user_models.TeacherRead)
        assert updated_teacher.id == test_teacher_orm.id
        assert updated_teacher.first_name == "UpdatedTeacherFirstName"
        assert updated_teacher.currency == "EUR"
        # Ensure other fields are unchanged
        assert updated_teacher.last_name == test_teacher_orm.last_name
        
        # Assert that specialties were NOT changed by this operation
        assert len(updated_teacher.teacher_specialties) == original_specialty_count

        # Verify in DB
        db_user = await user_service.get_user_by_id(test_teacher_orm.id)
        assert db_user.first_name == "UpdatedTeacherFirstName"
        assert db_user.currency == "EUR"
        assert len(db_user.teacher_specialties) == original_specialty_count
        
        print("--- Successfully updated teacher as self, specialties were preserved. ---")
        pprint(updated_teacher.model_dump())

    async def test_update_teacher_as_admin_happy_path(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        test_admin_orm: db_models.Admins,
        user_service: UserService
    ):
        """Tests that an admin can successfully update a teacher's profile."""
        print("\n--- Testing update_teacher as admin ---")
        update_data = user_models.TeacherUpdate(
            email="new.teacher.email@example.com",
            timezone="Europe/London"
        )

        updated_teacher = await teacher_service.update_teacher(
            teacher_id=test_teacher_orm.id,
            update_data=update_data,
            current_user=test_admin_orm
        )

        assert isinstance(updated_teacher, user_models.TeacherRead)
        assert updated_teacher.email == "new.teacher.email@example.com"
        assert updated_teacher.timezone == "Europe/London"

        # Verify in DB
        db_user = await user_service.get_user_by_id(test_teacher_orm.id)
        assert db_user.email == "new.teacher.email@example.com"
        assert db_user.timezone == "Europe/London"
        print("--- Successfully updated teacher as admin ---")
        pprint(updated_teacher.model_dump())

    async def test_update_teacher_password_change(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        user_service: UserService
    ):
        """Tests that a teacher can update their own password."""
        print("\n--- Testing update_teacher password change ---")
        new_password = "new_secure_teacher_password_456"
        update_data = user_models.TeacherUpdate(password=new_password)

        original_hash = test_teacher_orm.password
        
        await teacher_service.update_teacher(
            teacher_id=test_teacher_orm.id,
            update_data=update_data,
            current_user=test_teacher_orm
        )

        db_user = await user_service.get_user_by_id(test_teacher_orm.id)
        assert db_user.password != original_hash
        assert HashedPassword.verify(new_password, db_user.password)
        print("--- Successfully updated teacher password ---")

    async def test_update_teacher_as_unrelated_teacher_forbidden(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        test_unrelated_teacher_orm: db_models.Teachers
    ):
        """Tests that an unrelated teacher is forbidden from updating a profile."""
        print("\n--- Testing update_teacher as unrelated teacher (Forbidden) ---")
        update_data = user_models.TeacherUpdate(first_name="Forbidden")
        
        with pytest.raises(HTTPException) as e:
            await teacher_service.update_teacher(
                teacher_id=test_teacher_orm.id,
                update_data=update_data,
                current_user=test_unrelated_teacher_orm
            )
        assert e.value.status_code == 403
        assert "You do not have permission to update this profile." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_update_teacher_as_parent_forbidden(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        test_parent_orm: db_models.Parents
    ):
        """Tests that a parent is forbidden from updating a teacher's profile."""
        print("\n--- Testing update_teacher as parent (Forbidden) ---")
        update_data = user_models.TeacherUpdate(first_name="Forbidden")
        
        with pytest.raises(HTTPException) as e:
            await teacher_service.update_teacher(
                teacher_id=test_teacher_orm.id,
                update_data=update_data,
                current_user=test_parent_orm
            )
        assert e.value.status_code == 403
        assert "You do not have permission to update this profile." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_update_teacher_as_student_forbidden(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        test_student_orm: db_models.Students
    ):
        """Tests that a student is forbidden from updating a teacher's profile."""
        print("\n--- Testing update_teacher as student (Forbidden) ---")
        update_data = user_models.TeacherUpdate(first_name="Forbidden")
        
        with pytest.raises(HTTPException) as e:
            await teacher_service.update_teacher(
                teacher_id=test_teacher_orm.id,
                update_data=update_data,
                current_user=test_student_orm
            )
        assert e.value.status_code == 403
        assert "You do not have permission to update this profile." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_update_teacher_not_found(
        self,
        teacher_service: TeacherService,
        test_admin_orm: db_models.Admins
    ):
        """Tests that updating a non-existent teacher raises a 404."""
        print("\n--- Testing update_teacher for non-existent ID ---")
        update_data = user_models.TeacherUpdate(first_name="NotFound")

        with pytest.raises(HTTPException) as e:
            await teacher_service.update_teacher(
                teacher_id=UUID(int=0),
                update_data=update_data,
                current_user=test_admin_orm
            )
        assert e.value.status_code == 404
        assert "Teacher not found." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")


@pytest.mark.anyio
class TestTeacherServiceUpdateSpecialties:
    """Tests for adding and removing teacher specialties."""

    async def test_add_specialty_as_owner(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        db_session
    ):
        """Tests a teacher can add a new specialty to their own profile."""
        print("\n--- Testing add_specialty_as_owner ---")
        specialty_data = user_models.TeacherSpecialtyWrite(
            subject=SubjectEnum.GEOGRAPHY,
            educational_system=EducationalSystemEnum.IGCSE,
            grade=8
        )
        
        # Ensure the specialty doesn't already exist
        assert not any(
            s.subject == specialty_data.subject.value and s.educational_system == specialty_data.educational_system.value
            for s in test_teacher_orm.teacher_specialties
        )
        
        original_count = len(test_teacher_orm.teacher_specialties)

        updated_teacher = await teacher_service.add_specialty_to_teacher(
            teacher_id=test_teacher_orm.id,
            specialty_data=specialty_data,
            current_user=test_teacher_orm
        )

        assert len(updated_teacher.teacher_specialties) == original_count + 1
        
        new_specialty = next(
            s for s in updated_teacher.teacher_specialties 
            if s.subject == specialty_data.subject and s.educational_system == specialty_data.educational_system
        )
        assert new_specialty is not None

        # Verify in DB
        await db_session.refresh(test_teacher_orm, ['teacher_specialties'])
        assert len(test_teacher_orm.teacher_specialties) == original_count + 1
        print("--- Successfully added new specialty as owner. ---")

    async def test_add_specialty_as_admin(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        test_admin_orm: db_models.Admins,
        db_session
    ):
        """Tests an admin can add a new specialty to a teacher's profile."""
        print("\n--- Testing add_specialty_as_admin ---")
        specialty_data = user_models.TeacherSpecialtyWrite(
            subject=SubjectEnum.GEOGRAPHY,
            educational_system=EducationalSystemEnum.NATIONAL_EG,
            grade=8
        )
        
        original_count = len(test_teacher_orm.teacher_specialties)

        updated_teacher = await teacher_service.add_specialty_to_teacher(
            teacher_id=test_teacher_orm.id,
            specialty_data=specialty_data,
            current_user=test_admin_orm
        )

        assert len(updated_teacher.teacher_specialties) == original_count + 1
        
        await db_session.refresh(test_teacher_orm, ['teacher_specialties'])
        assert len(test_teacher_orm.teacher_specialties) == original_count + 1
        print("--- Successfully added new specialty as admin. ---")

    async def test_add_duplicate_specialty_fails(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that adding an existing specialty raises a 400 error."""
        print("\n--- Testing add_duplicate_specialty_fails ---")
        
        # Get a specialty that already exists from the fixture
        existing_specialty = test_teacher_orm.teacher_specialties[0]
        specialty_data = user_models.TeacherSpecialtyWrite(
            subject=SubjectEnum(existing_specialty.subject),
            educational_system=EducationalSystemEnum(existing_specialty.educational_system),
            grade=10
        )

        with pytest.raises(HTTPException) as e:
            await teacher_service.add_specialty_to_teacher(
                teacher_id=test_teacher_orm.id,
                specialty_data=specialty_data,
                current_user=test_teacher_orm
            )
        
        assert e.value.status_code == 400
        assert "This specialty already exists for this teacher" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_add_specialty_as_unauthorized_user_fails(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        test_parent_orm: db_models.Parents
    ):
        """Tests that a non-admin/non-owner cannot add a specialty."""
        print("\n--- Testing add_specialty_as_unauthorized_user_fails ---")
        specialty_data = user_models.TeacherSpecialtyWrite(
            subject=SubjectEnum.GEOGRAPHY,
            educational_system=EducationalSystemEnum.SAT,
            grade=8
        )

        with pytest.raises(HTTPException) as e:
            await teacher_service.add_specialty_to_teacher(
                teacher_id=test_teacher_orm.id,
                specialty_data=specialty_data,
                current_user=test_parent_orm
            )
        
        assert e.value.status_code == 403
        assert "You do not have permission to modify this profile" in e.value.detail
        print(f"--- Correctly raised HTTPException for unauthorized user: {e.value.status_code} ---")

    async def test_delete_unused_specialty_as_owner(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        db_session
    ):
        """Tests a teacher can delete an unused specialty from their profile."""
        print("\n--- Testing delete_unused_specialty_as_owner ---")
        
        # ARRANGE: Add a new, unused specialty first
        specialty_data = user_models.TeacherSpecialtyWrite(
            subject=SubjectEnum.IT,
            educational_system=EducationalSystemEnum.NATIONAL_KW,
            grade=8
        )
        teacher_with_new_specialty = await teacher_service.add_specialty_to_teacher(
            teacher_id=test_teacher_orm.id,
            specialty_data=specialty_data,
            current_user=test_teacher_orm
        )
        
        specialty_to_delete = next(
            s for s in teacher_with_new_specialty.teacher_specialties
            if s.subject == specialty_data.subject and s.educational_system == specialty_data.educational_system
        )
        assert specialty_to_delete is not None
        
        original_count = len(teacher_with_new_specialty.teacher_specialties)

        # ACT: Delete the specialty
        await teacher_service.delete_teacher_specialty(
            teacher_id=test_teacher_orm.id,
            specialty_id=specialty_to_delete.id,
            current_user=test_teacher_orm
        )
        
        # ASSERT
        await db_session.refresh(test_teacher_orm, ['teacher_specialties'])
        assert len(test_teacher_orm.teacher_specialties) == original_count - 1
        assert not any(s.id == specialty_to_delete.id for s in test_teacher_orm.teacher_specialties)
        print("--- Successfully deleted unused specialty. ---")

    async def test_delete_unused_specialty_as_admin(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers,
        test_admin_orm: db_models.Admins,
        db_session
    ):
        """Tests an admin can delete an unused specialty from a teacher's profile."""
        print("\n--- Testing delete_unused_specialty_as_admin ---")
        
        # ARRANGE: Add a new, unused specialty first
        specialty_data = user_models.TeacherSpecialtyWrite(
            subject=SubjectEnum.IT,
            educational_system=EducationalSystemEnum.NATIONAL_EG,
            grade=8
        )
        teacher_with_new_specialty = await teacher_service.add_specialty_to_teacher(
            teacher_id=test_teacher_orm.id,
            specialty_data=specialty_data,
            current_user=test_admin_orm # Admin adds the specialty
        )
        
        specialty_to_delete = next(
            s for s in teacher_with_new_specialty.teacher_specialties
            if s.subject == specialty_data.subject and s.educational_system == specialty_data.educational_system
        )
        assert specialty_to_delete is not None
        original_count = len(teacher_with_new_specialty.teacher_specialties)

        # ACT: Delete the specialty as admin
        await teacher_service.delete_teacher_specialty(
            teacher_id=test_teacher_orm.id,
            specialty_id=specialty_to_delete.id,
            current_user=test_admin_orm
        )
        
        # ASSERT
        await db_session.refresh(test_teacher_orm, ['teacher_specialties'])
        assert len(test_teacher_orm.teacher_specialties) == original_count - 1
        assert not any(s.id == specialty_to_delete.id for s in test_teacher_orm.teacher_specialties)
        print("--- Successfully deleted unused specialty as admin. ---")

    async def test_delete_specialty_in_use_by_student_subject_fails(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that deleting a specialty used by a student_subject fails."""
        print("\n--- Testing delete_specialty_in_use_by_student_subject_fails ---")
        
        # ARRANGE: Find a specialty that is known to be in use by the seeded data
        # From `student_details.py`, we know TEST_TEACHER_ID teaches PHYSICS IGCSE to TEST_STUDENT_ID
        used_specialty = next(
            s for s in test_teacher_orm.teacher_specialties
            if s.subject == SubjectEnum.PHYSICS.value and s.educational_system == EducationalSystemEnum.IGCSE.value
        )
        assert used_specialty is not None

        # ACT & ASSERT
        with pytest.raises(HTTPException) as e:
            await teacher_service.delete_teacher_specialty(
                teacher_id=test_teacher_orm.id,
                specialty_id=used_specialty.id,
                current_user=test_teacher_orm
            )
        
        assert e.value.status_code == 400
        assert "Cannot delete specialty as it is currently in use" in e.value.detail
        print(f"--- Correctly raised HTTPException for deleting used specialty: {e.value.status_code} ---")

    async def test_delete_non_existent_specialty_fails(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that deleting a non-existent specialty_id raises a 404."""
        print("\n--- Testing delete_non_existent_specialty_fails ---")
        non_existent_specialty_id = UUID(int=0)

        with pytest.raises(HTTPException) as e:
            await teacher_service.delete_teacher_specialty(
                teacher_id=test_teacher_orm.id,
                specialty_id=non_existent_specialty_id,
                current_user=test_teacher_orm
            )
        
        assert e.value.status_code == 404
        assert "Specialty not found" in e.value.detail
        print(f"--- Correctly raised HTTPException for non-existent specialty: {e.value.status_code} ---")

@pytest.mark.anyio
class TestTeacherServiceDelete:
    pass


@pytest.mark.anyio
class TestTeacherServiceGetBySpecialty:
    """Tests for the get_all_for_student_subject method."""

    async def test_get_all_for_student_subject_as_parent_success(
        self,
        teacher_service: TeacherService,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that a parent can successfully fetch teachers by specialty."""
        print("\n--- Testing get_all_for_student_subject as PARENT (Happy Path) ---")
        query = user_models.TeacherSpecialtyQuery(
            subject=SubjectEnum.PHYSICS,
            educational_system=EducationalSystemEnum.IGCSE,
            grade=10
        )

        teachers = await teacher_service.get_all_for_student_subject(query, test_parent_orm)

        assert isinstance(teachers, list)
        assert len(teachers) > 0
        assert any(t.id == test_teacher_orm.id for t in teachers)
        print(f"--- Found {len(teachers)} teachers for the specified specialty. ---")

    async def test_get_all_for_student_subject_as_admin_success(
        self,
        teacher_service: TeacherService,
        test_admin_orm: db_models.Admins,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that an admin can successfully fetch teachers by specialty."""
        print("\n--- Testing get_all_for_student_subject as ADMIN (Happy Path) ---")
        query = user_models.TeacherSpecialtyQuery(
            subject=SubjectEnum.PHYSICS,
            educational_system=EducationalSystemEnum.IGCSE,
            grade=10
        )

        teachers = await teacher_service.get_all_for_student_subject(query, test_admin_orm)

        assert isinstance(teachers, list)
        assert len(teachers) > 0
        assert any(t.id == test_teacher_orm.id for t in teachers)
        print(f"--- Found {len(teachers)} teachers for the specified specialty. ---")

    async def test_get_all_for_student_subject_no_match(
        self,
        teacher_service: TeacherService,
        test_parent_orm: db_models.Parents
    ):
        """Tests that an empty list is returned when no teachers match the specialty."""
        print("\n--- Testing get_all_for_student_subject with no matching specialty ---")
        # This subject/system combination is not in the test data for any teacher
        query = user_models.TeacherSpecialtyQuery(
            subject=SubjectEnum.GEOGRAPHY,
            educational_system=EducationalSystemEnum.IGCSE,
            grade=10
        )

        teachers = await teacher_service.get_all_for_student_subject(query, test_parent_orm)

        assert isinstance(teachers, list)
        assert len(teachers) == 0
        print("--- Correctly returned an empty list for a non-matching specialty. ---")

    async def test_get_all_for_student_subject_as_teacher_forbidden(
        self,
        teacher_service: TeacherService,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that a teacher is forbidden from fetching teachers by specialty."""
        print("\n--- Testing get_all_for_student_subject as TEACHER (Forbidden) ---")
        query = user_models.TeacherSpecialtyQuery(
            subject=SubjectEnum.PHYSICS,
            educational_system=EducationalSystemEnum.IGCSE,
            grade=10
        )

        with pytest.raises(HTTPException) as e:
            await teacher_service.get_all_for_student_subject(query, test_teacher_orm)

        assert e.value.status_code == 403
        assert "You do not have permission to view this list." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_get_all_for_student_subject_as_student_forbidden(
        self,
        teacher_service: TeacherService,
        test_student_orm: db_models.Students
    ):
        """Tests that a student is forbidden from fetching teachers by specialty."""
        print("\n--- Testing get_all_for_student_subject as STUDENT (Forbidden) ---")
        query = user_models.TeacherSpecialtyQuery(
            subject=SubjectEnum.PHYSICS,
            educational_system=EducationalSystemEnum.IGCSE,
            grade=10
        )

        with pytest.raises(HTTPException) as e:
            await teacher_service.get_all_for_student_subject(query, test_student_orm)

        assert e.value.status_code == 403
        assert "You do not have permission to view this list." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

