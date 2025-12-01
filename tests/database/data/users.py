"""
Test data for all user types: Admins, Teachers, Parents, and Students.
"""
from tests.constants import (
    TEST_ADMIN_ID, TEST_NORMAL_ADMIN_ID, TEST_TEACHER_ID, TEST_UNRELATED_TEACHER_ID,
    TEST_PARENT_ID, TEST_UNRELATED_PARENT_ID, TEST_STUDENT_ID, TEST_UNRELATED_STUDENT_ID, 
    TEST_PASSWORD_STUDENT
)
from src.efficient_tutor_backend.database.db_enums import AdminPrivilegeType

# --- Admins ---
ADMINS_DATA = [
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
]

# --- Teachers ---
TEACHERS_DATA = [
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
]

# --- Parents ---
PARENTS_DATA = [
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
]

# --- Students ---
STUDENTS_DATA = [
    {
        "factory": "RawStudentFactory",
        "id": TEST_STUDENT_ID,
        "grade": 10,
        "email": "test.student@example.com",
        "first_name": "Test",
        "last_name": "Student",
        "parent_id": TEST_PARENT_ID, 
        "generated_password": TEST_PASSWORD_STUDENT
    },
    {
        "factory": "RawStudentFactory",
        "id": TEST_UNRELATED_STUDENT_ID,
        "grade": 10,
        "email": "unrelated.student@example.com",
        "first_name": "Unrelated",
        "last_name": "Student",
        "parent_id": TEST_UNRELATED_PARENT_ID, 
        "generated_password": TEST_PASSWORD_STUDENT
    },
]
