"""
Test data for Notes.
"""
from tests.constants import TEST_NOTE_ID, TEST_TEACHER_ID, TEST_STUDENT_ID
from src.efficient_tutor_backend.database.db_enums import SubjectEnum, NoteTypeEnum
import uuid

# --- Notes ---
NOTES_DATA = [
    {
        "factory": "RawNoteFactory",
        "name": "Forces",
        "id": TEST_NOTE_ID,
        "teacher_id": TEST_TEACHER_ID,
        "student_id": TEST_STUDENT_ID,
        "subject": SubjectEnum.PHYSICS.value,
        "note_type": NoteTypeEnum.STUDY_NOTES.value,
        "url": "www.goodnotes.com/some-doc"

    },
    {
        "factory": "RawNoteFactory",
        "name": "Momentum",
        "id": uuid.uuid4(),
        "teacher_id": TEST_TEACHER_ID,
        "student_id": TEST_STUDENT_ID,
        "subject": SubjectEnum.PHYSICS.value,
        "note_type": NoteTypeEnum.STUDY_NOTES.value,
        "url": "www.goodnotes.com/some-doc"

    },

    {
        "factory": "RawNoteFactory",
        "name": "Algebra",
        "id": uuid.uuid4(),
        "teacher_id": TEST_TEACHER_ID,
        "student_id": TEST_STUDENT_ID,
        "subject": SubjectEnum.MATH.value,
        "note_type": NoteTypeEnum.STUDY_NOTES.value,
        "url": "www.goodnotes.com/some-other-doc"

    },

    {
        "factory": "RawNoteFactory",
        "name": "Algebra HW",
        "id": uuid.uuid4(),
        "teacher_id": TEST_TEACHER_ID,
        "student_id": TEST_STUDENT_ID,
        "subject": SubjectEnum.MATH.value,
        "note_type": NoteTypeEnum.HOMEWORK.value,
        "url": "www.goodnotes.com/some-other-doc"

    },
]
