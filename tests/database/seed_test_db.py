"""
Standalone script to seed the test database with deterministic data.
This script orchestrates the seeding process by reading data definitions
from the `tests/database/data/` directory.
"""

import asyncio
import uuid
import datetime
import importlib
import sys
from pathlib import Path
import os

# --- Setup Path & Environment ---
# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

os.environ["TEST_MODE"] = "True"

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from src.efficient_tutor_backend.common.config import settings
from src.efficient_tutor_backend.database import models as db_models
from tests.database import factories
from tests.constants import TEST_TUITION_ID, TEST_TIMETABLE_RUN_ID

# --- Import Manual Data Definitions ---
from tests.database.data.users import ADMINS_DATA, TEACHERS_DATA, PARENTS_DATA, STUDENTS_DATA
from tests.database.data.teacher_specialties import TEACHER_SPECIALTIES_DATA
from tests.database.data.tuitions import TUITIONS_DATA, MEETING_LINKS_DATA, TUITION_TEMPLATE_CHARGES_DATA
from tests.database.data.student_details import STUDENT_DETAILS_DATA 
from tests.database.data.teacher_details import TEACHER_DETAILS_DATA
from tests.database.data.logs import TUITION_LOGS_DATA, TUITION_LOG_CHARGES_DATA, PAYMENT_LOGS_DATA
from tests.database.data.notes import NOTES_DATA
from tests.database.data.timetable import TIMETABLE_RUN_USER_SOLUTIONS_DATA, TIMETABLE_SOLUTION_SLOTS_DATA

# --- Dynamic Import for Auto-Generated Data ---
def safe_import(module_name, var_name, default=[]):
    try:
        mod = importlib.import_module(f"tests.database.data.{module_name}")
        return getattr(mod, var_name, default)
    except ImportError:
        return default

AUTO_ADMINS_DATA = safe_import("auto_users", "AUTO_ADMINS_DATA")
AUTO_TEACHERS_DATA = safe_import("auto_users", "AUTO_TEACHERS_DATA")
AUTO_PARENTS_DATA = safe_import("auto_users", "AUTO_PARENTS_DATA")
AUTO_STUDENTS_DATA = safe_import("auto_users", "AUTO_STUDENTS_DATA")

AUTO_TEACHER_SPECIALTIES_DATA = safe_import("auto_teacher_specialties", "AUTO_TEACHER_SPECIALTIES_DATA")
AUTO_STUDENT_DETAILS_DATA = (
    safe_import("auto_student_details", "AUTO_STUDENT_SUBJECTS_DATA") + 
    safe_import("auto_student_details", "AUTO_STUDENT_AVAILABILITY_DATA")
)

AUTO_TUITIONS_DATA = safe_import("auto_tuitions", "AUTO_TUITIONS_DATA")
AUTO_MEETING_LINKS_DATA = safe_import("auto_tuitions", "AUTO_MEETING_LINKS_DATA")
AUTO_TUITION_TEMPLATE_CHARGES_DATA = safe_import("auto_tuitions", "AUTO_TUITION_TEMPLATE_CHARGES_DATA")

AUTO_TUITION_LOGS_DATA = safe_import("auto_logs", "AUTO_TUITION_LOGS_DATA")
AUTO_TUITION_LOG_CHARGES_DATA = safe_import("auto_logs", "AUTO_TUITION_LOG_CHARGES_DATA")
AUTO_PAYMENT_LOGS_DATA = safe_import("auto_logs", "AUTO_PAYMENT_LOGS_DATA")

AUTO_NOTES_DATA = safe_import("auto_notes", "AUTO_NOTES_DATA")

# New: Auto-generated Timetable Solutions
AUTO_TIMETABLE_RUN_USER_SOLUTIONS_DATA = safe_import("auto_timetable", "AUTO_TIMETABLE_RUN_USER_SOLUTIONS_DATA")
AUTO_TIMETABLE_SOLUTION_SLOTS_DATA = safe_import("auto_timetable", "AUTO_TIMETABLE_SOLUTION_SLOTS_DATA")

# --- Special Handling: The Master Timetable Run ---
# We synthesize ONE Master Run record that acts as the parent for ALL solution data.
MASTER_TIMETABLE_RUN = [{
    "factory": "TimetableRunFactory",
    "id": TEST_TIMETABLE_RUN_ID,
    "run_started_at": datetime.datetime.now(datetime.timezone.utc),
    "status": "SUCCESS",
    "input_version_hash": "test_master_hash",
    "trigger_source": "test_seeder",
    "legacy_solution_data": [] # Empty, but satisfies the column requirement
}]


# --- Seeding Topology ---
# We combine Manual + Auto data here.
SEEDING_ORDER = [
    ("Admins", ADMINS_DATA + AUTO_ADMINS_DATA),
    ("Teachers", TEACHERS_DATA + AUTO_TEACHERS_DATA),
    ("Parents", PARENTS_DATA + AUTO_PARENTS_DATA),
    ("Students", STUDENTS_DATA + AUTO_STUDENTS_DATA),
    ("TeacherSpecialties", TEACHER_SPECIALTIES_DATA + AUTO_TEACHER_SPECIALTIES_DATA),
    ("StudentDetails", STUDENT_DETAILS_DATA + AUTO_STUDENT_DETAILS_DATA),
    ("TeacherDetails", TEACHER_DETAILS_DATA),
    ("Tuitions", TUITIONS_DATA + AUTO_TUITIONS_DATA),
    ("MeetingLinks", MEETING_LINKS_DATA + AUTO_MEETING_LINKS_DATA),
    ("TuitionTemplateCharges", TUITION_TEMPLATE_CHARGES_DATA + AUTO_TUITION_TEMPLATE_CHARGES_DATA),
    ("TuitionLogs", TUITION_LOGS_DATA + AUTO_TUITION_LOGS_DATA),
    ("TuitionLogCharges", TUITION_LOG_CHARGES_DATA + AUTO_TUITION_LOG_CHARGES_DATA),
    ("PaymentLogs", PAYMENT_LOGS_DATA + AUTO_PAYMENT_LOGS_DATA),
    ("Notes", NOTES_DATA + AUTO_NOTES_DATA),
    
    # --- New Timetable Topology ---
    # 1. Create the Master Run
    ("TimetableRuns", MASTER_TIMETABLE_RUN),
    # 2. Attach User Solutions to the Master Run
    ("TimetableRunUserSolutions", TIMETABLE_RUN_USER_SOLUTIONS_DATA + AUTO_TIMETABLE_RUN_USER_SOLUTIONS_DATA),
    # 3. Attach Slots to the User Solutions
    ("TimetableSolutionSlots", TIMETABLE_SOLUTION_SLOTS_DATA + AUTO_TIMETABLE_SOLUTION_SLOTS_DATA),
]

async def clear_database(session: AsyncSession):
    """Wipes all data from public tables."""
    print("Wiping database...")
    async with session.begin():
        # Order matters for cascading deletes (though TRUNCATE CASCADE handles it)
        await session.execute(text('TRUNCATE TABLE "timetable_solution_slots" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "timetable_run_user_solutions" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "timetable_runs" RESTART IDENTITY CASCADE'))
        
        await session.execute(text('TRUNCATE TABLE "tuition_log_charges" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "tuition_logs" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "payment_logs" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "notes" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "meeting_links" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "tuition_template_charges" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "tuitions" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "student_subjects" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "availability_intervals" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "teacher_specialties" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "users" RESTART IDENTITY CASCADE'))
        await session.execute(text('TRUNCATE TABLE "admins" RESTART IDENTITY CASCADE'))
    print("Database wiped.")

async def seed_data(session: AsyncSession):
    """Seeds the database by processing data definition files."""
    print("Seeding data...")
    factories.test_db_session = session

    for label, data_list in SEEDING_ORDER:
        print(f"Seeding {label} ({len(data_list)} items)...")
        
        # Deduplicate based on ID if present, or specific unique constraints
        seen_ids = set()
        seen_unique_constraints = set()
        unique_data_list = []
        
        for entry in data_list:
            # 1. Primary Key Deduplication
            entry_id = entry.get("id")
            if entry_id:
                if entry_id in seen_ids:
                    continue
                seen_ids.add(entry_id)

            # 2. Unique Constraint Deduplication (for TeacherSpecialties)
            if label == "TeacherSpecialties":
                # Composite Key: (teacher_id, subject, educational_system, grade)
                composite_key = (
                    str(entry.get("teacher_id")),
                    entry.get("subject"), 
                    entry.get("educational_system"), 
                    entry.get("grade")
                )
                if composite_key in seen_unique_constraints:
                    continue
                seen_unique_constraints.add(composite_key)

            # 3. Unique Constraint Deduplication (for StudentDetails -> StudentSubjects)
            # We only check this if the entry looks like a StudentSubject (has 'student_id' and 'subject')
            if label == "StudentDetails" and "subject" in entry:
                # Composite Key: (student_id, subject, teacher_id, educational_system, grade)
                composite_key = (
                    str(entry.get("student_id")),
                    entry.get("subject"), 
                    str(entry.get("teacher_id")),
                    entry.get("educational_system"), 
                    entry.get("grade")
                )
                if composite_key in seen_unique_constraints:
                    continue
                seen_unique_constraints.add(composite_key)

            # 4. Unique Constraint Deduplication (for MeetingLinks)
            # MeetingLinks have a PK of (tuition_id) or (tuition_id) is unique
            if label == "MeetingLinks":
                tuition_id = str(entry.get("tuition_id"))
                if tuition_id in seen_unique_constraints:
                    continue
                seen_unique_constraints.add(tuition_id)

            # 5. Unique Constraint Deduplication (for Admins - Single Master)
            if label == "Admins":
                privileges = entry.get("privileges")
                if privileges == "Master":
                    if "MasterAdmin" in seen_unique_constraints:
                        continue
                    seen_unique_constraints.add("MasterAdmin")

            # 6. Unique Constraint Deduplication (for TimetableRuns)
            # For runs, we rely on the ID check above, but in our new design 
            # there is only ever one Master Run with ID 9999.
            # Any accidental duplicates will be caught by "seen_ids".
            pass 

            unique_data_list.append(entry)

        for entry in unique_data_list:
            data = entry.copy()
            factory_name = data.pop("factory")
            factory_class = getattr(factories, factory_name)

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
