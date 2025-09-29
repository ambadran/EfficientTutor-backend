'''
Testing all the core tuitions module functionalities
'''
import pytest
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

def test_tuitions_get_all(tuitions: Tuitions):
    pprint(tuitions.get_all())
