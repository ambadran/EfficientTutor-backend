"""
(V0.4) standalone script to run all SQL migration files in the correct order.

This script connects to the database and executes the raw SQL from each
migration file located in the `src/efficient_tutor_backend/database/sql/v0.4_migration` directory.

Usage:
    python scripts/v0.4_migration/run_migrations.py [--sql-only]
"""

import sys
import os
import argparse
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --- Constants ---
# The directory where migration scripts are stored.
SQL_DIR = PROJECT_ROOT / 'src' / 'efficient_tutor_backend' / 'database' / 'sql' / 'v0.4_migration'

# The specific order in which the migration scripts must be run.
MIGRATION_FILES = [
    'create_user_devices_table.sql',
]

def load_env():
    """
    Manually load .env file from PROJECT_ROOT if variables are missing.
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
    parser = argparse.ArgumentParser(description="Run v0.4 database migrations.")
    parser.add_argument("--sql-only", action="store_true", help="Run only the SQL migrations, skipping Python post-processing scripts.")
    parser.add_argument("--prod", action="store_true", help="Run migrations against the PRODUCTION database.")
    args = parser.parse_args()

    load_env() # Ensure env vars are loaded
    
    if args.prod:
        target_env_var = "DATABASE_URL_PROD_CLI"
        print("⚠️  WARNING: You are about to run migrations against the PRODUCTION database. ⚠️")
        confirmation = input("Are you sure you want to proceed? (y/n): ").strip().lower()
        if confirmation != 'y':
            print("Operation aborted.")
            return
    else:
        target_env_var = "DATABASE_URL_TEST_CLI"

    db_url = os.getenv(target_env_var)
    if not db_url:
        print(f"Error: {target_env_var} environment variable not set.")
        return

    print(f"Connecting to database ({target_env_var})...")
    
    # Use sync engine for running migrations
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

    engine.dispose()


if __name__ == "__main__":
    run_migrations_sync()
