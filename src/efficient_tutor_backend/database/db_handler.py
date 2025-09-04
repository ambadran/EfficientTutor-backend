'''
Database Handler
'''
import os
import json
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

class DatabaseHandler:
    """
    Handles database interactions for the EfficientTutor user-facing app.
    """
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set.")

    def _get_connection(self):
        try:
            return psycopg2.connect(self.database_url)
        except psycopg2.OperationalError as e:
            print(f"!!! DATABASE CONNECTION FAILED: {e} !!!")
            return None

    def check_connection(self):
        conn = self._get_connection()
        if conn:
            conn.close()
            return True
        return False

    def signup_user(self, email, hashed_password):
        """Creates a new user with a hashed password."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
                if cur.fetchone():
                    return None, "User with this email already exists"

                new_user_id = str(uuid.uuid4())
                # The 'parent' role is assigned by default from the database schema
                cur.execute(
                    "INSERT INTO users (id, email, password, is_first_sign_in) VALUES (%s, %s, %s, %s);",
                    (new_user_id, email, hashed_password, True)
                )
                conn.commit()
                
                user_data = {"id": new_user_id, "email": email, "isFirstSignIn": True}
                return user_data, "Signup successful"

    def get_user_by_email(self, email):
        """Fetches a full user record by email to check a password."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
                user = cur.fetchone()
                return user

    def get_students(self, user_id):
        """Retrieves all students for a given user."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT student_data FROM students WHERE user_id = %s;", (user_id,))
                return [row['student_data'] for row in cur.fetchall()]

    def save_student(self, user_id, student_data):
        """Saves a student's data and handles reciprocal sharing logic."""
        student_id = student_data.get('id')
        if not student_id:
             return None # Should not happen with new frontend

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get original data for reciprocal logic
                cur.execute("SELECT student_data FROM students WHERE id = %s;", (student_id,))
                original_student_row = cur.fetchone()
                original_student_data = original_student_row['student_data'] if original_student_row else None

                # Save the primary student's new data
                self._update_student_record(cur, user_id, student_data)

                # Process reciprocal sharing (same logic as before)
                if original_student_data:
                    old_subjects = {s['name']: set(s.get('sharedWith', [])) for s in original_student_data.get('subjects', [])}
                else:
                    old_subjects = {}
                
                new_subjects = {s['name']: set(s.get('sharedWith', [])) for s in student_data.get('subjects', [])}

                all_subject_names = set(old_subjects.keys()) | set(new_subjects.keys())

                for subject_name in all_subject_names:
                    old_shared_with = old_subjects.get(subject_name, set())
                    new_shared_with = new_subjects.get(subject_name, set())

                    # Add reciprocal links
                    for target_student_id in new_shared_with - old_shared_with:
                        self._toggle_reciprocal_link(cur, user_id, target_student_id, student_id, subject_name, 'ADD')
                    
                    # Remove reciprocal links
                    for target_student_id in old_shared_with - new_shared_with:
                        self._toggle_reciprocal_link(cur, user_id, target_student_id, student_id, subject_name, 'REMOVE')

                # Update the user's is_first_sign_in flag if necessary
                cur.execute("UPDATE users SET is_first_sign_in = FALSE WHERE id = %s AND is_first_sign_in = TRUE;", (user_id,))
                
                conn.commit()
                return student_id

    def delete_student(self, user_id, student_id):
        """Deletes a student from the database."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM students WHERE id = %s AND user_id = %s;", (student_id, user_id))
                conn.commit()
                return cur.rowcount > 0

    # --- Helper Methods for save_student ---

    def _update_student_record(self, cur, user_id, student_data):
        """Helper function to update a student record within a transaction."""
        cur.execute(
            """
            INSERT INTO students (id, user_id, student_data)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET student_data = EXCLUDED.student_data;
            """,
            (student_data['id'], user_id, json.dumps(student_data))
        )

    def _toggle_reciprocal_link(self, cur, user_id, target_student_id, source_student_id, subject_name, action):
        """Adds or removes a reciprocal link in another student's record."""
        cur.execute("SELECT student_data FROM students WHERE id = %s;", (target_student_id,))
        target_student_row = cur.fetchone()
        if not target_student_row:
            return

        target_student = target_student_row['student_data']
        for subject in target_student.get('subjects', []):
            if subject['name'] == subject_name:
                if 'sharedWith' not in subject: subject['sharedWith'] = []
                
                if action == 'ADD' and source_student_id not in subject['sharedWith']:
                    subject['sharedWith'].append(source_student_id)
                elif action == 'REMOVE' and source_student_id in subject['sharedWith']:
                    subject['sharedWith'].remove(source_student_id)
                break
        
        self._update_student_record(cur, user_id, target_student)
