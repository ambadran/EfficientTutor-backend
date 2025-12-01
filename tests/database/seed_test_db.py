"""
Standalone script to seed the test database with deterministic data.
This script orchestrates the seeding process by reading data definitions
from the `tests/database/data/` directory.
"""

import asyncio
import uuid
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os

# --- Setup & Imports ---
os.environ["TEST_MODE"] = "True"

from src.efficient_tutor_backend.common.config import settings
from src.efficient_tutor_backend.database import models as db_models
from tests.database import factories
from tests.constants import TEST_TUITION_ID

# --- Import Data Definitions ---
from .data.users import ADMINS_DATA, TEACHERS_DATA, PARENTS_DATA, STUDENTS_DATA
from .data.teacher_specialties import TEACHER_SPECIALTIES_DATA
from .data.tuitions import TUITIONS_DATA, MEETING_LINKS_DATA, TUITION_TEMPLATE_CHARGES_DATA
from .data.student_details import STUDENT_DETAILS_DATA 
from .data.logs import TUITION_LOGS_DATA, TUITION_LOG_CHARGES_DATA, PAYMENT_LOGS_DATA
from .data.misc import NOTES_DATA, TIMETABLE_RUNS_DATA

# --- Seeding Topology ---
SEEDING_ORDER = [
    ("Admins", ADMINS_DATA),
    ("Teachers", TEACHERS_DATA),
    ("Parents", PARENTS_DATA),
    ("Students", STUDENTS_DATA),
    ("TeacherSpecialties", TEACHER_SPECIALTIES_DATA),
    ("StudentDetails", STUDENT_DETAILS_DATA),
    ("Tuitions", TUITIONS_DATA),
    ("MeetingLinks", MEETING_LINKS_DATA),
    ("TuitionTemplateCharges", TUITION_TEMPLATE_CHARGES_DATA),
    ("TuitionLogs", TUITION_LOGS_DATA),
    ("TuitionLogCharges", TUITION_LOG_CHARGES_DATA),
    ("PaymentLogs", PAYMENT_LOGS_DATA),
    ("Notes", NOTES_DATA),
    ("TimetableRuns", TIMETABLE_RUNS_DATA),
]

async def clear_database(session: AsyncSession):
    """Wipes all data from public tables."""
    print("Wiping database...")
    async with session.begin():
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
        await session.execute(text('TRUNCATE TABLE "teacher_specialties" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "users" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "admins" RESTART IDENTITY CASCADE'))
    print("Database wiped.")

async def seed_data(session: AsyncSession):
    """Seeds the database by processing data definition files."""
    print("Seeding data...")
    factories.test_db_session = session

    for label, data_list in SEEDING_ORDER:
        print(f"Seeding {label}...")
        for entry in data_list:
            data = entry.copy()
            factory_name = data.pop("factory")
            factory_class = getattr(factories, factory_name)

            # --- Special Handling ---
            if factory_name == "TimetableRunFactory":
                now = datetime.datetime.now(datetime.timezone.utc)
                data["solution_data"] = [{"category": "Tuition", "id": str(TEST_TUITION_ID), "start_time": now.isoformat(), "end_time": (now + datetime.timedelta(hours=1)).isoformat()}]

            # Create the object. 
            # Because we are using "Raw*" factories for items with FKs, 
            # factory_boy will ignore the relationships and use the provided IDs directly.
            factory_class.create(**data)
        
        await session.flush()

    await session.commit()
    print("Data seeding complete.")


async def main():
    if not settings.TEST_MODE:
        raise ConnectionRefusedError("Seeding script must be run with TEST_MODE=True.")

    engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        await clear_database(session)
        await seed_data(session)

    await engine.dispose()
    print("\nDatabase seeding complete.")


if __name__ == "__main__":
    asyncio.run(main())