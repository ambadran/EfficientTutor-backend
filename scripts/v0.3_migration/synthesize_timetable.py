"""
Script to synthesize Timetable data during v0.3 migration.
This populates the empty `timetable_runs`, `timetable_run_user_solutions`,
and `timetable_solution_slots` tables based on a provided schedule.
"""

import asyncio
import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("synthesize_timetable")

# --- Hardcoded Schedule Data --- 
SCHEDULE_DATA = [
 {"name": "Tuition_Lily_Math_1",
  "category": "Tuition",
  "start_time": "2025-11-08T12:30:00",
  "end_time": "2025-11-08T14:00:00"},
 {"name": "Tuition_Omran_IT_1",
  "category": "Tuition",
  "start_time": "2025-11-08T14:00:00",
  "end_time": "2025-11-08T15:30:00"},
 {"name": "Tuition_Ali_Math_1",
  "category": "Tuition",
  "start_time": "2025-11-08T15:30:00",
  "end_time": "2025-11-08T17:00:00"},
 {"name": "Tuition_Abdullah_Math_1",
  "category": "Tuition",
  "start_time": "2025-11-08T17:00:00",
  "end_time": "2025-11-08T18:30:00"},
 {"name": "Tuition_Omran_Mila_Math_1",
  "category": "Tuition",
  "start_time": "2025-11-08T18:30:00",
  "end_time": "2025-11-08T20:00:00"},

 {"name": "Tuition_Abdullah_Biology_1",
  "category": "Tuition",
  "start_time": "2025-11-09T15:00:00",
  "end_time": "2025-11-09T16:30:00"},
 {"name": "Tuition_Adham_Chemistry_1",
  "category": "Tuition",
  "start_time": "2025-11-09T16:30:00",
  "end_time": "2025-11-09T18:00:00"},
 {"name": "Tuition_Yassin_Math_1",
  "category": "Tuition",
  "start_time": "2025-11-09T18:00:00",
  "end_time": "2025-11-09T19:30:00"},
 {"name": "Tuition_Lily_Physics_1",
  "category": "Tuition",
  "start_time": "2025-11-09T19:30:00",
  "end_time": "2025-11-09T21:00:00"},

 {"name": "Tuition_Yassin_Physics_1",
  "category": "Tuition",
  "start_time": "2025-11-10T15:30:00",
  "end_time": "2025-11-10T17:00:00"},
 {"name": "Tuition_Ali_Physics_1",
  "category": "Tuition",
  "start_time": "2025-11-10T17:00:00",
  "end_time": "2025-11-10T18:30:00"},
 {"name": "Tuition_Omran_Mila_Physics_1",
  "category": "Tuition",
  "start_time": "2025-11-10T18:30:00",
  "end_time": "2025-11-10T20:00:00"},
 {"name": "Tuition_Abdullah_Physics_1",
  "category": "Tuition",
  "start_time": "2025-11-10T19:30:00",
  "end_time": "2025-11-10T21:00:00"},

 {"name": "Tuition_Abdullah_Chemistry_1",
  "category": "Tuition",
  "start_time": "2025-11-11T15:00:00",
  "end_time": "2025-11-11T16:30:00"},
 {"name": "Tuition_Jacob_Math_1",
  "category": "Tuition",
  "start_time": "2025-11-11T16:30:00",
  "end_time": "2025-11-11T18:00:00"},
 {"name": "Tuition_Lily_Math_2",
  "category": "Tuition",
  "start_time": "2025-11-11T18:00:00",
  "end_time": "2025-11-11T19:30:00"},
 {"name": "Tuition_Yassin_Chemistry_1",
  "category": "Tuition",
  "start_time": "2025-11-11T19:30:00",
  "end_time": "2025-11-11T21:00:00"},

 {"name": "Tuition_Adham_Physics_1",
  "category": "Tuition",
  "start_time": "2025-11-12T15:30:00",
  "end_time": "2025-11-12T17:00:00"},
 {"name": "Tuition_Ali_Chemistry_1",
  "category": "Tuition",
  "start_time": "2025-11-12T17:00:00",
  "end_time": "2025-11-12T18:30:00"},
 {"name": "Tuition_Omran_Mila_Chemistry_1",
  "category": "Tuition",
  "start_time": "2025-11-12T18:30:00",
  "end_time": "2025-11-12T20:00:00"},

 {"name": "Tuition_Jacob_Physics_1",
  "category": "Tuition",
  "start_time": "2025-11-13T14:15:00",
  "end_time": "2025-11-13T15:45:00"},
 {"name": "Tuition_Lily_Physics_2",
  "category": "Tuition",
  "start_time": "2025-11-13T18:00:00",
  "end_time": "2025-11-13T19:30:00"}
]


def load_env():
    """Load env vars manually."""
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

def parse_schedule_item(item):
    """
    Parses a schedule item to extract lookup criteria and timing.
    Returns:
        names (set): Set of student first names (lowercase).
        subject (str): Subject name (lowercase).
        index (int): Lesson index.
        day_of_week (int): 1-7.
        start_time (str): HH:MM:SS.
        end_time (str): HH:MM:SS.
    """
    # Name format: Tuition_{Names}_{Subject}_{Index}
    # e.g. Tuition_Omran_Mila_Physics_1
    parts = item['name'].split('_')
    # parts[0] is 'Tuition'
    # parts[-1] is index
    # parts[-2] is subject
    # parts[1:-2] are student names
    
    lesson_index = int(parts[-1])
    subject = parts[-2].lower()
    student_names = {n.lower() for n in parts[1:-2]}
    
    dt_start = datetime.fromisoformat(item['start_time'])
    dt_end = datetime.fromisoformat(item['end_time'])
    
    # ISO weekday: Mon=1, Sun=7
    day_of_week = dt_start.isoweekday()
    
    return {
        "names": student_names,
        "subject": subject,
        "index": lesson_index,
        "day_of_week": day_of_week,
        "start_time": dt_start.time(),
        "end_time": dt_end.time()
    }

async def build_tuition_lookup(session: AsyncSession):
    """
    Builds a map: (frozenset(student_names), subject, index) -> tuition_row
    """
    # Fetch Tuitions with their Students
    # We join tuition_template_charges to get student IDs, then students table to get first_names
    query = text("""
        SELECT 
            t.id as tuition_id,
            t.subject,
            t.lesson_index,
            t.teacher_id,
            array_agg(u.first_name) as student_names,
            array_agg(s.id) as student_ids
        FROM tuitions t
        JOIN tuition_template_charges ttc ON t.id = ttc.tuition_id
        JOIN students s ON ttc.student_id = s.id
        JOIN users u ON s.id = u.id
        GROUP BY t.id, t.subject, t.lesson_index, t.teacher_id
    """)
    
    result = await session.execute(query)
    lookup = {}
    
    for row in result.mappings():
        # normalize key
        names = frozenset(n.lower() for n in row['student_names'])
        subject = row['subject'].lower()
        index = row['lesson_index']
        
        key = (names, subject, index)
        lookup[key] = {
            "tuition_id": row['tuition_id'],
            "teacher_id": row['teacher_id'],
            "student_ids": row['student_ids']
        }
    
    return lookup

async def main():
    parser = argparse.ArgumentParser(description="Synthesize Timetable.")
    parser.add_argument("--prod", action="store_true", help="Run against PRODUCTION database.")
    args = parser.parse_args()

    load_env()
    
    if args.prod:
        target_env = "DATABASE_URL_PROD_CLI"
    else:
        target_env = "DATABASE_URL_TEST_CLI"

    db_url = os.getenv(target_env)
    if not db_url:
        logger.error(f"{target_env} not set")
        return

    # Ensure async
    if db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    print(f"Connecting to database ({target_env})...")
    engine = create_async_engine(db_url, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    logger.info("Starting Timetable Synthesis...")

    async with AsyncSessionLocal() as session:
        async with session.begin(): # Transaction start
            
            # 1. Resolve Tuitions
            tuition_lookup = await build_tuition_lookup(session)
            logger.info(f"Loaded {len(tuition_lookup)} tuitions from DB.")
            
            resolved_schedule = []
            for item in SCHEDULE_DATA:
                criteria = parse_schedule_item(item)
                key = (frozenset(criteria['names']), criteria['subject'], criteria['index'])
                
                if key in tuition_lookup:
                    resolved = tuition_lookup[key]
                    resolved.update(criteria) # add timing info
                    resolved_schedule.append(resolved)
                else:
                    logger.warning(f"Could not resolve tuition for: {item['name']} (Key: {key})")

            logger.info(f"Resolved {len(resolved_schedule)} schedule items.")

            # 2. Create Master Run
            # Get Max ID
            res = await session.execute(text("SELECT MAX(id) FROM timetable_runs"))
            max_id = res.scalar() or 0
            new_run_id = max_id + 1
            
            logger.info(f"Creating Master Run ID: {new_run_id}")
            
            await session.execute(text("""
                INSERT INTO timetable_runs (id, run_started_at, status, input_version_hash, trigger_source)
                VALUES (:id, :now, 'SUCCESS', 'migration_synthesis', 'v0.3_migration')
            """), {"id": new_run_id, "now": datetime.now(timezone.utc)})
            
            # 3. Create User Solutions
            # Fetch all users (teachers + students)
            # Actually, we need users who are active.
            # We can just fetch all users from the users table that are parents, teachers or students?
            # Actually, we need solutions for Teachers and Students. Parents don't have timetables (usually).
            # But availability is linked to 'users' table.
            
            # Strategy: Create solutions for ALL users who have availability OR are part of a tuition.
            
            # For simplicity in this migration, let's create solutions for ALL users with role 'student' or 'teacher'.
            users_res = await session.execute(text("""
                SELECT id FROM users WHERE role IN ('student', 'teacher')
            """))
            user_ids = [row[0] for row in users_res.fetchall()]
            
            user_solution_map = {} # user_id -> solution_id
            
            logger.info(f"Creating solutions for {len(user_ids)} users...")
            
            for uid in user_ids:
                # Create Solution
                sol_id_res = await session.execute(text("""
                    INSERT INTO timetable_run_user_solutions (timetable_run_id, user_id)
                    VALUES (:run_id, :uid)
                    RETURNING id
                """), {"run_id": new_run_id, "uid": uid})
                sol_id = sol_id_res.scalar()
                user_solution_map[uid] = sol_id
            
            # 4. Migrate Availability
            logger.info("Migrating Availability Intervals...")
            # We insert slots for each availability interval
            # linking to the user's solution.
            
            # Fetch all intervals
            intervals_res = await session.execute(text("SELECT * FROM availability_intervals"))
            intervals = intervals_res.mappings().all()
            
            for interval in intervals:
                uid = interval['user_id']
                if uid not in user_solution_map:
                    continue # Should not happen if we selected all students/teachers
                
                sol_id = user_solution_map[uid]
                
                await session.execute(text("""
                    INSERT INTO timetable_solution_slots (
                        solution_id, name, day_of_week, start_time, end_time, availability_interval_id
                    ) VALUES (
                        :sol_id, :name, :dow, :start, :end, :aid
                    )
                """), {
                    "sol_id": sol_id,
                    "name": "Availability", # Generic name
                    "dow": interval['day_of_week'],
                    "start": interval['start_time'],
                    "end": interval['end_time'],
                    "aid": interval['id']
                })

            # 5. Insert Tuition Slots
            logger.info("Scheduling Tuitions...")
            
            for item in resolved_schedule:
                tuition_id = item['tuition_id']
                teacher_id = item['teacher_id']
                student_ids = item['student_ids']
                
                dow = item['day_of_week']
                start = item['start_time']
                end = item['end_time']
                
                # Teacher Slot
                if teacher_id and teacher_id in user_solution_map:
                    await session.execute(text("""
                        INSERT INTO timetable_solution_slots (
                            solution_id, name, day_of_week, start_time, end_time, tuition_id, participant_ids
                        ) VALUES (
                            :sol_id, :name, :dow, :start, :end, :tid, :pids
                        )
                    """), {
                        "sol_id": user_solution_map[teacher_id],
                        "name": f"Tuition: {item['subject'].capitalize()} ({', '.join(sorted(item['names'])).title()})",
                        "dow": dow,
                        "start": start,
                        "end": end,
                        "tid": tuition_id,
                        "pids": student_ids # Store student IDs as participants for teacher
                    })
                
                # Student Slots
                for sid in student_ids:
                    if sid in user_solution_map:
                        await session.execute(text("""
                            INSERT INTO timetable_solution_slots (
                                solution_id, name, day_of_week, start_time, end_time, tuition_id, participant_ids
                            ) VALUES (
                                :sol_id, :name, :dow, :start, :end, :tid, :pids
                            )
                        """), {
                                                    "sol_id": user_solution_map[sid],
                                                    "name": f"Tuition: {item['subject'].capitalize()} ({', '.join(sorted(item['names'])).title()})",
                                                    "dow": dow,
                                                    "start": start,
                                                    "end": end,
                                                    "tid": tuition_id,
                                                    "pids": [teacher_id] if teacher_id else [] # Store teacher ID as participant for student
                                                })
    logger.info("Timetable Synthesis Complete.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())