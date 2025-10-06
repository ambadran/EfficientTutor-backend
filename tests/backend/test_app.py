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
 
def test_get_custom_log_entry_data(client):

    # Test 1: testing no viewer_id
    response = client.get('/custom-log-entry-data')
    print(f"\n=== GET /custom-log-entry-data no user RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print("===================================\n")
    assert response.status_code == 400

    # Test 2: testing parent user
    response = client.get(f'/custom-log-entry-data?viewer_id={TEST_PARENT_ID}')
    print(f"\n=== GET /custom-log-entry-data Parent user RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print("===================================\n")
    assert response.status_code == 401
 
    # Test 2: testing teacher user
    response = client.get(f'/custom-log-entry-data?viewer_id={TEST_TEACHER_ID}')
    print(f"\n=== GET /custom-log-entry-data Teacher User RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON:")
    pprint(response.get_json())
    print("===================================\n")
    assert response.status_code == 200
    assert isinstance(response.get_json(), dict)
 

def test_get_parent_list_for_teacher(client):
    response = client.get('/parent-list?viewer_id=dcef54de-bc89-4388-a7a8-dba5d8327447')

    print(f"\n=== GET /parent-list? Teacher ID RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON 1 example:")
    pprint(response.get_json())
    print("===================================\n")

    assert response.status_code == 200
    assert isinstance(response.get_json(), dict)


def test_get_all_payment_logs(client):
    response = client.get('/payment-logs?viewer_id=dcef54de-bc89-4388-a7a8-dba5d8327447')

    print(f"\n=== GET /tuition-logs RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON:")
    pprint(response.get_json())
    print("===================================\n")

    #TODO: test with a student id and must return unauthorized
        

    assert response.status_code == 200
    assert isinstance(response.get_json(), list)


def test_get_financial_report(client):
    response = client.get('/financial-report/d4c17e60-08de-47c7-9ef0-33ae8aa442fb')

    print(f"\n=== GET /financial-report/ RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON:")
    pprint(response.get_json())
    print("===================================\n")
