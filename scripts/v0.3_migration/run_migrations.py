"""
(V0.3) standalone script to run all SQL migration files in the correct order.

This script connects to the database and executes the raw SQL from each
migration file located in the `src/efficient_tutor_backend/database/sql/` directory.
"""

import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# --- Path Setup ---
# This allows the script to import modules from the 'src' directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.efficient_tutor_backend.common.config import settings

# --- Constants ---
# The directory where migration scripts are stored.
SQL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'efficient_tutor_backend', 'database', 'sql', 'v0.3_migration')

# The specific order in which the migration scripts must be run.
MIGRATION_FILES = [
    'sql_code.sql',
    'subject_migration.sql',
    'availability_migration.sql',
    'add_teacher_to_subjects.sql',
    'create_admins_table.sql',
    'teacher_specialty_migration.sql',
    'student_subject_educational_system_migration.sql',
    'grade_migration.sql'
]


def run_migrations_sync():
    """
    Connects to the database and executes all SQL migration scripts in order.
    """
    db_url = settings.DATABASE_URL_TEST_CLI
    if not db_url:
        print("Error: DATABASE_URL_TEST_CLI environment variable not set.")
        return

    print(f"Connecting to database...")
    
    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine)

    print("Starting migration process...")
    with Session() as session:
        for filename in MIGRATION_FILES:
            file_path = os.path.join(SQL_DIR, filename)
            
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

    engine.dispose()


if __name__ == "__main__":
    run_migrations_sync()
