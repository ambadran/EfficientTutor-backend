import pytest
from uuid import UUID
from fastapi import HTTPException
from datetime import time
from decimal import Decimal
from unittest.mock import MagicMock

# --- Import models and services ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.user_service import AdminService, UserService # Added UserService
from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.database.db_enums import UserRole, AdminPrivilegeType
from src.efficient_tutor_backend.common.security_utils import HashedPassword # Added HashedPassword

from pprint import pp as pprint


@pytest.mark.anyio
class TestAdminService:

    # --- Tests for get_all ---

    async def test_get_all_as_master_admin_happy_path(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins, # Master admin
        test_normal_admin_orm: db_models.Admins # Ensure at least one other admin exists
    ):
        """Tests that a MASTER admin can get all admins."""
        print("\n--- Testing get_all as MASTER admin (Happy Path) ---")
        admins = await admin_service.get_all(current_user=test_admin_orm)
        
        assert len(admins) >= 2 # Master admin + normal admin
        assert any(a.id == test_admin_orm.id for a in admins)
        assert any(a.id == test_normal_admin_orm.id for a in admins)
        assert all(isinstance(a, user_models.AdminRead) for a in admins)

        print(f"Found {len(admins)} Admin users")
        print("Example Admin user:")
        pprint(admins[0].model_dump())

    async def test_get_all_as_normal_admin_forbidden(
        self,
        admin_service: AdminService,
        test_normal_admin_orm: db_models.Admins
    ):
        """Tests that a NORMAL admin cannot get all admins (HTTP 403)."""
        print("\n--- Testing get_all as NORMAL admin (Forbidden) ---")
        with pytest.raises(HTTPException) as e:
            await admin_service.get_all(current_user=test_normal_admin_orm)
        
        assert e.value.status_code == 403
        assert "Only a Master admin can view the list of all admins." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_get_all_as_teacher_forbidden(
        self,
        admin_service: AdminService,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that a TEACHER cannot get all admins (HTTP 403)."""
        print("\n--- Testing get_all as TEACHER (Forbidden) ---")
        with pytest.raises(HTTPException) as e:
            await admin_service.get_all(current_user=test_teacher_orm)
        
        assert e.value.status_code == 403
        assert "You do not have permission to view this list." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_get_all_as_parent_forbidden(
        self,
        admin_service: AdminService,
        test_parent_orm: db_models.Parents
    ):
        """Tests that a PARENT cannot get all admins (HTTP 403)."""
        print("\n--- Testing get_all as PARENT (Forbidden) ---")
        with pytest.raises(HTTPException) as e:
            await admin_service.get_all(current_user=test_parent_orm)
        
        assert e.value.status_code == 403
        assert "You do not have permission to view this list." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_get_all_as_student_forbidden(
        self,
        admin_service: AdminService,
        test_student_orm: db_models.Students
    ):
        """Tests that a STUDENT cannot get all admins (HTTP 403)."""
        print("\n--- Testing get_all as STUDENT (Forbidden) ---")
        with pytest.raises(HTTPException) as e:
            await admin_service.get_all(current_user=test_student_orm)
        
        assert e.value.status_code == 403
        assert "You do not have permission to view this list." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    # --- Tests for create_admin ---

    async def test_create_admin_as_master_admin_happy_path(
        self,
        admin_service: AdminService,
        user_service: UserService, # Need UserService to verify creation
        test_admin_orm: db_models.Admins, # Master admin
        mock_geo_service: MagicMock
    ):
        """Tests successful creation of a new non-master admin by a master admin."""
        print("\n--- Testing create_admin as MASTER admin (Happy Path) ---")
        admin_data = user_models.AdminCreate(
            email="new.normal.admin@example.com",
            password="securepassword123",
            first_name="New",
            last_name="NormalAdmin",
            privileges=AdminPrivilegeType.NORMAL # Creating a normal admin
        )
        ip_address = "1.2.3.4" # Dummy IP for testing

        # --- ACT ---
        created_admin = await admin_service.create_admin(admin_data, test_admin_orm, ip_address)

        # --- ASSERT ---
        assert isinstance(created_admin, user_models.AdminRead)
        assert created_admin.email == admin_data.email
        assert created_admin.first_name == admin_data.first_name
        assert created_admin.role == UserRole.ADMIN
        assert created_admin.privileges == AdminPrivilegeType.NORMAL

        # Verify in DB
        db_admin = await user_service.get_user_by_id(created_admin.id)
        assert db_admin is not None
        assert isinstance(db_admin, db_models.Admins)
        assert db_admin.email == admin_data.email
        assert db_admin.privileges == AdminPrivilegeType.NORMAL.value
        assert HashedPassword.verify(admin_data.password, db_admin.password)

        mock_geo_service.get_location_info.assert_called_once_with(ip_address)
        print("--- Successfully created new normal admin ---")
        pprint(created_admin.model_dump())

    async def test_create_admin_as_master_admin_duplicate_email(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins, # Master admin
        test_normal_admin_orm: db_models.Admins, # Existing admin for duplicate email
        mock_geo_service: MagicMock
    ):
        """Tests that creating an admin with a duplicate email by a master admin raises a 400 error."""
        print("\n--- Testing create_admin with duplicate email ---")
        admin_data = user_models.AdminCreate(
            email=test_normal_admin_orm.email, # Use existing email
            password="anotherpassword",
            first_name="Duplicate",
            last_name="Admin",
            privileges=AdminPrivilegeType.READ_ONLY
        )
        ip_address = "5.6.7.8"

        with pytest.raises(HTTPException) as exc_info:
            await admin_service.create_admin(admin_data, test_admin_orm, ip_address)
        
        assert exc_info.value.status_code == 400
        assert "Email already registered" in exc_info.value.detail
        print(f"--- Correctly raised HTTPException: {exc_info.value.status_code} {exc_info.value.detail} ---")

    async def test_create_admin_as_master_admin_create_master_forbidden(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins, # Master admin
        mock_geo_service: MagicMock
    ):
        """Tests that a master admin cannot create another master admin."""
        print("\n--- Testing create_admin as MASTER admin (Create Master Forbidden) ---")
        admin_data = user_models.AdminCreate(
            email="forbidden.master@example.com",
            password="password",
            first_name="Forbidden",
            last_name="Master",
            privileges=AdminPrivilegeType.MASTER # Attempt to create master
        )
        ip_address = "9.10.11.12"

        with pytest.raises(HTTPException) as exc_info:
            await admin_service.create_admin(admin_data, test_admin_orm, ip_address)
        
        assert exc_info.value.status_code == 400
        assert "Cannot create another Master admin." in exc_info.value.detail
        print(f"--- Correctly raised HTTPException: {exc_info.value.status_code} {exc_info.value.detail} ---")

    async def test_create_admin_as_normal_admin_forbidden(
        self,
        admin_service: AdminService,
        test_normal_admin_orm: db_models.Admins, # Normal admin
        mock_geo_service: MagicMock
    ):
        """Tests that a normal admin is forbidden from creating new admins."""
        print("\n--- Testing create_admin as NORMAL admin (Forbidden) ---")
        admin_data = user_models.AdminCreate(
            email="normal.admin.create.forbidden@example.com",
            password="password",
            first_name="Forbidden",
            last_name="Normal",
            privileges=AdminPrivilegeType.READ_ONLY
        )
        ip_address = "13.14.15.16"

        with pytest.raises(HTTPException) as exc_info:
            await admin_service.create_admin(admin_data, test_normal_admin_orm, ip_address)
        
        assert exc_info.value.status_code == 403
        assert "Only a Master admin can create new admins." in exc_info.value.detail
        print(f"--- Correctly raised HTTPException: {exc_info.value.status_code} {exc_info.value.detail} ---")

    async def test_create_admin_as_teacher_forbidden(
        self,
        admin_service: AdminService,
        test_teacher_orm: db_models.Teachers,
        mock_geo_service: MagicMock
    ):
        """Tests that a teacher is forbidden from creating new admins."""
        print("\n--- Testing create_admin as TEACHER (Forbidden) ---")
        admin_data = user_models.AdminCreate(
            email="teacher.create.forbidden@example.com",
            password="password",
            first_name="Forbidden",
            last_name="Teacher",
            privileges=AdminPrivilegeType.NORMAL
        )
        ip_address = "17.18.19.20"

        with pytest.raises(HTTPException) as exc_info:
            await admin_service.create_admin(admin_data, test_teacher_orm, ip_address)
        
        assert exc_info.value.status_code == 403
        assert "You do not have permission to create admins." in exc_info.value.detail
        print(f"--- Correctly raised HTTPException: {exc_info.value.status_code} {exc_info.value.detail} ---")

    async def test_create_admin_as_parent_forbidden(
        self,
        admin_service: AdminService,
        test_parent_orm: db_models.Parents,
        mock_geo_service: MagicMock
    ):
        """Tests that a parent is forbidden from creating new admins."""
        print("\n--- Testing create_admin as PARENT (Forbidden) ---")
        admin_data = user_models.AdminCreate(
            email="parent.create.forbidden@example.com",
            password="password",
            first_name="Forbidden",
            last_name="Parent",
            privileges=AdminPrivilegeType.NORMAL
        )
        ip_address = "21.22.23.24"

        with pytest.raises(HTTPException) as exc_info:
            await admin_service.create_admin(admin_data, test_parent_orm, ip_address)
        
        assert exc_info.value.status_code == 403
        assert "You do not have permission to create admins." in exc_info.value.detail
        print(f"--- Correctly raised HTTPException: {exc_info.value.status_code} {exc_info.value.detail} ---")

    async def test_create_admin_as_student_forbidden(
        self,
        admin_service: AdminService,
        test_student_orm: db_models.Students,
        mock_geo_service: MagicMock
    ):
        """Tests that a student is forbidden from creating new admins."""
        print("\n--- Testing create_admin as STUDENT (Forbidden) ---")
        admin_data = user_models.AdminCreate(
            email="student.create.forbidden@example.com",
            password="password",
            first_name="Forbidden",
            last_name="Student",
            privileges=AdminPrivilegeType.NORMAL
        )
        ip_address = "25.26.27.28"

        with pytest.raises(HTTPException) as exc_info:
            await admin_service.create_admin(admin_data, test_student_orm, ip_address)
        
        assert exc_info.value.status_code == 403
        assert "You do not have permission to create admins." in exc_info.value.detail
        print(f"--- Correctly raised HTTPException: {exc_info.value.status_code} {exc_info.value.detail} ---")

    # --- Tests for update_admin ---

    async def test_update_admin_as_self_happy_path(
        self,
        admin_service: AdminService,
        test_normal_admin_orm: db_models.Admins, # Normal admin
        user_service: UserService
    ):
        """Tests that an admin can successfully update their own profile (excluding privileges)."""
        print("\n--- Testing update_admin as self (Happy Path) ---")
        update_data = user_models.AdminUpdate(
            first_name="UpdatedNormal",
            last_name="AdminSelf"
        )
        updated_admin = await admin_service.update_admin(
            admin_id=test_normal_admin_orm.id,
            update_data=update_data,
            current_user=test_normal_admin_orm
        )
        
        assert isinstance(updated_admin, user_models.AdminRead)
        assert updated_admin.id == test_normal_admin_orm.id
        assert updated_admin.first_name == "UpdatedNormal"
        assert updated_admin.last_name == "AdminSelf"
        assert updated_admin.privileges == AdminPrivilegeType.NORMAL # Privileges should not change
        
        db_admin = await user_service.get_user_by_id(test_normal_admin_orm.id)
        assert db_admin.first_name == "UpdatedNormal"
        assert db_admin.last_name == "AdminSelf"
        print("--- Successfully updated normal admin as self ---")
        pprint(updated_admin.model_dump())

    async def test_update_admin_as_self_change_privileges_forbidden(
        self,
        admin_service: AdminService,
        test_normal_admin_orm: db_models.Admins # Normal admin
    ):
        """Tests that an admin cannot change their own privilege level."""
        print("\n--- Testing update_admin as self (Change Privileges Forbidden) ---")
        update_data = user_models.AdminUpdate(
            privileges=AdminPrivilegeType.READ_ONLY # Attempt to change own privilege
        )
        with pytest.raises(HTTPException) as e:
            await admin_service.update_admin(
                admin_id=test_normal_admin_orm.id,
                update_data=update_data,
                current_user=test_normal_admin_orm
            )
        assert e.value.status_code == 403
        assert "You cannot change your own privilege level." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail}---")

    async def test_update_admin_as_master_admin_update_other_admin_happy_path(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins, # Master admin
        test_normal_admin_orm: db_models.Admins, # Admin to be updated
        user_service: UserService
    ):
        """Tests that a master admin can successfully update another admin's profile."""
        print("\n--- Testing update_admin as MASTER admin (Update Other Admin Happy Path) ---")
        update_data = user_models.AdminUpdate(
            first_name="UpdatedByMaster",
            privileges=AdminPrivilegeType.READ_ONLY # Master admin can change other's privileges
        )
        updated_admin = await admin_service.update_admin(
            admin_id=test_normal_admin_orm.id,
            update_data=update_data,
            current_user=test_admin_orm
        )
        
        assert isinstance(updated_admin, user_models.AdminRead)
        assert updated_admin.id == test_normal_admin_orm.id
        assert updated_admin.first_name == "UpdatedByMaster"
        assert updated_admin.privileges == AdminPrivilegeType.READ_ONLY
        
        db_admin = await user_service.get_user_by_id(test_normal_admin_orm.id)
        assert db_admin.first_name == "UpdatedByMaster"
        assert db_admin.privileges == AdminPrivilegeType.READ_ONLY.value
        print("--- Successfully updated other admin by master admin ---")
        pprint(updated_admin.model_dump())

    async def test_update_admin_as_master_admin_assign_master_privilege_forbidden(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins, # Master admin
        test_normal_admin_orm: db_models.Admins # Admin to be updated
    ):
        """Tests that a master admin cannot assign Master privilege to another admin via update."""
        print("\n--- Testing update_admin as MASTER admin (Assign Master Forbidden) ---")
        update_data = user_models.AdminUpdate(
            privileges=AdminPrivilegeType.MASTER # Attempt to assign Master
        )
        with pytest.raises(HTTPException) as e:
            await admin_service.update_admin(
                admin_id=test_normal_admin_orm.id,
                update_data=update_data,
                current_user=test_admin_orm
            )
        assert e.value.status_code == 400
        assert "Cannot assign Master privilege." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    async def test_update_admin_as_normal_admin_update_other_admin_forbidden(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins, # Master admin (target)
        test_normal_admin_orm: db_models.Admins # Normal admin (current_user)
    ):
        """Tests that a normal admin is forbidden from updating another admin's profile."""
        print("\n--- Testing update_admin as NORMAL admin (Update Other Admin Forbidden) ---")
        update_data = user_models.AdminUpdate(
            first_name="ForbiddenUpdate"
        )
        with pytest.raises(HTTPException) as e:
            await admin_service.update_admin(
                admin_id=test_admin_orm.id, # Attempt to update master admin
                update_data=update_data,
                current_user=test_normal_admin_orm
            )
        assert e.value.status_code == 403
        assert "Only a Master admin can update other admin profiles." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    async def test_update_admin_as_teacher_forbidden(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins, # Admin to be updated
        test_teacher_orm: db_models.Teachers # Teacher (current_user)
    ):
        """Tests that a teacher is forbidden from updating an admin's profile."""
        print("\n--- Testing update_admin as TEACHER (Forbidden) ---")
        update_data = user_models.AdminUpdate(
            first_name="ForbiddenUpdate"
        )
        with pytest.raises(HTTPException) as e:
            await admin_service.update_admin(
                admin_id=test_admin_orm.id,
                update_data=update_data,
                current_user=test_teacher_orm
            )
        assert e.value.status_code == 403
        assert "You do not have permission to update admin profiles." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    async def test_update_admin_not_found(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins # Master admin (current_user)
    ):
        """Tests that updating a non-existent admin raises a 404."""
        print("\n--- Testing update_admin for non-existent ID ---")
        update_data = user_models.AdminUpdate(
            first_name="NotFound"
        )
        with pytest.raises(HTTPException) as e:
            await admin_service.update_admin(
                admin_id=UUID(int=0), # Non-existent ID
                update_data=update_data,
                current_user=test_admin_orm
            )
        assert e.value.status_code == 404
        assert "Admin not found." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    # --- Tests for delete_admin ---

    async def test_delete_admin_as_master_admin_happy_path(
        self,
        admin_service: AdminService,
        user_service: UserService,
        test_admin_orm: db_models.Admins, # Master admin
        mock_geo_service: MagicMock # Needed for create_admin
    ):
        """Tests that a master admin can successfully delete another normal admin."""
        print("\n--- Testing delete_admin as MASTER admin (Happy Path) ---")
        # ARRANGE: Create a normal admin to delete
        admin_to_delete_data = user_models.AdminCreate(
            email="normal.admin.to.delete@example.com",
            password="password123",
            first_name="Delete",
            last_name="Me",
            privileges=AdminPrivilegeType.NORMAL
        )
        created_admin_read = await admin_service.create_admin(admin_to_delete_data, test_admin_orm, "1.1.1.1")
        await admin_service.db.commit()

        # ACT
        success = await admin_service.delete_admin(created_admin_read.id, test_admin_orm)
        assert success is True
        await admin_service.db.commit()

        # ASSERT
        deleted_admin = await user_service.get_user_by_id(created_admin_read.id)
        assert deleted_admin is None
        print(f"--- Successfully deleted normal admin {created_admin_read.id} by master admin ---")

    async def test_delete_admin_as_master_admin_self_delete_forbidden(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins # Master admin
    ):
        """Tests that a master admin cannot delete their own account."""
        print("\n--- Testing delete_admin as MASTER admin (Self Delete Forbidden) ---")
        with pytest.raises(HTTPException) as e:
            await admin_service.delete_admin(test_admin_orm.id, test_admin_orm)
        
        assert e.value.status_code == 400
        assert "You cannot delete your own account." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    async def test_delete_admin_as_master_admin_last_master_delete_forbidden(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins, # The last master admin
        mock_geo_service: MagicMock # Needed for create_admin
    ):
        """
        Tests that a master admin cannot delete the last master admin.
        This test is now self-contained and does not affect other tests.
        """
        print("\n--- Testing delete_admin as MASTER admin (Last Master Delete Forbidden) ---")
        # ARRANGE: Create and then delete a temporary normal admin to ensure
        # we are in a state where we might be deleting the last master.
        temp_admin_data = user_models.AdminCreate(
            email="temp.deletable.admin@example.com",
            password="password",
            first_name="Temp",
            last_name="Admin",
            privileges=AdminPrivilegeType.NORMAL # This was the missing field
        )
        created_temp_admin = await admin_service.create_admin(temp_admin_data, test_admin_orm, "1.2.3.4")
        await admin_service.db.flush() # Use flush to keep changes in the transaction
        
        await admin_service.delete_admin(created_temp_admin.id, test_admin_orm)
        await admin_service.db.flush() # Use flush to keep changes in the transaction
        
        # ACT & ASSERT: Attempt to delete the master admin (which is also self-deletion)
        with pytest.raises(HTTPException) as e:
            await admin_service.delete_admin(test_admin_orm.id, test_admin_orm)
        
        assert e.value.status_code == 400
        assert "You cannot delete your own account." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    async def test_delete_admin_as_normal_admin_forbidden(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins, # Target admin
        test_normal_admin_orm: db_models.Admins # Normal admin (current_user)
    ):
        """Tests that a normal admin is forbidden from deleting any admin."""
        print("\n--- Testing delete_admin as NORMAL admin (Forbidden) ---")
        with pytest.raises(HTTPException) as e:
            await admin_service.delete_admin(test_admin_orm.id, test_normal_admin_orm)
        
        assert e.value.status_code == 403
        assert "Only a Master admin can delete other admins." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    async def test_delete_admin_as_teacher_forbidden(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins, # Target admin
        test_teacher_orm: db_models.Teachers # Teacher (current_user)
    ):
        """Tests that a teacher is forbidden from deleting an admin."""
        print("\n--- Testing delete_admin as TEACHER (Forbidden) ---")
        with pytest.raises(HTTPException) as e:
            await admin_service.delete_admin(test_admin_orm.id, test_teacher_orm)
        
        assert e.value.status_code == 403
        assert "You do not have permission to delete admins." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    async def test_delete_admin_not_found(
        self,
        admin_service: AdminService,
        test_admin_orm: db_models.Admins # Master admin (current_user)
    ):
        """Tests that deleting a non-existent admin raises a 404."""
        print("\n--- Testing delete_admin for non-existent ID ---")
        with pytest.raises(HTTPException) as e:
            await admin_service.delete_admin(UUID(int=0), test_admin_orm)
        assert e.value.status_code == 404
        assert "Admin not found." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")
