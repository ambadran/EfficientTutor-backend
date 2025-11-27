"""
Test data for all user types: Admins, Teachers, Parents, and Students.
"""
from tests.constants import (
    TEST_ADMIN_ID, TEST_NORMAL_ADMIN_ID, TEST_TEACHER_ID, TEST_UNRELATED_TEACHER_ID,
    TEST_PARENT_ID, TEST_UNRELATED_PARENT_ID, TEST_STUDENT_ID, TEST_UNRELATED_STUDENT_ID, 
    TEST_PASSWORD_STUDENT
)
from src.efficient_tutor_backend.database.db_enums import AdminPrivilegeType

# The 'factory' key will be used by the seeder to know which factory to call.
# The rest of the keys are the arguments for that factory.
USERS_DATA = [
    # --- Admins ---
    {
        "factory": "AdminFactory",
        "id": TEST_ADMIN_ID,
        "email": "master.admin@example.com",
        "first_name": "Master",
        "last_name": "Admin",
        "privileges": AdminPrivilegeType.MASTER.value,
    },
    {
        "factory": "AdminFactory",
        "id": TEST_NORMAL_ADMIN_ID,
        "email": "normal.admin@example.com",
        "first_name": "Normal",
        "last_name": "Admin",
        "privileges": AdminPrivilegeType.NORMAL.value,
    },
    # --- Teachers ---
    {
        "factory": "TeacherFactory",
        "id": TEST_TEACHER_ID,
        "email": "test.teacher@example.com",
        "first_name": "Test",
        "last_name": "Teacher",
    },
    {
        "factory": "TeacherFactory",
        "id": TEST_UNRELATED_TEACHER_ID,
        "email": "unrelated.teacher@example.com",
        "first_name": "Unrelated",
        "last_name": "Teacher",
    },
    # --- Parents ---
    {
        "factory": "ParentFactory",
        "id": TEST_PARENT_ID,
        "email": "test.parent@example.com",
        "first_name": "Test",
        "last_name": "Parent",
    },
    {
        "factory": "ParentFactory",
        "id": TEST_UNRELATED_PARENT_ID,
        "email": "unrelated.parent@example.com",
        "first_name": "Unrelated",
        "last_name": "Parent",
    },
    # --- Students ---
    # Note: Students have a dependency on a parent. We will handle this
    # in the seeder script by creating users in order and passing the
    # created parent object. For now, we define the relationship by ID.
    {
        "factory": "StudentFactory",
        "id": TEST_STUDENT_ID,
        "grade": 10,
        "email": "test.student@example.com",
        "first_name": "Test",
        "last_name": "Student",
        "parent_id": TEST_PARENT_ID, # Define the relationship
        "generated_password": TEST_PASSWORD_STUDENT
    },
    {
        "factory": "StudentFactory",
        "id": TEST_UNRELATED_STUDENT_ID,
        "grade": 10,
        "email": "unrelated.student@example.com",
        "first_name": "Unrelated",
        "last_name": "Student",
        "parent_id": TEST_UNRELATED_PARENT_ID, # This is the crucial link
        "generated_password": TEST_PASSWORD_STUDENT
    },
]
