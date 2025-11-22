
from tests.constants import TEST_TEACHER_ID, TEST_UNRELATED_TEACHER_ID
from src.efficient_tutor_backend.database.db_enums import SubjectEnum, EducationalSystemEnum

TEACHER_SPECIALTIES_DATA = [
    {
        "factory": "TeacherSpecialtyFactory",
        "teacher_id": TEST_TEACHER_ID,
        "subject": SubjectEnum.PHYSICS.value,
        "educational_system": EducationalSystemEnum.IGCSE.value,
    },
    {
        "factory": "TeacherSpecialtyFactory",
        "teacher_id": TEST_TEACHER_ID,
        "subject": SubjectEnum.MATH.value,
        "educational_system": EducationalSystemEnum.IGCSE.value,
    },
    {
        "factory": "TeacherSpecialtyFactory",
        "teacher_id": TEST_TEACHER_ID,
        "subject": SubjectEnum.CHEMISTRY.value,
        "educational_system": EducationalSystemEnum.IGCSE.value,
    },
    {
        "factory": "TeacherSpecialtyFactory",
        "teacher_id": TEST_UNRELATED_TEACHER_ID,
        "subject": SubjectEnum.MATH.value,
        "educational_system": EducationalSystemEnum.IGCSE.value,
    },
    {
        "factory": "TeacherSpecialtyFactory",
        "teacher_id": TEST_UNRELATED_TEACHER_ID,
        "subject": SubjectEnum.PHYSICS.value,
        "educational_system": EducationalSystemEnum.IGCSE.value,
    },
    {
        "factory": "TeacherSpecialtyFactory",
        "teacher_id": TEST_UNRELATED_TEACHER_ID,
        "subject": SubjectEnum.MATH.value,
        "educational_system": EducationalSystemEnum.SAT.value,
    },
    {
        "factory": "TeacherSpecialtyFactory",
        "teacher_id": TEST_UNRELATED_TEACHER_ID,
        "subject": SubjectEnum.PHYSICS.value,
        "educational_system": EducationalSystemEnum.SAT.value,
    },


]
