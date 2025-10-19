


def test_get_parent_list_for_teacher(client):
    response = client.get('/parent-list?viewer_id=dcef54de-bc89-4388-a7a8-dba5d8327447')

    print(f"\n=== GET /parent-list? Teacher ID RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON 1 example:")
    pprint(response.get_json())
    print("===================================\n")

    assert response.status_code == 200
    assert isinstance(response.get_json(), dict)



