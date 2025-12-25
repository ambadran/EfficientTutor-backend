"""
(V0.3) standalone script to Regenerate Tuition IDs to be Deterministic.

This script:
1. Preserves the linkage between existing Tuition Logs and their Tuitions.
2. Preserves the linkage between existing Meeting Links and their Tuitions.
3. Calls the TuitionService.regenerate_all_tuitions() method.
   - This method wipes the current 'tuitions' table.
   - It rebuilds it based on 'student_subjects' and 'student_subject_sharings'.
   - It generates DETERMINISTIC UUIDs for the new tuitions.
4. Restores the linkage for Tuition Logs AND Meeting Links by calculating the 
   matching Deterministic ID for the preserved attributes.
"""

import asyncio
import sys
import os
import argparse
import hashlib
from pathlib import Path
from uuid import UUID
from typing import List, Dict, Any, Tuple

from sqlalchemy import select, text, update, insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.tuition_service import TuitionService
from src.efficient_tutor_backend.services.user_service import UserService

# Helper to load env (duplicated from run_migrations, but needed for standalone run)
def load_env():
    env_path = PROJECT_ROOT / '.env'
    if not env_path.exists():
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
                if k not in os.environ:
                    os.environ[k] = v

def generate_deterministic_id(subject: str, educational_system: str, grade: int, lesson_index: int, teacher_id: UUID, student_ids: List[UUID]) -> UUID:
    """
    Replicates the logic from TuitionService to calculate the ID offline if needed,
    or simply to verify.
    """
    id_string = f"{subject}:{educational_system}:{grade}:{lesson_index}:{teacher_id}:{','.join(map(str, sorted(student_ids)))}"
    hasher = hashlib.sha256(id_string.encode('utf-8'))
    return UUID(bytes=hasher.digest()[:16])

async def main():
    parser = argparse.ArgumentParser(description="Fix Tuition IDs.")
    parser.add_argument("--prod", action="store_true", help="Run against PRODUCTION database.")
    args = parser.parse_args()

    load_env()
    
    if args.prod:
        target_env = "DATABASE_URL_PROD_CLI"
    else:
        target_env = "DATABASE_URL_TEST_CLI"

    db_url = os.getenv(target_env)
    if not db_url:
        print(f"ERROR: {target_env} not set.")
        return
    
    # Ensure async
    if db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    print(f"Connecting to database ({target_env})...")
    engine = create_async_engine(db_url, echo=False)
    AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        # We need to construct the services manually (dependency injection doesn't work here)
        user_svc = UserService(session) 
        tuition_svc = TuitionService(session, user_svc)

        # --- Step 1: Preserve Logs ---
        print("--- Step 1: Preserving Tuition Log Attributes ---")
        logs_stmt = text("""
            SELECT 
                tl.id as log_id,
                t.subject,
                t.educational_system,
                t.grade,
                t.lesson_index,
                t.teacher_id,
                array_agg(ttc.student_id) as student_ids
            FROM tuition_logs tl
            JOIN tuitions t ON tl.tuition_id = t.id
            JOIN tuition_template_charges ttc ON t.id = ttc.tuition_id
            WHERE tl.tuition_id IS NOT NULL
            GROUP BY tl.id, t.subject, t.educational_system, t.grade, t.lesson_index, t.teacher_id
        """)
        result_logs = await session.execute(logs_stmt)
        preserved_logs = result_logs.mappings().all()
        print(f"Preserved attributes for {len(preserved_logs)} logs.")

        # --- Step 2: Preserve Meeting Links ---
        print("--- Step 2: Preserving Meeting Link Attributes ---")
        links_stmt = text("""
            SELECT 
                ml.tuition_id as original_tuition_id,
                ml.meeting_link_type,
                ml.meeting_link,
                ml.meeting_id,
                ml.meeting_password,
                t.subject,
                t.educational_system,
                t.grade,
                t.lesson_index,
                t.teacher_id,
                array_agg(ttc.student_id) as student_ids
            FROM meeting_links ml
            JOIN tuitions t ON ml.tuition_id = t.id
            JOIN tuition_template_charges ttc ON t.id = ttc.tuition_id
            GROUP BY ml.tuition_id, ml.meeting_link_type, ml.meeting_link, ml.meeting_id, ml.meeting_password,
                     t.subject, t.educational_system, t.grade, t.lesson_index, t.teacher_id
        """)
        result_links = await session.execute(links_stmt)
        preserved_links = result_links.mappings().all()
        print(f"Preserved attributes for {len(preserved_links)} meeting links.")

        # --- Step 3: Regenerate Tuitions ---
        print("--- Step 3: Regenerating Tuitions (Deterministic IDs) ---")
        # This wipes 'tuitions' (orphaning logs, deleting links) and rebuilds from 'student_subjects'
        success = await tuition_svc.regenerate_all_tuitions()
        if not success:
            print("Regeneration failed or returned False.")
            return
        
        # --- Step 4: Restore Log Linkages ---
        print("--- Step 4: Restoring Log Linkages ---")
        restored_logs_count = 0
        
        for p_log in preserved_logs:
            new_id = generate_deterministic_id(
                subject=p_log['subject'],
                educational_system=p_log['educational_system'],
                grade=p_log['grade'],
                lesson_index=p_log['lesson_index'],
                teacher_id=p_log['teacher_id'],
                student_ids=p_log['student_ids']
            )
            
            try:
                await session.execute(
                    update(db_models.TuitionLogs)
                    .where(db_models.TuitionLogs.id == p_log['log_id'])
                    .values(tuition_id=new_id)
                )
                restored_logs_count += 1
            except Exception as e:
                print(f"Failed to relink Log {p_log['log_id']} to Tuition {new_id}: {e}")

        # --- Step 5: Restore Meeting Links ---
        print("--- Step 5: Restoring Meeting Links ---")
        restored_links_count = 0

        for p_link in preserved_links:
            new_id = generate_deterministic_id(
                subject=p_link['subject'],
                educational_system=p_link['educational_system'],
                grade=p_link['grade'],
                lesson_index=p_link['lesson_index'],
                teacher_id=p_link['teacher_id'],
                student_ids=p_link['student_ids']
            )

            # MeetingLinks were deleted by cascade when Tuitions were wiped.
            # We must INSERT new records.
            try:
                # Using ORM or Core Insert
                # Since meeting_links table has a simple structure, core insert is fine.
                # However, db_models.MeetingLinks might be safer if we use model logic.
                # Let's use core insert to avoid fetching the tuition object first.
                
                await session.execute(
                    insert(db_models.MeetingLinks).values(
                        tuition_id=new_id,
                        meeting_link_type=p_link['meeting_link_type'],
                        meeting_link=p_link['meeting_link'],
                        meeting_id=p_link['meeting_id'],
                        meeting_password=p_link['meeting_password']
                    )
                )
                restored_links_count += 1
            except Exception as e:
                # This could fail if the new tuition doesn't exist (regeneration mismatch)
                print(f"Failed to restore link for Tuition {new_id}: {e}")

        await session.commit()
        print(f"Successfully relinked {restored_logs_count} logs.")
        print(f"Successfully restored {restored_links_count} meeting links.")

    await engine.dispose()
    print("Tuition ID Fix Complete.")

if __name__ == "__main__":
    asyncio.run(main())
