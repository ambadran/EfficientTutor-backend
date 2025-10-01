'''
testing the api endpoints
'''
import pytest

from pprint import pp as pprint

def test_get_all_tuition_logs(client):
    response = client.get('/tuition-logs?viewer_id=dcef54de-bc89-4388-a7a8-dba5d8327447')

    print(f"\n=== GET /tuition-logs RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON:")
    pprint(response.get_json())
    print("===================================\n")

    #TODO: test with a student id and must return unauthorized
        

    assert response.status_code == 200
    assert isinstance(response.get_json(), list)

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


def test_get_schedulable_tuitions(client):
    response = client.get('/schedulable-tuitions')

    print(f"\n=== GET /schedulable-tuitions RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON:")
    pprint(response.get_json())
    print("===================================\n")
 
def test_get_manual_entry_data(client):
    response = client.get('/manual-entry-data')

    print(f"\n=== GET /manual-entry-data RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON:")
    pprint(response.get_json())
    print("===================================\n")

def test_get_financial_report(client):
    response = client.get('/financial-report/d4c17e60-08de-47c7-9ef0-33ae8aa442fb')

    print(f"\n=== GET /financial-report/ RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON:")
    pprint(response.get_json())
    print("===================================\n")
