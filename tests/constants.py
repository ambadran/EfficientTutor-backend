from uuid import UUID
import sys

TEST_PARENT_ID = UUID('e850ce9b-d934-47b9-a029-b510f39d5bbc')
TEST_TEACHER_ID = UUID('dcef54de-bc89-4388-a7a8-dba5d8327447')
TEST_STUDENT_ID = UUID('e46d56d4-a856-49cc-b078-bffa79d9a142')
TEST_PARENT_IDS = [UUID('e850ce9b-d934-47b9-a029-b510f39d5bbc'),
                         UUID('d4c17e60-08de-47c7-9ef0-33ae8aa442fb'),
                         UUID('7accbce5-4cdd-4ca3-930f-b0042e035299'),
                         UUID('a6934e55-9538-4c06-a7b0-545fbd4d8cee'),
                         UUID('eca287cc-2774-43d6-bef8-8f2d75ad11cf')]

TEST_TUITION_ID = UUID('026ce9a5-eded-480f-b98c-a62b459807aa')
TEST_TUITION_LOG_ID_SCHEDULED = UUID('d3bff492-2d0c-4fce-a65b-a58107d125ec')
TEST_TUITION_LOG_ID_CUSTOM = UUID('8bb36a2a-fed8-4908-a4fa-32ea960a8335')

TEST_PAYMENT_LOG_ID = UUID('d5dcf3b2-d166-4fd0-890d-3553bf2eca57')

if sys.platform == 'linux':
    TEST_NOTE_ID=UUID('b61ff351-2115-4008-899e-ee48a706e82a')  # linux
elif sys.platform == 'darwin':
    TEST_NOTE_ID=UUID('60ea094c-28ec-4994-adb7-44b773ad8f21') # MacOS
else:
    raise ValueError("didn't create TEST_NOTE_ID for this device")


if sys.platform == 'linux':
    TEST_UNRELATED_TEACHER_ID=UUID('6667e14b-f8b7-45ee-998a-48832413d4c7')
elif sys.platform == 'darwin':
    TEST_UNRELATED_TEACHER_ID=UUID('78280aae-2a09-4e11-ab25-bad18965c95d')
else:
    raise ValueError("didn't create TEST_UNRELATED_TEACHER_ID for this device")

TEST_UNRELATED_PARENT_ID = UUID('d4c17e60-08de-47c7-9ef0-33ae8aa442fb')

TEST_TUITION_ID_NO_LINK = UUID('80194ca6-fb6a-422a-bdb8-63e64e23e79e')

