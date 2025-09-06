'''
Database Handler
'''
import os
import json
import uuid
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

    def get_user_by_email(self, email):
        """
        THE FIX: This is the missing method.
        Retrieves a single user record from the database by their email.
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
                user = cur.fetchone()
                return user

    def signup_and_login_user(self, email, password):
        """
        Creates a new user and returns their session data in one atomic operation.
        If any part fails, the transaction is rolled back.
        """
        if self.get_user_by_email(email):
            return None, "User with this email already exists"

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:600000')
        new_user_id = str(uuid.uuid4())

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                try:
                    cur.execute(
                        "INSERT INTO users (id, email, password) VALUES (%s, %s, %s) RETURNING id, email, is_first_sign_in;",
                        (new_user_id, email, hashed_password)
                    )
                    user_data = cur.fetchone()
                    conn.commit() # Commit the transaction only if the insert was successful

                    # Format the data for the frontend session
                    return {
                        "id": str(user_data['id']),
                        "email": user_data['email'],
                        "isFirstSignIn": user_data['is_first_sign_in']
                    }, "Signup successful"

                except Exception as e:
                    conn.rollback() # Roll back the transaction on any error
                    print(f"ERROR during signup transaction: {e}")
                    return None, "An internal error occurred during signup."

    def login_user(self, user_record, password):
        """Verifies a password against the stored hash for a given user record."""
        if user_record and check_password_hash(user_record['password'], password):
            return {
                "id": str(user_record['id']),
                "email": user_record['email'],
                "isFirstSignIn": user_record['is_first_sign_in']
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
                    student_obj = row['student_data']
                    
                    # Add the dedicated fields to the top level of the object
                    student_obj['id'] = str(row['id'])
                    student_obj['firstName'] = row['first_name']
                    student_obj['lastName'] = row['last_name']
                    student_obj['grade'] = row['grade']
                    
                    reconstructed_students.append(student_obj)
                    
                return reconstructed_students

    def save_student(self, user_id, student_data):
        """
        Saves a student's data by separating basic info into dedicated columns
        and the rest into the JSONB field. Also handles reciprocal sharing.
        """
        student_id_str = student_data.get('id')
        first_name = student_data.get('firstName')
        last_name = student_data.get('lastName')
        # Handle potential string or int from frontend before it hits the DB
        grade = int(student_data.get('grade')) if student_data.get('grade') else None

        json_data = {k: v for k, v in student_data.items() if k not in ['id', 'firstName', 'lastName', 'grade']}

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # --- Reciprocal Sharing Logic ---
                cur.execute("SELECT student_data FROM students WHERE id = %s;", (student_id_str,))
                old_student_row = cur.fetchone()
                old_shared_with = set(old_student_row['student_data'].get('subjects', [{}])[0].get('sharedWith', [])) if old_student_row else set()
                
                new_subjects = json_data.get('subjects', [])
                new_shared_with = set()
                if new_subjects:
                    new_shared_with = set(new_subjects[0].get('sharedWith', []))

                added_students = new_shared_with - old_shared_with
                removed_students = old_shared_with - new_shared_with
                
                for other_student_id in added_students:
                    cur.execute("UPDATE students SET student_data = jsonb_set(student_data, '{subjects,0,sharedWith}', student_data->'{subjects,0,sharedWith}' || %s::jsonb) WHERE id = %s;", (json.dumps([student_id_str]), other_student_id))
                
                for other_student_id in removed_students:
                    cur.execute("UPDATE students SET student_data = student_data #- '{subjects,0,sharedWith," + str(list(new_shared_with).index(other_student_id)) + "}' WHERE id = %s;", (other_student_id,))

                # --- Main Save Logic ---
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
                    (student_id_str, user_id, first_name, last_name, grade, json.dumps(json_data))
                )

                cur.execute("UPDATE users SET is_first_sign_in = FALSE WHERE id = %s AND is_first_sign_in = TRUE;", (user_id,))
                conn.commit()
                return student_id_str

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
                # Use a transaction to ensure atomicity
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
                        VALUES (%s, %s, %s, %s, %s, %s);
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
                # This will automatically trigger the NOTIFY for your CSP worker
                conn.commit()

