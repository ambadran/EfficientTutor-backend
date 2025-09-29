'''

'''
from efficient_tutor_backend.core.users import Users, Parents, Teachers, Students
from pprint import pprint

def test_users_service_initialization(users: Users):
    """
    Tests if the Users service can be instantiated correctly.
    """
    assert users is not None
    assert users.db is not None

def test_parents_get_all(parents: Parents):
    pprint(parents.get_all())

def test_teachers_get_all(teachers: Teachers):
    pprint(teachers.get_all())

def test_students_get_all(students: Students):
    pprint(students.get_all())
