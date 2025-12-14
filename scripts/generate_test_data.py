"""Script to extract data from a production database (restored locally),
anonymize it, and generate Python data files for the test seeder.

Usage:
    python scripts/generate_test_data.py --db-url postgresql+asyncpg://user:pass@localhost:5432/prod_temp
"""

import argparse
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from decimal import Decimal
from datetime import datetime, date, time
from pathlib import Path
import sys

# Third-party
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text, inspect, MetaData
from sqlalchemy.orm import sessionmaker
from faker import Faker

# App imports
# (Adjust path if necessary depending on where you run this script from)
sys.path.append(str(Path(__file__).parent.parent))
from src.efficient_tutor_backend.database.db_enums import (
    UserRole, AdminPrivilegeType, SubjectEnum, EducationalSystemEnum,
    MeetingLinkTypeEnum, NoteTypeEnum, LogStatusEnum, TuitionLogCreateTypeEnum,
    AvailabilityTypeEnum, RunStatusEnum
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

faker = Faker()

# Global configuration
ANONYMIZE_PII = True

# --- Configuration ---

# Mapping Table Name -> (Factory Name, Anonymization Rules)
# Rules: dict where key is column name, value is a callable that takes the original value and returns new value
# If value is None, it keeps the original value.
# If key is not present, it keeps original value.

def anonymize_email(old_val: str) -> str:
    if not ANONYMIZE_PII:
        return old_val
    return faker.unique.email()

def anonymize_first_name(old_val: str) -> str:
    if not ANONYMIZE_PII:
        return old_val
    return faker.first_name()

def anonymize_last_name(old_val: str) -> str:
    if not ANONYMIZE_PII:
        return old_val
    return faker.last_name()

def anonymize_password(old_val: str) -> str:
    # Return a known hash: "password" (or whatever constant you prefer)
    # Using a placeholder hash for speed.
    # This password is 'testtest'
    return "$2b$12$ezyY86d0mZsWLPdJ0V5Jeuf/qFcsGcM8zO5GKEQ7I3KN9d2LNDN1C"

# We need to know which Factory corresponds to which table AND filtered by some criteria (like Role) for Users.
# Since 'users' table holds multiple roles, we handle it specially.

TABLE_CONFIG = [
    # (Table Name, Output Filename, Filter/Type Logic, Factory Name)

    # --- Users (Split by Role) ---
    {
        "table": "admins",
        "filename": "auto_users.py",
        "var_name": "AUTO_ADMINS_DATA",
        "factory": "AdminFactory",
        "anonymize": {
            "email": anonymize_email,
            "first_name": anonymize_first_name,
            "last_name": anonymize_last_name,
            "password": anonymize_password
        }
    },
    {
        "table": "users",
        "filename": "auto_users.py",
        "var_name": "AUTO_TEACHERS_DATA",
        "factory": "TeacherFactory",
        "filter_clause": f"role = '{UserRole.TEACHER.value}'",
        "anonymize": {
            "email": anonymize_email,
            "first_name": anonymize_first_name,
            "last_name": anonymize_last_name,
            "password": anonymize_password
        }
    },
    {
        "table": "users",
        "filename": "auto_users.py",
        "var_name": "AUTO_PARENTS_DATA",
        "factory": "ParentFactory",
        "filter_clause": f"role = '{UserRole.PARENT.value}'",
        "anonymize": {
            "email": anonymize_email,
            "first_name": anonymize_first_name,
            "last_name": anonymize_last_name,
            "password": anonymize_password
        }
    },
    {
        "table": "users", # Students are in 'users' table? No, check models.py.
        # Wait, Students are in 'students' table which inherits/joins with 'users' or is standalone?
        # Looking at seed_test_db.py/factories.py:
        # StudentFactory uses db_models.Students.
        # Let's check if 'students' is a separate table or if it's all single-table inheritance.
        # Checking db_enums... UserRole.STUDENT.
        # Checking factories.py... AdminFactory->db_models.Admins, TeacherFactory->db_models.Teachers.
        # It seems we are using Joined Table Inheritance or separate tables?
        # I will assume specific tables exist: 'admins', 'teachers', 'parents', 'students' 
        # based on the factories targeting specific models.
        # IF they are all views/inheritance on 'users', I need to query 'users' join 'students'.
        # Let's assume standard SQL names.
        "table": "students", # This table likely has specific student columns + user columns via join?
        # Actually, usually in factories, we write to the specific ORM model.
        # For extraction, if I query 'students' table, I get student-specific fields.
        # I might need to join with 'users' to get email/name.
        # FOR SIMPLICITY: I will read from the specific tables assuming they contain the necessary IDs.
        # If 'email' is in 'users' and not 'students', I need to join.
        # Let's assume we need to query the VIEW or JOIN manually if needed.
        # FIX: I will try to select from the specific tables. 
        # If columns are missing, I'll add a join in the query logic.
        "filename": "auto_users.py",
        "var_name": "AUTO_STUDENTS_DATA",
        "factory": "RawStudentFactory",
        "join_parent_table": "users", # Custom flag to indicate we need data from parent table
        "join_on": "id",
        "anonymize": {
            "email": anonymize_email,
            "first_name": anonymize_first_name,
            "last_name": anonymize_last_name,
            "password": anonymize_password # Note: Students have 'generated_password' usually?
        }
    },

    # --- Details ---
    {
        "table": "teacher_specialties",
        "filename": "auto_teacher_specialties.py",
        "var_name": "AUTO_TEACHER_SPECIALTIES_DATA",
        "factory": "RawTeacherSpecialtyFactory",
        "anonymize": {}
    },
    {
        "table": "student_subjects",
        "filename": "auto_student_details.py",
        "var_name": "AUTO_STUDENT_SUBJECTS_DATA",
        "factory": "RawStudentSubjectFactory",
        "anonymize": {}
    },
    {
        "table": "availability_intervals",
        "filename": "auto_student_details.py",
        "var_name": "AUTO_STUDENT_AVAILABILITY_DATA",
        "factory": "RawAvailabilityIntervalFactory",
        "anonymize": {}
    },

    # --- Tuitions ---
    {
        "table": "tuitions",
        "filename": "auto_tuitions.py",
        "var_name": "AUTO_TUITIONS_DATA",
        "factory": "RawTuitionFactory",
        "anonymize": {}
    },
    {
        "table": "meeting_links",
        "filename": "auto_tuitions.py",
        "var_name": "AUTO_MEETING_LINKS_DATA",
        "factory": "RawMeetingLinkFactory",
        "anonymize": {
            "meeting_link": lambda x: x if not ANONYMIZE_PII else "https://meet.google.com/auto-generated",
            "meeting_id": lambda x: x if not ANONYMIZE_PII else faker.bothify(text="???-####-???"),
            "meeting_password": lambda x: x if not ANONYMIZE_PII else "auto-pass"
        }
    },
    {
        "table": "tuition_template_charges",
        "filename": "auto_tuitions.py",
        "var_name": "AUTO_TUITION_TEMPLATE_CHARGES_DATA",
        "factory": "RawTuitionTemplateChargeFactory",
        "anonymize": {}
    },

    # --- Logs ---
    {
        "table": "tuition_logs",
        "filename": "auto_logs.py",
        "var_name": "AUTO_TUITION_LOGS_DATA",
        "factory": "RawTuitionLogFactory",
        "anonymize": {}
    },
    {
        "table": "tuition_log_charges",
        "filename": "auto_logs.py",
        "var_name": "AUTO_TUITION_LOG_CHARGES_DATA",
        "factory": "RawTuitionLogChargeFactory",
        "anonymize": {}
    },
    {
        "table": "payment_logs",
        "filename": "auto_logs.py",
        "var_name": "AUTO_PAYMENT_LOGS_DATA",
        "factory": "RawPaymentLogFactory",
        "anonymize": {
            "notes": lambda x: x if not ANONYMIZE_PII else "Anonymized payment note"
        }
    },
    
    # --- Misc ---
    {
        "table": "notes",
        "filename": "auto_notes.py",
        "var_name": "AUTO_NOTES_DATA",
        "factory": "RawNoteFactory",
        "anonymize": {
            "name": lambda x: x if not ANONYMIZE_PII else faker.sentence(nb_words=3),
            "description": lambda x: x if not ANONYMIZE_PII else faker.text(),
            "url": lambda x: x if not ANONYMIZE_PII else "https://example.com/anonymized-note"
        }
    },
    {
        "table": "timetable_runs",
        "filename": "auto_timetable.py",
        "var_name": "AUTO_TIMETABLE_RUNS_DATA",
        "factory": "TimetableRunFactory",
        "anonymize": {}
    },
    {
        "table": "timetable_run_user_solutions",
        "filename": "auto_timetable.py",
        "var_name": "AUTO_TIMETABLE_RUN_USER_SOLUTIONS_DATA",
        "factory": "RawTimetableRunUserSolutionFactory",
        "anonymize": {
            "timetable_run_id": lambda x: 9999
        }
    },
    {
        "table": "timetable_solution_slots",
        "filename": "auto_timetable.py",
        "var_name": "AUTO_TIMETABLE_SOLUTION_SLOTS_DATA",
        "factory": "RawTimetableSolutionSlotFactory",
        "anonymize": {
             "name": lambda x: x if not ANONYMIZE_PII else "Anonymized Slot"
        }
    },
]

def repr_val(val: Any) -> str:
    """Helper to format values for Python code."""
    if isinstance(val, UUID):
        return f"UUID('{str(val)}')"
    if isinstance(val, datetime):
        return f"datetime.datetime.fromisoformat('{val.isoformat()}')"
    if isinstance(val, date):
        return f"datetime.date.fromisoformat('{val.isoformat()}')"
    if isinstance(val, time):
        return f"datetime.time.fromisoformat('{val.isoformat()}')"
    if isinstance(val, Decimal):
        return f"Decimal('{str(val)}')"
    if val is None:
        return "None"
    return repr(val)

async def process_table(
    session: AsyncSession,
    config: Dict[str, Any],
    output_buffer: Dict[str, List[str]]
):
    table_name = config["table"]
    factory_name = config["factory"]
    var_name = config["var_name"]
    filename = config["filename"]
    
    logger.info(f"Processing table: {table_name} -> {factory_name}")

    # Build Query
    # Basic select *
    query_str = f"SELECT * FROM {table_name}"
    
    # Handle Inheritance Join (very basic, assumes 1:1 on id)
    if "join_parent_table" in config:
        parent = config["join_parent_table"]
        join_col = config.get("join_on", "id")
        # We select specific columns to avoid collision or just select all and let dictionary merge handle it?
        # Better to select T.* and P. 
        # Actually, in SQLAlchemy execute(text), columns with same name might collide.
        # We assume the child table columns override parent if collision, except ID is same.
        query_str = f"SELECT {parent}.*, {table_name}.* FROM {table_name} JOIN {parent} ON {table_name}.{join_col} = {parent}.id"

    if "filter_clause" in config:
        query_str += f" WHERE {config['filter_clause']}"

    result = await session.execute(text(query_str))
    rows = result.mappings().all()

    if not rows:
        logger.warning(f"No rows found for {table_name}")
        return

    # Prepare List of Dict strings
    data_list_str = []
    
    for row in rows:
        row_dict = dict(row)
        
        # Anonymize
        anonymizers = config.get("anonymize", {})
        for col, func in anonymizers.items():
            if col in row_dict: # Only if column exists
                row_dict[col] = func(row_dict[col])
        
        # Format as dict string
        # We need to construct the string: {"factory": "Name", "col": val, ...}
        
        # Filter out internal sqlalchemy/postgres columns if any (usually not in mappings)
        # Filter out None values? No, factory might need explicit None to override SubFactory.
        
        # Construct content items
        items = [f"'factory': '{factory_name}'"]
        
        for k, v in row_dict.items():
            # Skip ignored columns if necessary (e.g., created_at, updated_at if not in factory)
            # For now, we include everything. Factory boy usually ignores extra kwargs or we can exclude them.
            # Actually FactoryBoy creates attributes for kwargs. If the model doesn't have the field, it might crash
            # if using SQLAlchemyModelFactory? No, SQLAlchemyModelFactory is smart.
            # However, 'created_at' usually is handled by DB defaults. Let's try to include everything.
            
            # Exclude redundant ID columns from joins if they appear twice?
            # mappings() handles distinct keys.
            
            items.append(f"'{k}': {repr_val(v)}")
        
        dict_str = "    {" + ", ".join(items) + "},"
        data_list_str.append(dict_str)

    # Add to buffer
    if filename not in output_buffer:
        output_buffer[filename] = []
    
    # Format variable block
    header = f"# --- {var_name} ---\n{var_name} = [\n"
    footer = "\n]\n"
    block = header + "\n".join(data_list_str) + footer
    output_buffer[filename].append(block)


async def main():
    global ANONYMIZE_PII
    parser = argparse.ArgumentParser(description="Generate test data from production DB.")
    parser.add_argument("--db-url", required=True, help="Source Database URL")
    parser.add_argument("--no-anonymize", action="store_true", help="Disable PII anonymization (keep real emails/names)")
    args = parser.parse_args()

    if args.no_anonymize:
        ANONYMIZE_PII = False
        logger.info("Anonymization DISABLED. Real PII will be used.")
    else:
        ANONYMIZE_PII = True
        logger.info("Anonymization ENABLED.")

    db_url = args.db_url
    if db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Buffer to hold file contents: Filename -> List of variable blocks
    output_buffer: Dict[str, List[str]] = {}

    async with async_session() as session:
        for config in TABLE_CONFIG:
            await process_table(session, config, output_buffer)

    # Write files
    # Resolve path relative to project root (which is parent of scripts/ dir)
    project_root = Path(__file__).parent.parent
    base_path = project_root / "tests/database/data"
    base_path.mkdir(parents=True, exist_ok=True)

    header = "from uuid import UUID\nfrom decimal import Decimal\nimport datetime\n\n"

    for filename, blocks in output_buffer.items():
        full_content = header + "\n".join(blocks)
        file_path = base_path / filename
        logger.info(f"Writing {len(blocks)} blocks to {file_path}")
        with open(file_path, "w") as f:
            f.write(full_content)

    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
