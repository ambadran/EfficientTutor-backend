"""
Standalone script to seed the test database with deterministic data.

Run this script directly to wipe and repopulate the test database.
It will print the UUIDs of the created objects, which should be copied
into `tests/constants.py` to ensure tests are pointing to the correct data.

Instructions:
1. Make sure your .env file is configured for the TEST database.
2. Run the script: `uv run python -m tests.seed_test_db`
3. Copy the printed UUIDs and other constants into `tests/constants.py`.
4. Set the passwords in `tests/constants.py` to the values printed below.
"""

import asyncio
import uuid
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os

# Temporarily set the TEST_MODE environment variable
os.environ["TEST_MODE"] = "True"

# Now, import from the application
from src.efficient_tutor_backend.common.config import settings
from src.efficient_tutor_backend.database import models as db_models
from tests.database import factories
from datetime import time
from src.efficient_tutor_backend.database.db_enums import (
    SubjectEnum, AvailabilityTypeEnum, TuitionLogCreateTypeEnum, AdminPrivilegeType
)
from tests.constants import (
    TEST_ADMIN_ID, TEST_NORMAL_ADMIN_ID, TEST_TEACHER_ID, TEST_UNRELATED_TEACHER_ID, TEST_PARENT_ID, TEST_UNRELATED_PARENT_ID,
    TEST_STUDENT_ID, TEST_TUITION_ID, TEST_TUITION_ID_NO_LINK, TEST_NOTE_ID,
    TEST_TUITION_LOG_ID_SCHEDULED, TEST_TUITION_LOG_ID_CUSTOM, TEST_PAYMENT_LOG_ID
)


async def clear_database(session: AsyncSession):
    """Wipes all data from public tables."""
    print("Wiping database...")
    async with session.begin():
        # The order is important to respect foreign key constraints
        await session.execute(text('TRUNCATE TABLE "timetable_runs" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "tuition_log_charges" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "tuition_logs" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "payment_logs" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "notes" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "meeting_links" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "tuition_template_charges" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "tuitions" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "student_subjects" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "student_availability_intervals" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "users" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "admins" RESTART IDENTITY CASCADE'))
    print("Database wiped.")

async def seed_data(session: AsyncSession):
    """Seeds the database with a known set of data."""
    print("Seeding data...")

    # Set the session for factory-boy
    factories.test_db_session = session

    # --- Create Admins ---
    factories.AdminFactory.create(id=TEST_ADMIN_ID) # Master admin (default)
    factories.AdminFactory.create(
        id=TEST_NORMAL_ADMIN_ID,
        email="normal.admin@example.com",
        first_name="Normal",
        last_name="Admin",
        privileges=AdminPrivilegeType.NORMAL.value
    )

    # --- Create Users ---
    teacher = factories.TeacherFactory.create(id=TEST_TEACHER_ID)
    unrelated_teacher = factories.TeacherFactory.create(
        id=TEST_UNRELATED_TEACHER_ID, 
        email="unrelated.teacher@example.com"
    )
    
    parent = factories.ParentFactory.create(
        id=TEST_PARENT_ID, 
        email="test.parent@example.com"
    )
    unrelated_parent = factories.ParentFactory.create(
        id=TEST_UNRELATED_PARENT_ID, 
        email="unrelated.parent@example.com"
    )
    factories.StudentFactory.create(
        email="unrelated.student@example.com",
        parent=unrelated_parent
    )

    student = factories.StudentFactory.create(
        id=TEST_STUDENT_ID,
        email="test.student@example.com",
        parent=parent
    )

    # --- Create initial data for the student to satisfy test pre-conditions ---
    factories.StudentSubjectFactory.create(
        student=student,
        teacher=teacher,
        subject=SubjectEnum.PHYSICS.value
    )
    factories.StudentAvailabilityIntervalFactory.create(
        student=student,
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(17, 0),
        availability_type=AvailabilityTypeEnum.SCHOOL.value
    )

    # --- Create Tuitions ---
    tuition = factories.TuitionFactory.create(
        id=TEST_TUITION_ID,
        teacher=teacher
    )
    
    tuition_no_link = factories.TuitionFactory.create(
        id=TEST_TUITION_ID_NO_LINK,
        teacher=teacher 
    )

    # --- Create Objects for Fixtures ---

    # For `test_tuition_orm`
    factories.MeetingLinkFactory.create(tuition=tuition)
    factories.TuitionTemplateChargeFactory.create(
        tuition=tuition,
        student=student,
        parent=parent
    )
    factories.TuitionTemplateChargeFactory.create(
        tuition=tuition_no_link,
        student=student,
        parent=parent
    )

    # For `tuition_log_scheduled`
    log_scheduled = factories.TuitionLogFactory.create(
        id=TEST_TUITION_LOG_ID_SCHEDULED,
        create_type=TuitionLogCreateTypeEnum.SCHEDULED.value,
        tuition=tuition,
        teacher=teacher
    )
    factories.TuitionLogChargeFactory.create(
        tuition_log=log_scheduled,
        student=student,
        parent=parent
    )

    # For `tuition_log_custom`
    log_custom = factories.TuitionLogFactory.create(
        id=TEST_TUITION_LOG_ID_CUSTOM,
        create_type=TuitionLogCreateTypeEnum.CUSTOM.value,
        tuition=tuition,
        teacher=teacher
    )
    factories.TuitionLogChargeFactory.create(
        tuition_log=log_custom,
        student=student,
        parent=parent
    )

    # For `payment_log_orm`
    factories.PaymentLogFactory.create(
        id=TEST_PAYMENT_LOG_ID,
        parent=parent,
        teacher=teacher
    )

    # For `test_note_orm`
    factories.NoteFactory.create(
        id=TEST_NOTE_ID,
        teacher=teacher,
        student=student
    )

    # --- Create Timetable Run ---
    now = datetime.datetime.now(datetime.timezone.utc)
    solution_data = [
        {
            "category": "Tuition",
            "id": str(TEST_TUITION_ID),
            "start_time": now.isoformat(),
            "end_time": (now + datetime.timedelta(hours=1)).isoformat()
        }
    ]
    factories.TimetableRunFactory.create(solution_data=solution_data)
    
    await session.commit()
    print("Data seeding complete.")


async def main():
    """Main function to connect, wipe, and seed the database."""
    if not settings.TEST_MODE:
        raise ConnectionRefusedError(
            "Seeding script must be run with TEST_MODE=True in your environment "
            "to prevent accidental deletion of production data."
        )

    engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as session:
        await clear_database(session)
        await seed_data(session)

    await engine.dispose()
    print("\nDatabase seeding complete. All constants are now managed in tests/constants.py")


if __name__ == "__main__":
    # to run this script use
    # `uv run python -m tests.database.seed_test_db`
    # it's supposed to delete all the data of the database and introduced the data definined here.
    asyncio.run(main())
