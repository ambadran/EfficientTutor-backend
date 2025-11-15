"""
Defines factory-boy factories for creating test data.

These factories are used by the `seed_test_db.py` script to populate the
test database with a known, deterministic set of data.
"""

import factory
import uuid
import datetime
from factory.alchemy import SQLAlchemyModelFactory
from factory.faker import Faker

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.database.db_enums import (
    UserRole, AdminPrivilegeType, SubjectEnum, MeetingLinkTypeEnum, 
    NoteTypeEnum, LogStatusEnum, TuitionLogCreateTypeEnum, AvailabilityTypeEnum,
    RunStatusEnum
)
from src.efficient_tutor_backend.common.security_utils import HashedPassword
from tests.constants import TEST_PASSWORD_ADMIN, TEST_PASSWORD_PARENT, TEST_PASSWORD_STUDENT, TEST_PASSWORD_TEACHER

# This is a placeholder for the actual session from the seeding script
# It will be set dynamically by the script before the factories are used.
test_db_session = None

class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "flush"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # This ensures the session is set before any factory is used
        if test_db_session is None:
            raise RuntimeError(
                "The 'test_db_session' global must be set in your seeding script before using factories."
            )
        cls._meta.sqlalchemy_session = test_db_session
        return super()._create(model_class, *args, **kwargs)


class AdminFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    email = Faker("email")
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    role = UserRole.ADMIN.value
    privileges = AdminPrivilegeType.MASTER.value
    timezone = "UTC"
    password = HashedPassword.get_hash(TEST_PASSWORD_ADMIN)

    class Meta:
        model = db_models.Admins

class TeacherFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    email = Faker("email")
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    role = UserRole.TEACHER.value
    timezone = "UTC"
    currency = "USD"
    password = HashedPassword.get_hash(TEST_PASSWORD_TEACHER)

    class Meta:

        model = db_models.Teachers

class ParentFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    email = Faker("email")
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    role = UserRole.PARENT.value
    timezone = "UTC"
    currency = "USD"
    password = HashedPassword.get_hash(TEST_PASSWORD_PARENT)

    class Meta:
        model = db_models.Parents

class StudentFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    email = Faker("email")
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    role = UserRole.STUDENT.value
    timezone = "UTC"
    password = HashedPassword.get_hash(TEST_PASSWORD_STUDENT)
    parent_id = factory.SelfAttribute('parent.id')
    parent = factory.SubFactory(ParentFactory)

    class Meta:
        model = db_models.Students

class TuitionFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    subject = SubjectEnum.MATH.value
    lesson_index = 1
    min_duration_minutes = 60
    max_duration_minutes = 90
    teacher = factory.SubFactory(TeacherFactory)

    class Meta:
        model = db_models.Tuitions

class MeetingLinkFactory(BaseFactory):
    meeting_link_type = MeetingLinkTypeEnum.GOOGLE_MEET.value
    meeting_link = "https://meet.google.com/test-link"
    tuition = factory.SubFactory(TuitionFactory)

    class Meta:
        model = db_models.MeetingLinks

class TimetableRunFactory(BaseFactory):
    run_started_at = factory.LazyFunction(datetime.datetime.now)
    status = RunStatusEnum.SUCCESS.value
    input_version_hash = "test_hash"
    solution_data = []

    class Meta:
        model = db_models.TimetableRuns

class NoteFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    name = "Test Note"
    subject = SubjectEnum.MATH.value
    note_type = NoteTypeEnum.STUDY_NOTES.value
    description = "This is a test note."
    teacher = factory.SubFactory(TeacherFactory)
    student = factory.SubFactory(StudentFactory)

    class Meta:
        model = db_models.Notes

class PaymentLogFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    payment_date = factory.LazyFunction(datetime.datetime.now)
    amount_paid = 50.00
    status = LogStatusEnum.ACTIVE.value
    parent = factory.SubFactory(ParentFactory)
    teacher = factory.SubFactory(TeacherFactory)

    class Meta:
        model = db_models.PaymentLogs

class TuitionLogFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    subject = SubjectEnum.MATH.value
    start_time = factory.LazyFunction(datetime.datetime.now)
    end_time = factory.LazyFunction(lambda: datetime.datetime.now() + datetime.timedelta(hours=1))
    status = LogStatusEnum.ACTIVE.value
    create_type = TuitionLogCreateTypeEnum.CUSTOM.value
    tuition = factory.SubFactory(TuitionFactory)
    teacher = factory.SubFactory(TeacherFactory)

    class Meta:
        model = db_models.TuitionLogs

class TuitionTemplateChargeFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    cost = 100.00
    tuition = factory.SubFactory(TuitionFactory)
    student = factory.SubFactory(StudentFactory)
    parent = factory.SubFactory(ParentFactory)

    class Meta:
        model = db_models.TuitionTemplateCharges

class TuitionLogChargeFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    cost = 120.00
    tuition_log = factory.SubFactory(TuitionLogFactory)
    student = factory.SubFactory(StudentFactory)
    parent = factory.SubFactory(ParentFactory)

    class Meta:
        model = db_models.TuitionLogCharges

class StudentSubjectFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    subject = SubjectEnum.PHYSICS.value
    lessons_per_week = 2

    student = factory.SubFactory(StudentFactory)
    teacher = factory.SubFactory(TeacherFactory)

    class Meta:
        model = db_models.StudentSubjects

class StudentAvailabilityIntervalFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    day_of_week = 1
    start_time = datetime.time(9, 0)
    end_time = datetime.time(17, 0)
    availability_type = AvailabilityTypeEnum.SCHOOL.value

    student = factory.SubFactory(StudentFactory)

    class Meta:
        model = db_models.StudentAvailabilityIntervals

