"""
Test data for miscellaneous objects like Notes and TimetableRuns.
"""
import datetime
from tests.constants import TEST_NOTE_ID, TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_TUITION_ID
from src.efficient_tutor_backend.database.db_enums import SubjectEnum, NoteTypeEnum
import uuid

MISC_DATA = [
    # --- Notes ---
    {
        "factory": "NoteFactory",
        "name": "Forces",
        "id": TEST_NOTE_ID,
        "teacher_id": TEST_TEACHER_ID,
        "student_id": TEST_STUDENT_ID,
        "subject": SubjectEnum.PHYSICS.value,
        "note_type": NoteTypeEnum.STUDY_NOTES.value,
        "url": "www.goodnotes.com/some-doc"

    },
    {
        "factory": "NoteFactory",
        "name": "Momentum",
        "id": uuid.uuid4(),
        "teacher_id": TEST_TEACHER_ID,
        "student_id": TEST_STUDENT_ID,
        "subject": SubjectEnum.PHYSICS.value,
        "note_type": NoteTypeEnum.STUDY_NOTES.value,
        "url": "www.goodnotes.com/some-doc"

    },

    {
        "factory": "NoteFactory",
        "name": "Algebra",
        "id": uuid.uuid4(),
        "teacher_id": TEST_TEACHER_ID,
        "student_id": TEST_STUDENT_ID,
        "subject": SubjectEnum.MATH.value,
        "note_type": NoteTypeEnum.STUDY_NOTES.value,
        "url": "www.goodnotes.com/some-other-doc"

    },

    {
        "factory": "NoteFactory",
        "name": "Algebra HW",
        "id": uuid.uuid4(),
        "teacher_id": TEST_TEACHER_ID,
        "student_id": TEST_STUDENT_ID,
        "subject": SubjectEnum.MATH.value,
        "note_type": NoteTypeEnum.HOMEWORK.value,
        "url": "www.goodnotes.com/some-other-doc"

    },


    # --- Timetable Runs ---
    # This is more complex as it involves dynamic data (current time)
    # We can handle this by passing a callable or generating it in the seeder.
    # For now, we will define the static parts.
    {
        "factory": "TimetableRunFactory",
        # The solution_data will be generated dynamically in the seeder
    },
]
