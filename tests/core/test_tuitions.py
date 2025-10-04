'''
Testing all the core tuitions module functionalities
'''
import pytest
from tests.constants import *
from efficient_tutor_backend.core.tuitions import Tuitions

from pprint import pprint

def test_tuitions_initialization(tuitions: Tuitions):
    """
    A simple test to ensure the Tuitions service and its dependencies
    are instantiated correctly.
    """
    assert tuitions is not None
    assert tuitions.db is not None
    assert tuitions.students_service is not None

def test_tuitions_get_all_for_teacher(tuitions: Tuitions):
    all_tuitions = tuitions.get_all(TEST_TEACHER_ID)
    print(f"Got {len(all_tuitions)} {type(all_tuitions[0])} objects for teacher user.\nExample:\n")
    print(all_tuitions[0])

def test_tuitions_get_all_for_parent(tuitions: Tuitions):
    all_tuitions = tuitions.get_all(TEST_PARENT_ID)
    print(f"Got {len(all_tuitions)} {type(all_tuitions[0])} objects for parent user.\nExample:\n")
    print(all_tuitions[0])

def test_tuitions_get_all_for_student(tuitions: Tuitions):
    all_tuitions = tuitions.get_all(TEST_STUDENT_ID)
    print(f"Got {len(all_tuitions)} {type(all_tuitions[0])} objects for student user.\nExample:\n")
    print(all_tuitions[0])

def test_tuitions_get_by_id(tuitions: Tuitions):
    tuition = tuitions.get_by_id(TEST_TUITION_ID)
    print(f"Found {type(tuition)} type object.\n{tuition}")
