'''

'''
from uuid import UUID
from tests.constants import TEST_PARENT_ID, TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_PARENT_IDS
from efficient_tutor_backend.core.users import Users, Parents, Teachers, Students
from pprint import pprint

def test_users_service_initialization(users: Users):
    """
    Tests if the Users service can be instantiated correctly.
    """
    assert users is not None
    assert users.db is not None

def test_parents_get_all(parents: Parents):
    all_parents = parents.get_all()
    print(f"No Parent Users: {len(all_parents)}")
    print(all_parents[0])

def test_teachers_get_all(teachers: Teachers):
    all_teachers = teachers.get_all()
    print(f"No Teacher Users: {len(all_teachers)}")
    print(all_teachers)

def test_students_get_all_for_teacher(students: Students):
    all_students = students.get_all(TEST_TEACHER_ID)
    print(f"No Student Users for api: {len(all_students)}")
    print(all_students[0])

def test_students_get_all_for_parent(students: Students):
    all_students = students.get_all(TEST_PARENT_ID)
    print(f"No Student Users for api: {len(all_students)}")
    print(all_students[0])

def test_parents_get_all_for_api(parents: Parents):
    all_parents = parents.get_all_for_api(UUID('dcef54de-bc89-4388-a7a8-dba5d8327447'))
    print(f"No Parent Users for api: {len(all_parents)}")
    print(all_parents[0])

def test_teachers_get_all_for_api(teachers: Teachers):
    all_teachers = teachers.get_all_for_api()
    print(f"No Teacher Users for api: {len(all_teachers)}")
    print(all_teachers[0])

def test_students_get_all_for_api_for_teacher(students: Students):
    all_students = students.get_all_for_api(TEST_TEACHER_ID)
    print(f"No Student Users for api: {len(all_students)}")
    pprint(all_students)

def test_students_get_all_for_api_for_parent(students: Students):
    all_students = students.get_all_for_api(TEST_PARENT_ID)
    print(f"No Student Users for api: {len(all_students)}")
    pprint(all_students)


