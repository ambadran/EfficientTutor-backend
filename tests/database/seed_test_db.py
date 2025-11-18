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
from .data.users import USERS_DATA
from .data.tuitions import TUITIONS_DATA
from .data.student_details import STUDENT_DETAILS_DATA
from .data.logs import LOGS_DATA
from .data.misc import MISC_DATA


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
    """Seeds the database by processing data definition files."""
    print("Seeding data...")
    factories.test_db_session = session

    # In-memory stores for created objects to resolve dependencies
    created_users = {}
    created_tuitions = {}
    created_logs = {}

    # --- Process Data Files in Dependency Order ---

    # 1. Users
    for user_data in USERS_DATA:
        data = user_data.copy()
        factory = getattr(factories, data.pop("factory"))
        if "parent_id" in data:
            data["parent"] = created_users[data.pop("parent_id")]
        user = factory.create(**data)
        created_users[user.id] = user

    # 2. Tuitions
    for tuition_data in TUITIONS_DATA:
        data = tuition_data.copy()
        factory = getattr(factories, data.pop("factory"))
        if "teacher_id" in data:
            data["teacher"] = created_users[data.pop("teacher_id")]
        if "tuition_id" in data:
            data["tuition"] = created_tuitions[data.pop("tuition_id")]
        if "student_id" in data:
            data["student"] = created_users[data.pop("student_id")]
        if "parent_id" in data:
            data["parent"] = created_users[data.pop("parent_id")]
        item = factory.create(**data)
        if data.get("id"):
             created_tuitions[data["id"]] = item


    # 3. Student Details
    for detail_data in STUDENT_DETAILS_DATA:
        data = detail_data.copy()
        factory = getattr(factories, data.pop("factory"))
        if "student_id" in data:
            data["student"] = created_users[data.pop("student_id")]
        if "teacher_id" in data:
            data["teacher"] = created_users[data.pop("teacher_id")]
        factory.create(**data)

    # 4. Logs
    for log_data in LOGS_DATA:
        data = log_data.copy()
        factory = getattr(factories, data.pop("factory"))
        if "tuition_id" in data:
            data["tuition"] = created_tuitions[data.pop("tuition_id")]
        if "teacher_id" in data:
            data["teacher"] = created_users[data.pop("teacher_id")]
        if "student_id" in data:
            data["student"] = created_users[data.pop("student_id")]
        if "parent_id" in data:
            data["parent"] = created_users[data.pop("parent_id")]
        if "tuition_log_id" in data:
            data["tuition_log"] = created_logs[data.pop("tuition_log_id")]
        item = factory.create(**data)
        if data.get("id"):
            created_logs[item.id] = item

    # 5. Miscellaneous
    for misc_data in MISC_DATA:
        data = misc_data.copy()
        factory = getattr(factories, data.pop("factory"))

        if factory == factories.TimetableRunFactory:
            now = datetime.datetime.now(datetime.timezone.utc)
            data["solution_data"] = [{"category": "Tuition", "id": str(TEST_TUITION_ID), "start_time": now.isoformat(), "end_time": (now + datetime.timedelta(hours=1)).isoformat()}]
        
        if "teacher_id" in data:
            data["teacher"] = created_users[data.pop("teacher_id")]
        if "student_id" in data:
            data["student"] = created_users[data.pop("student_id")]

        factory.create(**data)

    await session.commit()
    print("Data seeding complete.")


async def main():
    """Main function to connect, wipe, and seed the database."""
    if not settings.TEST_MODE:
        raise ConnectionRefusedError("Seeding script must be run with TEST_MODE=True.")

    engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        await clear_database(session)
        await seed_data(session)

    await engine.dispose()
    print("\nDatabase seeding complete. All data is now defined in `tests/database/data/`.")


if __name__ == "__main__":
    asyncio.run(main())
