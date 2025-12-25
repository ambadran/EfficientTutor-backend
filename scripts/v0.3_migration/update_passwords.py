"""
(V0.3) standalone script to update user passwords in the database.

This script connects to the database, finds specific users by their first_name,
and updates their passwords with a new hash generated from a plain-text password.

It also updates passwords for all students based on the plain-text password
stored in the `students.generated_password` column.

NOTE: This script assumes that the `first_name` for the staff users being updated
is unique, as confirmed by the user.
"""

import sys
import os
import argparse
from pathlib import Path

from passlib.context import CryptContext
from sqlalchemy import create_engine, update, select
from sqlalchemy.orm import sessionmaker

# --- Path Setup ---
# Ensure project root is in sys.path
# This file is at: root/scripts/v0.3_migration/update_passwords.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.efficient_tutor_backend.database.models import Users, Students


# --- Hashing Logic ---
# As provided by the user.
class HashedPassword:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    @classmethod
    def get_hash(cls, password: str) -> str:
        """Hashes a plain-text password."""
        return cls.pwd_context.hash(password)


# --- User Data ---
# Dictionary mapping the user's first_name to their new plain-text password.
PASSWORDS_TO_UPDATE = {
    "Manal": "New@2025",
    "Enas": "mumzy31*",
    "Ayman": "Yoyoyo.55",
    "Yasmine": "Yasmine@1977",
    "Reem": "Reemhany@1985",
    "AbdulRahman": "etsuperuser",
}

def load_env():
    """
    Manually load .env file from PROJECT_ROOT.
    """
    env_path = PROJECT_ROOT / '.env'
    if not env_path.exists():
        return

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                
                if key not in os.environ:
                    os.environ[key] = value

def update_staff_passwords_sync(session):
    """
    Updates passwords for staff members.
    """
    print("Updating staff passwords...")
    for first_name, plain_password in PASSWORDS_TO_UPDATE.items():
        # Hash the new password
        hashed_password = HashedPassword.get_hash(plain_password)

        # Create a targeted UPDATE statement
        stmt = (
            update(Users)
            .where(Users.first_name == first_name)
            .values(password=hashed_password)
        )
        
        # Execute the statement
        result = session.execute(stmt)
        
        if result.rowcount > 0:
            print(f"  - Prepared update for staff user: {first_name}")
        else:
            print(f"  - WARNING: Staff user '{first_name}' not found. No update occurred.")


def update_student_passwords_sync(session):
    """
    Updates passwords for all students from the 'generated_password' column.
    """
    print("\nUpdating student passwords...")
    
    # Select all students that have a generated password
    stmt = select(Students.id, Students.first_name, Students.generated_password).where(
        Students.generated_password.isnot(None)
    )
    students_to_update = session.execute(stmt).all()

    if not students_to_update:
        print("  - No students with a 'generated_password' found to update.")
        return

    for student_id, first_name, plain_password in students_to_update:
        if not plain_password:
            print(f"  - WARNING: Skipping student '{first_name}' (ID: {student_id}) due to empty generated_password.")
            continue

        # Hash the new password
        hashed_password = HashedPassword.get_hash(plain_password)

        # Create a targeted UPDATE statement for the 'users' table
        update_stmt = (
            update(Users)
            .where(Users.id == student_id)
            .values(password=hashed_password)
        )
        
        # Execute the statement
        result = session.execute(update_stmt)
        
        if result.rowcount > 0:
            print(f"  - Prepared update for student: {first_name}")
        else:
            # This case is unlikely if the student exists in the students table
            # but good to have for robustness.
            print(f"  - WARNING: Student '{first_name}' (ID: {student_id}) not found in users table. No update occurred.")


def run_all_updates():
    """
    Connects to the database and runs all password update functions.
    """
    parser = argparse.ArgumentParser(description="Update Passwords.")
    parser.add_argument("--prod", action="store_true", help="Run against PRODUCTION database.")
    args = parser.parse_args()

    load_env()
    
    if args.prod:
        target_env = "DATABASE_URL_PROD_CLI"
    else:
        target_env = "DATABASE_URL_TEST_CLI"

    db_url = os.getenv(target_env)
    if not db_url:
        print(f"Error: {target_env} environment variable not set.")
        return

    print(f"Connecting to database ({target_env})...")
    
    # Use sync engine for running migrations/updates
    if db_url.startswith("postgresql+asyncpg"):
        db_url = db_url.replace("postgresql+asyncpg", "postgresql")
    
    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine)

    print("Starting password update process...")
    with Session() as session:
        update_staff_passwords_sync(session)
        update_student_passwords_sync(session)

        # Commit all the changes at once
        print("\nCommitting changes to the database...")
        session.commit()

    engine.dispose()
    print("Password update process finished successfully.")


if __name__ == "__main__":
    run_all_updates()
