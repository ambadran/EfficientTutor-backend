'''
Database Handler
'''
import os
import json
import uuid
import random
import string
import psycopg2
import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from contextlib import contextmanager
from psycopg2 import pool
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from ..common.logger import log

class DatabaseHandler:
    """
    Handles database interactions for the EfficientTutor user-facing app.
    Uses a connection pool for efficient database access.
    """
    _pool = None # Class-level variable to hold the pool

    def __init__(self):
        if not DatabaseHandler._pool:
            load_dotenv()
            self.database_url = os.environ.get('DATABASE_URL')
            if not self.database_url:
                raise ValueError("DATABASE_URL environment variable not set.")
            try:
                # Create a connection pool.
                # minconn=1, maxconn=10 means it will keep 1 connection open
                # and can open up to 10 connections under load.
                DatabaseHandler._pool = pool.SimpleConnectionPool(
                    1, 10, dsn=self.database_url
                )
                log.info("Database connection pool created successfully.")
            except psycopg2.OperationalError as e:
                log.error(f"!!! DATABASE POOL CREATION FAILED: {e} !!!")
                raise

    @contextmanager
    def get_connection(self):
        """
        Provides a database connection from the pool.
        This is a context manager, so it will handle returning the connection
        to the pool automatically.
        Usage: with self.get_connection() as conn: ...
        """
        if not DatabaseHandler._pool:
            raise RuntimeError("Database pool is not initialized.")
        
        conn = None
        try:
            conn = DatabaseHandler._pool.getconn()
            yield conn
        finally:
            if conn:
                DatabaseHandler._pool.putconn(conn)

    def check_connection(self):
        """Checks if a connection from the pool can be established."""
        try:
            with self.get_connection() as conn:
                return conn is not None
        except Exception as e:
            log.error(f"Connection check failed: {e}")
            return False

    # --- User Authentication ---

    def get_user_by_email(self, email):
        """
        Retrieves a single user record from the database by their email.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
                user = cur.fetchone()
                return user

    def signup_and_login_user(self, email, password):
        """
        Creates a new user and returns their session data, now including their role.
        """
        if self.get_user_by_email(email):
            return None, "User with this email already exists"

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:600000')
        new_user_id = str(uuid.uuid4())

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                try:
                    # THE FIX: Add 'role' to the RETURNING clause to get it back from the DB.
                    cur.execute(
                        "INSERT INTO users (id, email, password) VALUES (%s, %s, %s) RETURNING id, email, is_first_sign_in, role;",
                        (new_user_id, email, hashed_password)
                    )
                    user_data = cur.fetchone()
                    conn.commit()
                    
                    # THE FIX: Add the 'role' to the returned user object.
                    return {
                        "id": str(user_data['id']),
                        "email": user_data['email'],
                        "isFirstSignIn": user_data['is_first_sign_in'],
                        "role": user_data['role']
                    }, "Signup successful"

                except Exception as e:
                    conn.rollback()
                    log.error(f"ERROR during signup transaction: {e}")
                    return None, "An internal error occurred during signup."

    def login_user(self, user_record, password):
        """
        Verifies a password and returns the user's session data, now including their role.
        """
        if user_record and check_password_hash(user_record['password'], password):
            # THE FIX: Add the 'role' from the user_record to the returned object.
            return {
                "id": str(user_record['id']),
                "email": user_record['email'],
                "isFirstSignIn": user_record['is_first_sign_in'],
                "role": user_record['role'] 
            }, "Login successful"
        
        return None, "Invalid email or password"

    def get_students(self, user_id):
        """
        Retrieves all students for a user and reconstructs the full student object
        by combining dedicated columns with the remaining JSON data.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Select the new dedicated columns AND the JSON data
                cur.execute(
                    "SELECT id, first_name, last_name, grade, student_data FROM students WHERE user_id = %s;", 
                    (user_id,)
                )
                
                reconstructed_students = []
                for row in cur.fetchall():
                    # Start with the JSON data (subjects, availability, etc.)
                    student_obj = row['student_data'] or {}
                    
                    # Add the dedicated fields to the top level of the object
                    student_obj['id'] = str(row['id'])
                    student_obj['firstName'] = row['first_name']
                    student_obj['lastName'] = row['last_name']
                    student_obj['grade'] = row['grade']
                    
                    reconstructed_students.append(student_obj)
                    
                return reconstructed_students

    def save_student(self, user_id, student_data):
        """
        Saves a student's data and robustly handles reciprocal sharing by directly
        updating only the affected students.
        """
        student_id_str = student_data.get('id')
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                try:
                    self._save_student_transaction(cur, user_id, student_id_str, student_data)
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    log.error(f"ERROR during save_student transaction: {e}")
                    raise

        return student_id_str

    def _save_student_transaction(self, cur, user_id, student_id_str, student_data):
        """The atomic transaction logic for saving a student."""
        first_name = student_data.get('firstName')
        last_name = student_data.get('lastName')
        grade = int(student_data.get('grade')) if student_data.get('grade') else None
        json_data_for_db = {k: v for k, v in student_data.items() if k not in ['id', 'firstName', 'lastName', 'grade']}
        
        # Check if this is a new student by checking the users table first
        cur.execute("SELECT id FROM users WHERE id = %s;", (student_id_str,))
        is_new_user = cur.fetchone() is None

        # Save the student profile data
        cur.execute(
            """
            INSERT INTO students (id, user_id, first_name, last_name, grade, student_data)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET 
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                grade = EXCLUDED.grade,
                student_data = EXCLUDED.student_data;
            """,
            (student_id_str, user_id, first_name, last_name, grade, json.dumps(json_data_for_db))
        )

        if is_new_user:
            self._create_and_store_student_credentials(cur, student_id_str, first_name, last_name)

        # --- Reciprocal Sharing Logic (This part is correct from your provided file) ---
        cur.execute("SELECT student_data FROM students WHERE id = %s;", (student_id_str,))
        old_student_row = cur.fetchone()
        old_subjects = (old_student_row['student_data'] if old_student_row else {}).get('subjects', [])
        new_subjects = json_data_for_db.get('subjects', [])
        all_subject_names = {s['name'] for s in old_subjects} | {s['name'] for s in new_subjects}

        for subject_name in all_subject_names:
            old_subject_data = next((s for s in old_subjects if s['name'] == subject_name), {})
            new_subject_data = next((s for s in new_subjects if s['name'] == subject_name), {})

            old_shared_with = set(old_subject_data.get('sharedWith', []))
            new_shared_with = set(new_subject_data.get('sharedWith', []))
            
            students_to_add_link = new_shared_with - old_shared_with
            students_to_remove_link = old_shared_with - new_shared_with

            for other_student_id in students_to_add_link:
                self._add_reciprocal_link(cur, other_student_id, student_id_str, subject_name)

            for other_student_id in students_to_remove_link:
                self._remove_reciprocal_link(cur, other_student_id, student_id_str, subject_name)

    def _add_reciprocal_link(self, cur, target_student_id, student_id_to_add, for_subject):
        """Helper to add a shared link to the correct subject on another student's record."""
        cur.execute("SELECT student_data FROM students WHERE id = %s FOR UPDATE;", (target_student_id,))
        target_row = cur.fetchone()
        if not target_row: return

        target_data = target_row['student_data'] or {}
        subjects = target_data.setdefault('subjects', [])
        
        target_subject = next((s for s in subjects if s.get('name') == for_subject), None)
        
        if target_subject:
            shared_list = target_subject.setdefault('sharedWith', [])
            if student_id_to_add not in shared_list:
                shared_list.append(student_id_to_add)
                cur.execute("UPDATE students SET student_data = %s WHERE id = %s;", (json.dumps(target_data), target_student_id))
                print(f"SUCCESS: Added reciprocal link for {for_subject} from {student_id_to_add} to {target_student_id}")

    def _remove_reciprocal_link(self, cur, target_student_id, student_id_to_remove, for_subject):
        """Helper to remove a shared link from the correct subject on another student's record."""
        cur.execute("SELECT student_data FROM students WHERE id = %s FOR UPDATE;", (target_student_id,))
        target_row = cur.fetchone()
        if not target_row: return

        target_data = target_row['student_data'] or {}
        subjects = target_data.get('subjects', [])
        
        target_subject = next((s for s in subjects if s.get('name') == for_subject), None)

        if target_subject and 'sharedWith' in target_subject:
            if student_id_to_remove in target_subject['sharedWith']:
                target_subject['sharedWith'].remove(student_id_to_remove)
                cur.execute("UPDATE students SET student_data = %s WHERE id = %s;", (json.dumps(target_data), target_student_id))
                print(f"SUCCESS: Removed reciprocal link for {for_subject} from {student_id_to_remove} from {target_student_id}")

    # --- NEW FUNCTION FOR STUDENT NOTES ---
    def get_student_notes(self, student_id):
        """
        Retrieves the list of notes for a specific student from the 'notes' JSONB column.
        what the notes look like in json 
        [

          {

            "id": "note-123",

            "name": "Algebra Chapter 5 Review",

            "description": "Key concepts and practice problems for the upcoming test.",

            "url": "https://example.com/path/to/algebra_notes.pdf"

          },

          {

            "id": "note-456",

            "name": "Physics Lab Safety",

            "description": "Mandatory reading before the next lab session.",

            "url": "https://example.com/path/to/lab_safety.pdf"

          }

        ] 
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT notes FROM students WHERE id = %s;",
                    (student_id,)
                )
                result = cur.fetchone()
                # If the student exists but has no notes, the 'notes' column might be NULL.
                # In that case, we should return an empty list.
                if result and result['notes']:
                    return result['notes']
                return []

    def get_student_meeting_links(self, student_id):
        """
        Retrieves all scheduled tuitions for a specific student, joining
        the tuition details (like meeting link) with the final scheduled times.
        It now correctly includes tuitions that have not yet been scheduled.
        [
          {
            "subject": "Math",
            "day": "Monday",
            "startTime": "19:00",
            "endTime": "20:00",
            "meetingLink": "https://zoom.us/j/1234567890"
          },
          {
            "subject": "Physics",
            "day": "Wednesday",
            "startTime": "17:30",
            "endTime": "18:30",
            "meetingLink": "https://meet.google.com/xyz-abc-def"
          }
        ]
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # --- Step 1: Get all required tuitions for the student ---
                cur.execute(
                    """
                    SELECT id, student_ids, subject, lesson_index, meeting_link
                    FROM tuitions
                    WHERE %s = ANY(student_ids)
                    ORDER BY subject, lesson_index;
                    """,
                    (student_id,)
                )
                required_tuitions = cur.fetchall()
                if not required_tuitions:
                    return []

                # Step 2: get the name of this student
                cur.execute ("SELECT first_name FROM students WHERE id = %s", (student_id,))
                res = cur.fetchall()
                if not res:
                    raise ValueError("WTF?")
                student_name = res[0]['first_name']

                # --- Step 2: Get scheduled times ONLY for those tuitions ---
                # --- Step 2: Get the latest schedule from the 'timetable_runs' table ---
                cur.execute("SELECT solution_data FROM timetable_runs ORDER BY run_started_at DESC LIMIT 1;")
                latest_run = cur.fetchone()
                
                scheduled_times = {}
                if latest_run and latest_run['solution_data']:
                    solution = latest_run['solution_data']
                    for session in solution:
                        if session.get('category') == 'Tuition' and 'name' in session:
                            scheduled_times[session['name']] = {
                                'start_time': session.get('start_time'),
                                'end_time': session.get('end_time')
                            }

                # Step : filter the scheduled_times_map to only
                scheduled_time_filtered = {}
                for session_name in scheduled_times.keys():
                    if student_name in session_name:
                        scheduled_time_filtered[session_name] = scheduled_times[session_name]

                # --- Step 3: Merge the results in Python ---
                results = []
                for tuition in required_tuitions:

                    # Get the start and end time
                    start_time = '--'
                    end_time = '--'
                    for session_name in scheduled_time_filtered.keys():
                        if tuition['subject'] in session_name and str(tuition['lesson_index']) in session_name:
                            start_time = scheduled_time_filtered[session_name]['start_time']
                            end_time = scheduled_time_filtered[session_name]['end_time']

                            if tuition['meeting_link']:
                                meeting_link = tuition['meeting_link']['meeting_link']
                            else:
                                meeting_link = None
                          
                            results.append({
                                "subject": tuition['subject'],
                                "lesson_index": tuition['lesson_index'],
                                "meeting_link": meeting_link,
                                "start_time": start_time,
                                "end_time": end_time
                            })

                return results

    def _create_and_store_student_credentials(self, cur, student_id, first_name, last_name):
        """
        Creates a user account for a new student, saves the hashed password to the
        users table, and updates the students table with the plaintext password.
        """
        print(f"No user found for student ID {student_id}. Creating new student account...")
        student_email = f"{first_name.lower()}.{last_name.lower()}.{student_id[:4]}@student.et"
        plaintext_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        hashed_password = generate_password_hash(plaintext_password, method='pbkdf2:sha256:600000')
        
        # Step 1: Create the user account with the hashed password.
        cur.execute(
            "INSERT INTO users (id, email, password, role) VALUES (%s, %s, %s, 'student');",
            (student_id, student_email, hashed_password)
        )
        print(f"Successfully created user for student with email: {student_email}")
        
        # Step 2: Update the students table with the plaintext password for the parent to view.
        cur.execute(
            "UPDATE students SET generated_password = %s WHERE id = %s;",
            (plaintext_password, student_id)
        )

    def get_student_credentials(self, parent_user_id, student_id):
        """
        Securely retrieves a student's generated email and password.
        It verifies that the requesting user is the student's parent.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # This query joins users and students to ensure the parent_user_id is correct
                cur.execute(
                    """
                    SELECT u.email, s.generated_password
                    FROM users u
                    JOIN students s ON u.id = s.id
                    WHERE s.id = %s AND s.user_id = %s;
                    """,
                    (student_id, parent_user_id)
                )
                credentials = cur.fetchone()
                return credentials # Returns {'email': '...', 'generated_password': '...'} or None

    def get_student_profile(self, student_id):
        """
        Retrieves the full profile for a single student by their ID.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, first_name, last_name, grade, student_data 
                    FROM students 
                    WHERE id = %s;
                    """,
                    (student_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None

                # Reconstruct the full student object for the frontend
                student_obj = row['student_data'] or {}
                student_obj['id'] = str(row['id'])
                student_obj['firstName'] = row['first_name']
                student_obj['lastName'] = row['last_name']
                student_obj['grade'] = row['grade']
                return student_obj

    def delete_student(self, user_id, student_id):
        """Deletes a student from the database."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM students WHERE id = %s AND user_id = %s;", (student_id, user_id))
                conn.commit()
                return cur.rowcount > 0

    def get_all_student_parameters(self):
        """ Fetches all students with their admin-defined parameters and new columns. """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT id, first_name, last_name, grade, student_data, 
                           cost, status, min_duration_mins, max_duration_mins 
                    FROM students;
                """
                cur.execute(query)
                return cur.fetchall()


    def replace_all_tuitions(self, tuitions: list[dict]):
        """
        Wipes the tuitions table and inserts the newly generated list.
        The 'subject' field is a string that matches the database ENUM.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                
                cur.execute("DELETE FROM tuitions;")
                
                if not tuitions:
                    print("Cleared old tuitions. No new records to insert.")
                    conn.commit()
                    return

                print(f"Cleared old tuitions. Inserting {len(tuitions)} new records...")
                for t in tuitions:
                    cur.execute(
                        """
                        INSERT INTO tuitions (student_ids, subject, lesson_index, cost,
                                            min_duration_minutes, max_duration_minutes)
                        -- THE FIX: Cast the student_ids placeholder to uuid[]
                        VALUES (%s::uuid[], %s, %s, %s, %s, %s);
                        """,
                        (
                            t['student_ids'],
                            t['subject'],
                            t['lesson_index'],
                            t['cost'],
                            t['min_duration_minutes'],
                            t['max_duration_minutes']
                            #TODO: add meeting link here
                        )
                    )
                conn.commit()


    # --- NEW FUNCTION FOR PARENT LOGS ---
    def get_user_logs(self, parent_user_id):
        """
        Fetches all tuition and payment logs for a given parent and computes
        a detailed summary and log list.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Step 1: Fetch all tuition logs for the parent, oldest first.
                cur.execute(
                    "SELECT * FROM tuition_logs WHERE parent_user_id = %s ORDER BY start_time ASC;",
                    (parent_user_id,)
                )
                tuition_logs = cur.fetchall()

                # Step 2: Fetch the total amount paid by the parent.
                cur.execute(
                    "SELECT COALESCE(SUM(amount_paid), 0) AS total FROM payment_logs WHERE parent_user_id = %s;",
                    (parent_user_id,)
                )
                total_paid = float(cur.fetchone()['total'])

                # Step 3: Process the logs in Python to calculate costs and statuses.
                detailed_logs_processed = []
                
                for log in tuition_logs:
                    duration = log['end_time'] - log['start_time']
                    duration_hours = duration.total_seconds() / 3600.0
                    lesson_cost = float(log['cost'])
                    
                    # Format for the detailed log list
                    detailed_logs_processed.append({
                        "id": str(log['id']),
                        "subject": log['subject'],
                        "attendees": log['attendee_names'],
                        "date": log['start_time'].strftime('%Y-%m-%d'),
                        "time_start": log['start_time'].strftime('%H:%M'),
                        "time_end": log['end_time'].strftime('%H:%M'),
                        "duration": f"{duration_hours:.1f}h",
                        "cost": lesson_cost, # Temporary key for status calculation
                    })

                # Step 4: Determine status and unpaid count
                unpaid_count = 0
                paid_balance = total_paid # from payment_logs
                paid_tuition_total = 0
                unpaid_tuition_total = 0
                for log in detailed_logs_processed:
                    if paid_balance > paid_tuition_total:
                        log['status'] = 'Paid'
                        paid_tuition_total += log['cost']
                    else:
                        unpaid_count += 1
                        unpaid_tuition_total += log["cost"]
                        # print(f"tuition cost: {log['cost']}\ncurrent unpaid_tuition_total: {unpaid_tuition_total}")
                        log['status'] = 'Unpaid'

                # Step 5: Calculate the final summary.
                total_due = unpaid_tuition_total
                credit = max(0, paid_tuition_total)
                
                lessons_due = 0
                if credit > 0 and len(tuition_logs) > 0:
                    average_lesson_cost = total_cost / len(tuition_logs)
                    if average_lesson_cost > 0:
                        lessons_due = math.floor(credit / average_lesson_cost)

                summary = {
                    "total_due": float(total_due),
                    "unpaid_count": unpaid_count,
                    "lessons_due": lessons_due
                }

                return {
                    "summary": summary,
                    "detailed_logs": detailed_logs_processed
                }


    def get_student_timetable(self, student_id):
        """
        Fetches the latest completed timetable run, finds the specified student's
        name, and returns a formatted list of their scheduled tuitions for the week.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Step 1: Get the student's first name from their ID.
                cur.execute("SELECT first_name FROM students WHERE id = %s;", (student_id,))
                student_record = cur.fetchone()
                if not student_record:
                    print(f"WARNING: Timetable requested for non-existent student ID: {student_id}")
                    return [] # Return empty list if student not found
                
                student_name = student_record['first_name']

                # Step 2: Fetch the most recent entry from the timetable_runs table.
                cur.execute("SELECT solution_data FROM timetable_runs ORDER BY run_started_at DESC LIMIT 1;")
                latest_run = cur.fetchone()

                if not latest_run or not latest_run['solution_data']:
                    #TODO: IMP: check if timetable is failed, if so, go to previous and so on.
                    print("WARNING: No timetable runs found in the database.")
                    return [] # Return empty list if no schedule has been generated yet

                # Step 3: Parse the solution in Python to find and format the student's tuitions.
                solution_data = latest_run['solution_data']
                student_tuitions = []

                for session in solution_data:
                    # We are only interested in Tuition sessions that involve this student.
                    if session.get('category') == 'Tuition' and student_name in session.get('name', ''):
                        try:
                            # Parse the ISO format datetime strings from the JSON
                            start_dt = datetime.datetime.fromisoformat(session['start_time'])
                            end_dt = datetime.datetime.fromisoformat(session['end_time'])

                            # Extract the subject from the name (e.g., "Tuition_Ali_Math_1")
                            name_parts = session['name'].split('_')
                            subject = name_parts[-2] if len(name_parts) > 2 else "Unknown"

                            formatted_tuition = {
                                "day": start_dt.strftime('%A').lower(), # e.g., "saturday"
                                "subject": subject,
                                "start": start_dt.strftime('%H:%M'), # e.g., "15:00"
                                "end": end_dt.strftime('%H:%M')    # e.g., "16:30"
                            }
                            student_tuitions.append(formatted_tuition)
                        except (ValueError, IndexError) as e:
                            print(f"WARNING: Could not parse session, skipping. Data: {session}, Error: {e}")
                            continue
                
                return student_tuitions


    def get_latest_timetable_run_data(self):
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT solution_data FROM timetable_runs ORDER BY run_started_at DESC LIMIT 1;")
                latest_run = cur.fetchone()

                if latest_run and latest_run['solution_data']:
                    return latest_run['solution_data']
 
    def get_student_name_from_id(self, student_id) -> Optional[tuple[str, str]]:
        '''

        '''
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute ("SELECT first_name, last_name FROM students WHERE id = %s", (student_id,))
                res = cur.fetchall()
                if not res:
                    return None
                # full_name = f"{res[0]['first_name']} {res[0]['last_name']}"
                # return full_name
                return res[0]['first_name'], res[0]['last_name']


#### v0.3 stuff

# methods for tuition log tuition list choosing
    def get_active_tuitions(self):
        """Fetches all records from the 'tuitions' table."""
        #TODO: check if it did indeed returns any data
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, student_ids, subject, lesson_index, cost FROM tuitions;")
                return cur.fetchall()

    
    def get_latest_successful_schedule(self):
        """
        Fetches the most recent, successfully or manually completed timetable run.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # MODIFICATION: Include 'MANUAL' in the status check
                cur.execute("""
                    SELECT solution_data 
                    FROM timetable_runs 
                    WHERE status IN ('SUCCESS', 'MANUAL') 
                    ORDER BY run_started_at DESC 
                    LIMIT 1;
                """)
                schedule = cur.fetchone()
                
                # NEW: Check if data was returned and log a warning if not
                if not schedule:
                    log.warning("No 'SUCCESS' or 'MANUAL' timetable runs found in the database.")
                
                return schedule
                
    def get_student_id_to_name_map(self):
        """Returns a dictionary mapping student UUIDs to their first names."""
        #TODO: check if it did indeed returns any data
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, first_name FROM students;")
                # Convert UUID objects to strings for consistent keying
                return {str(row['id']): row['first_name'] for row in cur.fetchall()}


# methods for tuition log manual choosing
    def get_all_students_basic_info(self):
        """
        Fetches a list of all students with their ID and full name.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, first_name, last_name FROM students ORDER BY first_name, last_name;"
                )
                return cur.fetchall()

    def get_subject_enum_values(self):
        """
        Dynamically fetches the possible values for the 'subject_enum' type.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur: # No RealDictCursor needed
                # This query inspects PostgreSQL's system catalogs for the enum values
                cur.execute("""
                    SELECT e.enumlabel
                    FROM pg_type t
                    JOIN pg_enum e ON t.oid = e.enumtypid
                    WHERE t.typname = 'subject_enum'
                    ORDER BY e.enumsortorder;
                """)
                # The result is a list of tuples, so we extract the first element of each
                return [row[0] for row in cur.fetchall()]

# methods for tuition log to actually log stuff
    def get_tuition_details_by_id(self, tuition_id):
        """Fetches a single tuition's details by its UUID."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT student_ids, subject, lesson_index, cost FROM tuitions WHERE id = %s;",
                    (tuition_id,)
                )
                return cur.fetchone()

    def get_parent_id_for_student(self, student_id):
        """Finds the parent (user_id) associated with a given student."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT user_id FROM students WHERE id = %s;", (student_id,))
                result = cur.fetchone()
                return str(result['user_id']) if result else None
    
    def get_student_names_by_ids(self, student_ids: list):
        """
        Takes a list of student UUIDs and returns a list of their first names.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Use ANY() for an efficient query with a list of IDs
                # MODIFICATION: Add ::uuid[] to cast the text array to a uuid array
                cur.execute(
                    "SELECT first_name FROM students WHERE id = ANY(%s::uuid[]);",
                    (student_ids,)
                )
                return [row[0] for row in cur.fetchall()]

    def insert_tuition_log(self, log_payload: dict) -> str:
        """Inserts a new record into the tuition_logs table."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO tuition_logs (
                            id, create_type, tuition_id, parent_user_id, subject, attendee_names,
                            lesson_index, cost, start_time, end_time
                        ) VALUES (
                            %(id)s, %(create_type)s, %(tuition_id)s, %(parent_user_id)s, %(subject)s, %(attendee_names)s,
                            %(lesson_index)s, %(cost)s, %(start_time)s, %(end_time)s
                        );
                    """, log_payload)
                    conn.commit()
                    return log_payload['id']
        except Exception as e:
            # NEW: Log the detailed error and the payload that caused it
            log.error(f"Failed to insert tuition log. Error: {e}")
            log.error(f"Failing payload: {log_payload}")
            # Re-raise the exception so the service layer can handle it
            raise
                
    def insert_payment_log(self, payment_data: dict) -> str:
        """Inserts a new record into the payment_logs table."""
        payment_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO payment_logs (id, parent_user_id, amount_paid, payment_date, notes)
                    VALUES (%s, %s, %s, %s, %s);
                """, (
                    payment_id,
                    payment_data['parent_user_id'],
                    payment_data['amount_paid'],
                    payment_data.get('payment_date'), # Can be None to use DB default
                    payment_data.get('notes')
                ))
                conn.commit()
                return payment_id

    def void_tuition_log(self, log_id: str) -> bool:
        """Sets a tuition log's status to 'VOID'. Returns True if a row was updated."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tuition_logs SET status = 'VOID' WHERE id = %s AND status = 'ACTIVE';",
                    (log_id,)
                )
                conn.commit()
                # cur.rowcount will be 1 if the update was successful, 0 otherwise
                return cur.rowcount > 0

    def link_corrected_log(self, new_log_id: str, original_log_id: str):
        """Updates the new log to link it to the one it corrected."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tuition_logs SET corrected_from_log_id = %s WHERE id = %s;",
                    (original_log_id, new_log_id)
                )
                conn.commit()

# methods to get payment data to create financial data to view
    def get_tuition_logs_for_parent(self, parent_user_id: str):
        """
        Fetches all active tuition logs for a parent, ordered chronologically,
        with timestamps converted to the application's timezone.
        """
        timezone = self.get_user_timezone(parent_user_id)
        log.info(f"Fetching tuition logs for parent_id: {parent_user_id} in timezone: {timezone}")
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # MODIFICATION: Use AT TIME ZONE to convert timestamps
                    cur.execute("""
                        SELECT 
                            id, 
                            subject, 
                            attendee_names, 
                            start_time AT TIME ZONE %(tz)s AS start_time, 
                            end_time AT TIME ZONE %(tz)s AS end_time, 
                            cost
                        FROM tuition_logs
                        WHERE parent_user_id = %(parent_id)s AND status = 'ACTIVE'
                        ORDER BY start_time ASC;
                    """, {'tz': timezone, 'parent_id': parent_user_id})
                    
                    logs = cur.fetchall()
                    if not logs:
                        log.info(f"No active tuition logs found for parent_id: {parent_user_id}")
                    return logs
        except Exception as e:
            log.error(f"Database error fetching tuition logs for parent {parent_user_id}: {e}", exc_info=True)
            raise

    def get_payment_logs_for_parent(self, parent_user_id: str):
        """
        Fetches all payment logs for a parent, with timestamps converted
        to the application's timezone.
        """
        timezone = self.get_user_timezone(parent_user_id)
        log.info(f"Fetching payment logs for parent_id: {parent_user_id} in timezone: {timezone}")
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # MODIFICATION: Use AT TIME ZONE to convert timestamps
                    cur.execute("""
                        SELECT 
                            amount_paid, 
                            payment_date AT TIME ZONE %(tz)s AS payment_date, 
                            notes 
                        FROM payment_logs 
                        WHERE parent_user_id = %(parent_id)s 
                        ORDER BY payment_date ASC;
                    """, {'tz': timezone, 'parent_id': parent_user_id})
                    
                    payments = cur.fetchall()
                    if not payments:
                        log.info(f"No payment logs found for parent_id: {parent_user_id}")
                    return payments
        except Exception as e:
            log.error(f"Database error fetching payment logs for parent {parent_user_id}: {e}", exc_info=True)
            raise

    def get_all_tuition_logs(self, viewer_id: str):
        """
        Fetches all tuition logs from the database, converting UTC timestamps
        to the application's configured timezone.
        """
        timezone = self.get_user_timezone(viewer_id)
        log.info(f"Fetching all tuition logs converting to timezone: {timezone}")
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # MODIFICATION: Use AT TIME ZONE to convert the timestamps
                    cur.execute("""
                        SELECT 
                            id, 
                            attendee_names, 
                            subject, 
                            start_time AT TIME ZONE %(tz)s AS start_time, 
                            end_time AT TIME ZONE %(tz)s AS end_time, 
                            cost, 
                            status, 
                            corrected_from_log_id 
                        FROM tuition_logs 
                        ORDER BY start_time DESC;
                    """, {'tz': timezone})
                    
                    logs = cur.fetchall()
                    if not logs:
                        log.info("No tuition logs found in the database.")
                    return logs
        except Exception as e:
            log.error(f"Database error while fetching all tuition logs: {e}", exc_info=True)
            raise


    def get_user_timezone(self, user_id: str) -> str:
        """Fetches the timezone for a specific user."""
        log.info(f"Fetching timezone for user_id: {user_id}")
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT timezone FROM users WHERE id = %s;", (user_id,))
                    result = cur.fetchone()
                    if result:
                        return result[0]
                    # Fallback to UTC if user not found or has no timezone
                    log.warning(f"Could not find timezone for user {user_id}. Defaulting to UTC.")
                    return 'UTC'
        except Exception as e:
            log.error(f"Database error fetching timezone for user {user_id}: {e}", exc_info=True)
            return 'UTC'
