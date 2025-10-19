'''
testing the api endpoints
'''
import pytest

from tests.constants import TEST_PARENT_ID, TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_PARENT_IDS

from pprint import pp as pprint

def test_get_schedulable_tuitions(client):

    # Test 1: testing no viewer_id
    response = client.get('/schedulable-tuitions')
    print(f"\n=== GET /schedulable-tuitions No user RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print("===================================\n")
    assert response.status_code == 400

    # Test 2: testing teacher user
    response = client.get(f'/schedulable-tuitions?viewer_id={TEST_TEACHER_ID}')
    print(f"\n=== GET /schedulable-tuitions Teacher User RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON:")
    pprint(response.get_json())
    print("===================================\n")
    assert response.status_code == 200
    assert isinstance(response.get_json(), list)
    
    # Test 3: testing parent user
    response = client.get(f'/schedulable-tuitions?viewer_id={TEST_PARENT_ID}')
    print(f"\n=== GET /schedulable-tuitions Parent User RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON:")
    pprint(response.get_json())
    print("===================================\n")
    assert response.status_code == 200
    assert isinstance(response.get_json(), list)

    # Test 4: testing student user
    response = client.get(f'/schedulable-tuitions?viewer_id={TEST_STUDENT_ID}')
    print(f"\n=== GET /schedulable-tuitions Student User RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON:")
    pprint(response.get_json())
    print("===================================\n")
    assert response.status_code == 200
    assert isinstance(response.get_json(), list)
 

