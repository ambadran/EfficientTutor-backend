'''
Database Handler
'''
import os
import json
import uuid
import random
import string
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash

class DatabaseHandler:
    """
    Handles database interactions for the EfficientTutor user-facing app.
    """
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set.")

    def _get_connection(self):
        """Establishes and returns a new database connection."""
        try:
            return psycopg2.connect(self.database_url)
        except psycopg2.OperationalError as e:
            print(f"!!! DATABASE CONNECTION FAILED: {e} !!!")
            return None

    def check_connection(self):
        """Checks if a connection to the database can be established."""
        conn = self._get_connection()
        if conn:
            conn.close()
            return True
        return False

    # --- User Authentication ---

    def get_user_by_email(self, email):
        """
        Retrieves a single user record from the database by their email.
        """
        with self._get_connection() as conn:
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

        with self._get_connection() as conn:
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
                    print(f"ERROR during signup transaction: {e}")
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
        with self._get_connection() as conn:
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
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                try:
                    self._save_student_transaction(cur, user_id, student_id_str, student_data)
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print(f"ERROR during save_student transaction: {e}")
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
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT notes FROM students WHERE id = %s;",
                    (student_id,)
                )
                result = cur.fetchone()
                #TODO: remove mock data
                result = {'notes':[
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

                    ] }
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
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # --- Step 1: Get all required tuitions for the student ---
                cur.execute(
                    """
                    SELECT id, subject, lesson_index, meeting_link
                    FROM tuitions
                    WHERE %s = ANY(student_ids)
                    ORDER BY subject, lesson_index;
                    """,
                    (student_id,)
                )
                required_tuitions = cur.fetchall()

                if not required_tuitions:
                    return []

                # --- Step 2: Get scheduled times ONLY for those tuitions ---
                #TODO: figure out how to get out start and end time from timetable_runs of a specific student.
                #TODO: this is very similar logic to the get-timetable endpoint so I will develop both together
                # tuition_ids = [t['id'] for t in required_tuitions]
                # cur.execute(
                #     """
                #     SELECT session_id, start_time, end_time
                #     FROM timetable_runs
                #     WHERE session_id = ANY(%s::uuid[]);
                #     """,
                #     (tuition_ids,)
                # )
                # scheduled_times = {row['session_id']: row for row in cur.fetchall()}
                scheduled_times = {}

                # --- Step 3: Merge the results in Python ---
                results = []
                for tuition in required_tuitions:
                    schedule = scheduled_times.get(tuition['id'])
                    
                    start_time = schedule['start_time'].isoformat() if schedule and schedule.get('start_time') else '--'
                    end_time = schedule['end_time'].isoformat() if schedule and schedule.get('end_time') else '--'
                    
                    results.append({
                        "subject": tuition['subject'],
                        "lesson_index": tuition['lesson_index'],
                        "meeting_link": tuition['meeting_link'],
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
        with self._get_connection() as conn:
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
        with self._get_connection() as conn:
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
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM students WHERE id = %s AND user_id = %s;", (student_id, user_id))
                conn.commit()
                return cur.rowcount > 0

    def get_all_student_parameters(self):
        """ Fetches all students with their admin-defined parameters and new columns. """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT id, first_name, last_name, grade, student_data, 
                           cost_per_hour, status, min_duration_mins, max_duration_mins 
                    FROM students;
                """
                cur.execute(query)
                return cur.fetchall()

    def replace_all_tuitions(self, tuitions: list[dict]):
        """
        Wipes the tuitions table and inserts the newly generated list.
        The 'subject' field is a string that matches the database ENUM.
        """
        with self._get_connection() as conn:
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
                        INSERT INTO tuitions (student_ids, subject, lesson_index, cost_per_hour,
                                            min_duration_minutes, max_duration_minutes)
                        -- THE FIX: Cast the student_ids placeholder to uuid[]
                        VALUES (%s::uuid[], %s, %s, %s, %s, %s);
                        """,
                        (
                            t['student_ids'],
                            t['subject'],
                            t['lesson_index'],
                            t['cost_per_hour'],
                            t['min_duration_minutes'],
                            t['max_duration_minutes']
                        )
                    )
                conn.commit()

