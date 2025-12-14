"""
(V0.3) standalone script to Regenerate Tuition IDs to be Deterministic.

This script:
1. Preserves the linkage between existing Tuition Logs and their Tuitions.
2. Calls the TuitionService.regenerate_all_tuitions() method.
   - This method wipes the current 'tuitions' table.
   - It rebuilds it based on 'student_subjects' and 'student_subject_sharings'.
   - It generates DETERMINISTIC UUIDs for the new tuitions.
3. Restores the linkage for Tuition Logs by calculating the matching Deterministic ID
   for the preserved attributes.
"""

import asyncio
import sys
import os
import hashlib
from pathlib import Path
from uuid import UUID
from typing import List, Dict, Any, Tuple

from sqlalchemy import select, text, update
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
    load_env()
    db_url = os.getenv("DATABASE_URL_TEST_CLI")
    if not db_url:
        print("ERROR: DATABASE_URL_TEST_CLI not set.")
        return
    
    # Ensure async
    if db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    print("Connecting to database...")
    engine = create_async_engine(db_url, echo=False)
    AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        # We need to construct the services manually (dependency injection doesn't work here)
        # UserService is needed by TuitionService init, though strictly not used by regenerate_all_tuitions
        user_svc = UserService(session) 
        tuition_svc = TuitionService(session, user_svc)

        print("--- Step 1: Preserving Tuition Log Linkages ---")
        # We need to capture enough info from the OLD tuition to calculate the NEW deterministic ID.
        # The key factors are: Subject, Ed System, Grade, Lesson Index, Teacher, and Student Group.
        
        # Fetch logs that have a tuition_id
        # Join Tuitions to get the attributes
        # Join TuitionTemplateCharges -> Students to get the student group
        
        # 1. Get all logs with a tuition_id
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
        
        result = await session.execute(logs_stmt)
        preserved_logs = result.mappings().all()
        print(f"Preserved attributes for {len(preserved_logs)} logs.")

        print("--- Step 2: Regenerating Tuitions (Deterministic IDs) ---")
        # This will wipe 'tuitions' and rebuild from 'student_subjects'
        success = await tuition_svc.regenerate_all_tuitions()
        if not success:
            print("Regeneration failed or returned False.")
            return
        
        # At this point, old tuitions are gone. Logs have tuition_id = NULL (due to ON DELETE SET NULL).
        # We must re-link them.

        print("--- Step 3: Restoring Log Linkages ---")
        restored_count = 0
        
        for p_log in preserved_logs:
            # Calculate what the NEW ID should be for these attributes
            new_id = generate_deterministic_id(
                subject=p_log['subject'],
                educational_system=p_log['educational_system'],
                grade=p_log['grade'],
                lesson_index=p_log['lesson_index'],
                teacher_id=p_log['teacher_id'],
                student_ids=p_log['student_ids']
            )
            
            # Update the log
            # We assume the regeneration created this ID. If not (e.g. data mismatch), 
            # the update might point to a non-existent ID (IntegrityError) OR we check first.
            # To be safe, we just try to update. If FK fails, it means regeneration 
            # didn't produce a tuition for this group (which implies data inconsistency).
            
            try:
                await session.execute(
                    update(db_models.TuitionLogs)
                    .where(db_models.TuitionLogs.id == p_log['log_id'])
                    .values(tuition_id=new_id)
                )
                restored_count += 1
            except Exception as e:
                print(f"Failed to relink Log {p_log['log_id']} to Tuition {new_id}: {e}")

        await session.commit()
        print(f"Successfully relinked {restored_count} logs.")

    await engine.dispose()
    print("Tuition ID Fix Complete.")

if __name__ == "__main__":
    asyncio.run(main())
