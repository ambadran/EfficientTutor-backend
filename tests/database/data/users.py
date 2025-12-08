"""
Test data for all user types: Admins, Teachers, Parents, and Students.
"""
from tests.constants import (
    TEST_ADMIN_ID, TEST_NORMAL_ADMIN_ID, TEST_TEACHER_ID, TEST_UNRELATED_TEACHER_ID,
    TEST_PARENT_ID, TEST_UNRELATED_PARENT_ID, TEST_STUDENT_ID, TEST_UNRELATED_STUDENT_ID, 
    TEST_PASSWORD_STUDENT, TEST_DELETABLE_TEACHER_ID,
    FIN_TEACHER_A_ID, FIN_TEACHER_B_ID,
    FIN_PARENT_A_ID, FIN_PARENT_B_ID,
    FIN_STUDENT_A1_ID, FIN_STUDENT_A2_ID, FIN_STUDENT_B1_ID
)
from src.efficient_tutor_backend.database.db_enums import AdminPrivilegeType, EducationalSystemEnum

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
    {
        "factory": "TeacherFactory",
        "id": TEST_DELETABLE_TEACHER_ID,
        "email": "deletable.teacher@example.com",
        "first_name": "Deletable",
        "last_name": "Teacher",
    },
    # Financial Sandbox Teachers
    {
        "factory": "TeacherFactory",
        "id": FIN_TEACHER_A_ID,
        "email": "fin.teacher.a@example.com",
        "first_name": "Fin",
        "last_name": "TeacherA",
    },
    {
        "factory": "TeacherFactory",
        "id": FIN_TEACHER_B_ID,
        "email": "fin.teacher.b@example.com",
        "first_name": "Fin",
        "last_name": "TeacherB",
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
    # Financial Sandbox Parents
    {
        "factory": "ParentFactory",
        "id": FIN_PARENT_A_ID,
        "email": "fin.parent.a@example.com",
        "first_name": "Fin",
        "last_name": "ParentA",
    },
    {
        "factory": "ParentFactory",
        "id": FIN_PARENT_B_ID,
        "email": "fin.parent.b@example.com",
        "first_name": "Fin",
        "last_name": "ParentB",
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
        "generated_password": TEST_PASSWORD_STUDENT,
        "educational_system": EducationalSystemEnum.IGCSE.value
    },
    {
        "factory": "RawStudentFactory",
        "id": TEST_UNRELATED_STUDENT_ID,
        "grade": 10,
        "email": "unrelated.student@example.com",
        "first_name": "Unrelated",
        "last_name": "Student",
        "parent_id": TEST_UNRELATED_PARENT_ID, 
        "generated_password": TEST_PASSWORD_STUDENT,
        "educational_system": EducationalSystemEnum.IGCSE.value
    },
    # Financial Sandbox Students
    {
        "factory": "RawStudentFactory",
        "id": FIN_STUDENT_A1_ID,
        "grade": 10,
        "email": "fin.student.a1@example.com",
        "first_name": "Fin",
        "last_name": "StudentA1",
        "parent_id": FIN_PARENT_A_ID, 
        "generated_password": TEST_PASSWORD_STUDENT,
        "educational_system": EducationalSystemEnum.IGCSE.value
    },
    {
        "factory": "RawStudentFactory",
        "id": FIN_STUDENT_A2_ID,
        "grade": 10,
        "email": "fin.student.a2@example.com",
        "first_name": "Fin",
        "last_name": "StudentA2",
        "parent_id": FIN_PARENT_A_ID, 
        "generated_password": TEST_PASSWORD_STUDENT,
        "educational_system": EducationalSystemEnum.IGCSE.value
    },
    {
        "factory": "RawStudentFactory",
        "id": FIN_STUDENT_B1_ID,
        "grade": 10,
        "email": "fin.student.b1@example.com",
        "first_name": "Fin",
        "last_name": "StudentB1",
        "parent_id": FIN_PARENT_B_ID, 
        "generated_password": TEST_PASSWORD_STUDENT,
        "educational_system": EducationalSystemEnum.IGCSE.value
    },
]