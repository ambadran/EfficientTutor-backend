"""
(V0.3) standalone script to run all SQL migration files in the correct order.

This script connects to the database and executes the raw SQL from each
migration file located in the `src/efficient_tutor_backend/database/sql/` directory.

Usage:
    python scripts/v0.3_migration/run_migrations.py [--sql-only]
"""

import sys
import os
import argparse
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# --- Path Setup ---
# Ensure project root is in sys.path
# This file is at: root/scripts/v0.3_migration/run_migrations.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --- Constants ---
# The directory where migration scripts are stored.
SQL_DIR = PROJECT_ROOT / 'src' / 'efficient_tutor_backend' / 'database' / 'sql' / 'v0.3_migration'

# The specific order in which the migration scripts must be run.
MIGRATION_FILES = [
    'sql_code.sql',
    'subject_migration.sql',
    'availability_migration.sql',
    'add_teacher_to_subjects.sql',
    'create_admins_table.sql',
    'teacher_specialty_migration.sql',
    'student_subject_educational_system_migration.sql',
    'grade_migration.sql',
    'generalize_availability.sql',
    'add_student_educational_system.sql',
    'create_timetable_solutions.sql'
]

def load_env():
    """
    Manually load .env file from PROJECT_ROOT if variables are missing.
    This ensures the script works even if shell env vars are not passed correctly.
    """
    env_path = PROJECT_ROOT / '.env'
    if not env_path.exists():
        return

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Split strictly on first =
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Basic quote removal
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                       value = value[1:-1]
                
                # Only set if not already in environment (respect shell overrides)
                if key not in os.environ:
                    os.environ[key] = value

def run_migrations_sync():
    """
    Connects to the database and executes all SQL migration scripts in order.
    Optionally runs Python-based post-migration scripts.
    """
    parser = argparse.ArgumentParser(description="Run v0.3 database migrations.")
    parser.add_argument("--sql-only", action="store_true", help="Run only the SQL migrations, skipping Python post-processing scripts.")
    args = parser.parse_args()

    load_env() # Ensure env vars are loaded
    
    db_url = os.getenv("DATABASE_URL_TEST_CLI")
    if not db_url:
        print("Error: DATABASE_URL_TEST_CLI environment variable not set.")
        return

    print(f"Connecting to database...")
    
    # Use sync engine for running migrations
    # If database_url is async (postgresql+asyncpg), we might need to replace it with psycopg2
    if db_url.startswith("postgresql+asyncpg"):
        db_url = db_url.replace("postgresql+asyncpg", "postgresql")
    
    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine)

    print("Starting migration process...")
    with Session() as session:
        for filename in MIGRATION_FILES:
            file_path = SQL_DIR / filename
            
            print(f"  - Executing: {filename}...")
            
            try:
                with open(file_path, 'r') as f:
                    sql_content = f.read()
                
                # Execute the entire content of the SQL file
                session.execute(text(sql_content))
                session.commit()
                print(f"    ...Success")

            except FileNotFoundError:
                print(f"    ...ERROR: File not found at {file_path}. Halting migrations.")
                session.rollback()
                break
            except SQLAlchemyError as e:
                print(f"    ...ERROR: An error occurred while executing {filename}.")
                print(f"    ...Details: {e}")
                print(f"    ...Rolling back and halting migrations.")
                session.rollback()
                break
            except Exception as e:
                print(f"    ...An unexpected error occurred: {e}")
                session.rollback()
                break
        else: # This 'else' belongs to the 'for' loop, runs only if the loop completes without 'break'
            print("\nAll migration scripts executed successfully.")

            if args.sql_only:
                print("Skipping Python post-processing scripts (--sql-only flag used).")
            else:
                import subprocess

                # --- V0.3 Addition: Fix Tuition IDs (Deterministic) ---
                print("\n--- Starting Tuition ID Fix (Deterministic Regeneration) ---")
                fix_ids_script = PROJECT_ROOT / 'scripts' / 'v0.3_migration' / 'fix_tuition_ids.py'
                try:
                    subprocess.run([sys.executable, str(fix_ids_script)], check=True)
                    print("Tuition IDs Fixed Successfully.")
                except subprocess.CalledProcessError:
                    print("ERROR: Tuition ID Fix Failed. Aborting.")
                    raise

                # --- V0.3 Addition: Run Timetable Synthesis ---
                # Now runs after IDs are fixed
                print("\n--- Starting Timetable Synthesis ---")
                synthesis_script = PROJECT_ROOT / 'scripts' / 'v0.3_migration' / 'synthesize_timetable.py'
                try:
                    subprocess.run([sys.executable, str(synthesis_script)], check=True)
                    print("Timetable Synthesis Completed Successfully.")
                except subprocess.CalledProcessError:
                    print("ERROR: Timetable Synthesis Failed. Aborting.")
                    raise

                # --- V0.3 Addition: Update Passwords ---
                print("\n--- Starting Password Updates ---")
                pwd_script = PROJECT_ROOT / 'scripts' / 'v0.3_migration' / 'update_passwords.py'
                try:
                    subprocess.run([sys.executable, str(pwd_script)], check=True)
                    print("Passwords Updated Successfully.")
                except subprocess.CalledProcessError:
                    print("ERROR: Password Update Failed.")
                    raise

    engine.dispose()


if __name__ == "__main__":
    run_migrations_sync()
