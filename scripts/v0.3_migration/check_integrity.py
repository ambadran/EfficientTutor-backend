import asyncio
import os
import sys
import argparse
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# --- Path Setup ---
# This file is assumed to be in <project_root>/scripts/check_integrity.py
# We want PROJECT_ROOT to be the parent of the scripts directory.
CURRENT_DIR = Path(__file__).resolve().parent
if CURRENT_DIR.name == "scripts":
    PROJECT_ROOT = CURRENT_DIR.parent
else:
    # Fallback if run from root or elsewhere unexpectedly, assume parent
    PROJECT_ROOT = CURRENT_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def load_env():
    env_path = PROJECT_ROOT / '.env'
    if not env_path.exists():
        print(f"Warning: .env not found at {env_path}")
        return
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                k, v = line.split('=', 1)
                k, v = k.strip(), v.strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                if k not in os.environ: os.environ[k] = v

async def check_integrity():
    parser = argparse.ArgumentParser(description="Check database integrity.")
    parser.add_argument("--prod", action="store_true", help="Run check against the PRODUCTION database.")
    args = parser.parse_args()

    load_env()
    
    if args.prod:
        target_env_var = "DATABASE_URL_PROD_CLI"
        print("⚠️  WARNING: You are checking integrity on the PRODUCTION database. ⚠️")
        # Integrity checks are read-only, so a simple y/n is sufficient, but still good practice.
        confirmation = input("Are you sure you want to proceed? (y/n): ").strip().lower()
        if confirmation != 'y':
            print("Operation aborted.")
            return
    else:
        target_env_var = "DATABASE_URL_TEST_CLI"

    db_url = os.getenv(target_env_var)
    if not db_url:
        print(f"Error: {target_env_var} not set.")
        return

    if db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    
    print(f"Connecting to database ({target_env_var})...")
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession)

    async with async_session() as session:
        print("--- Checking Foreign Key Integrity ---")
        
        # 1. Check Tuition Logs
        orphaned_logs = await session.execute(text("""
            SELECT count(*) FROM tuition_logs tl
            LEFT JOIN tuitions t ON tl.tuition_id = t.id
            WHERE tl.tuition_id IS NOT NULL AND t.id IS NULL
        """))
        count_logs = orphaned_logs.scalar()
        
        # 2. Check Meeting Links
        orphaned_links = await session.execute(text("""
            SELECT count(*) FROM meeting_links ml
            LEFT JOIN tuitions t ON ml.tuition_id = t.id
            WHERE t.id IS NULL
        """))
        count_links = orphaned_links.scalar()

        # 3. Check Count of Meeting Links
        total_links = await session.execute(text("SELECT count(*) FROM meeting_links"))
        total_count = total_links.scalar()

        print(f"Orphaned Logs: {count_logs}")
        print(f"Orphaned Links: {count_links}")
        print(f"Total Meeting Links: {total_count}")

        if count_logs == 0 and count_links == 0 and total_count > 0:
            print("✅ PASS: Integrity Verified.")
        else:
            print("❌ FAIL: Integrity Issues Found.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_integrity())
