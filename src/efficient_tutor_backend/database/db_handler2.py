'''

'''
import os
import logging
from uuid import UUID
from contextlib import contextmanager
from typing import Any, Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from ..common.logger import log

class DatabaseHandler:
    """
    Handles all database interactions for the application.
    Uses a connection pool for efficient database access and includes methods
    for creating, reading, updating, and deleting user data.
    """
    _pool = None

    def __init__(self):
        if not DatabaseHandler._pool:
            load_dotenv()
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                log.critical("!!! DATABASE_URL environment variable not set. !!!")
                raise ValueError("DATABASE_URL environment variable not set.")
            try:
                DatabaseHandler._pool = pool.SimpleConnectionPool(
                    1, 10, dsn=database_url
                )
                log.info("Database connection pool created successfully.")
            except psycopg2.OperationalError as e:
                log.critical(f"!!! DATABASE POOL CREATION FAILED: {e} !!!", exc_info=True)
                raise

    @contextmanager
    def get_connection(self):
        """
        Provides a database connection from the pool as a context manager.
        """
        if not DatabaseHandler._pool:
            log.error("Database pool is not initialized.")
            raise RuntimeError("Database pool is not initialized.")
        
        conn = None
        try:
            conn = DatabaseHandler._pool.getconn()
            yield conn
        finally:
            if conn:
                DatabaseHandler._pool.putconn(conn)

    # --- ENUM Handling ---
    def get_enum_labels(self, type_name: str) -> list[str]:
        """
        Dynamically fetches the labels for a given PostgreSQL ENUM type.
        
        Args:
            type_name: The name of the enum type in the database (e.g., 'user_role').

        Returns:
            A list of strings representing the enum labels.
        """
        log.info(f"Fetching labels for ENUM type '{type_name}'...")
        query = """
            SELECT e.enumlabel
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = %s
            ORDER BY e.enumsortorder;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (type_name,))
                    results = cur.fetchall()
                    if not results:
                        raise ValueError(f"No labels found for ENUM type '{type_name}'.")
                    labels = [row[0] for row in results]
                    log.info(f"Successfully fetched labels for '{type_name}': {labels}")
                    return labels
        except Exception as e:
            log.error(f"Failed to fetch ENUM labels for '{type_name}': {e}", exc_info=True)
            raise
            
    # --- User Retrieval (Read Operations) ---
    def _get_unified_user(self, key_column: str, value: Any) -> Optional[dict[str, Any]]:
        """
        Internal helper to fetch a unified user record by a specific key.
        This joins all user-related tables to create a complete user object.
        """
        log.info(f"Fetching unified user where {key_column} = {value}")
        # NOTE: We select specific columns to avoid fetching legacy ones
        # and the password hash, which should not leave the DB layer.
        query = """
            SELECT
                u.id, u.email, u.is_first_sign_in, u.role, u.timezone,
                u.first_name, u.last_name,
                p.currency,
                s.parent_id, s.student_data, s.cost, s.status,
                s.min_duration_mins, s.max_duration_mins, s.grade,
                s.generated_password
            FROM users u
            LEFT JOIN parents p ON u.id = p.id
            LEFT JOIN students s ON u.id = s.id
            WHERE u.{key} = %s;
        """.format(key=key_column) # Using format for the column name is safe here

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (value,))
                    user_data = cur.fetchone()
                    if not user_data:
                        log.warning(f"No user found with {key_column} = {value}")
                        return None
                    return dict(user_data)
        except Exception as e:
            log.error(f"Error fetching user by {key_column} '{value}': {e}", exc_info=True)
            return None

    def get_user_by_id(self, user_id: UUID) -> Optional[dict[str, Any]]:
        """Fetches a complete, unified user record by their UUID."""
        return self._get_unified_user('id', user_id)

    def get_user_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """Fetches a complete, unified user record by their email."""
        return self._get_unified_user('email', email)
        
    def get_students_by_parent_id(self, parent_id: UUID) -> list[dict[str, Any]]:
        """Fetches all students associated with a specific parent ID."""
        log.info(f"Fetching all students for parent_id: {parent_id}")
        # This query is specific to students and can be more direct
        query = """
            SELECT
                u.id, u.email, u.is_first_sign_in, u.role, u.timezone,
                u.first_name, u.last_name,
                s.parent_id, s.student_data, s.cost, s.status,
                s.min_duration_mins, s.max_duration_mins, s.grade,
                s.generated_password
            FROM users u
            JOIN students s ON u.id = s.id
            WHERE s.parent_id = %s;
        """
        results = []
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (parent_id,))
                    results = [dict(row) for row in cur.fetchall()]
        except Exception as e:
            log.error(f"Error fetching students for parent {parent_id}: {e}", exc_info=True)
        return results

    # --- User Creation (Write Operations) ---
    def create_parent(self, email: str, password: str, first_name: str, last_name: str, currency: str = 'EGP') -> Optional[UUID]:
        """
        Creates a new parent user in a single transaction.
        Handles hashing the password and creating records in 'users' and 'parents'.
        """
        log.info(f"Attempting to create a new parent user for email: {email}")
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:600000')
        new_user_id = uuid.uuid4()

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    # Insert into users table
                    cur.execute(
                        """
                        INSERT INTO users (id, email, password, role, first_name, last_name)
                        VALUES (%s, %s, %s, 'parent', %s, %s);
                        """,
                        (new_user_id, email, hashed_password, first_name, last_name)
                    )
                    # Insert into parents table
                    cur.execute(
                        "INSERT INTO parents (id, currency) VALUES (%s, %s);",
                        (new_user_id, currency)
                    )
                    conn.commit()
                    log.info(f"Successfully created parent with ID: {new_user_id}")
                    return new_user_id
                except Exception as e:
                    conn.rollback()
                    log.error(f"Transaction failed for creating parent {email}: {e}", exc_info=True)
                    return None

    def get_all_users_by_role(self, role: str) -> list[dict[str, Any]]:
        """
        Fetches all unified user records for a specific role.
        """
        log.info(f"Fetching all users with role: '{role}'")
        query = """
            SELECT
                u.id, u.email, u.is_first_sign_in, u.role, u.timezone,
                u.first_name, u.last_name,
                p.currency,
                s.parent_id, s.student_data, s.cost, s.status,
                s.min_duration_mins, s.max_duration_mins, s.grade,
                s.generated_password
            FROM users u
            LEFT JOIN parents p ON u.id = p.id
            LEFT JOIN students s ON u.id = s.id
            WHERE u.role = %s;
        """
        results = []
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (role,))
                    results = [dict(row) for row in cur.fetchall()]
        except Exception as e:
            log.error(f"Error fetching all users with role '{role}': {e}", exc_info=True)
        return results                   
    # ... Other creation methods for Teacher, Student, etc. would follow a similar pattern ...

    # --- User Deletion ---
    def delete_user(self, user_id: UUID) -> bool:
        """
        Deletes a user from the 'users' table.
        Due to 'ON DELETE CASCADE' constraints, records in 'students', 'parents',
        or 'teachers' tables will be deleted automatically.
        """
        log.info(f"Attempting to delete user with ID: {user_id}")
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
                    # Check if any row was actually deleted
                    if cur.rowcount == 0:
                        log.warning(f"No user found with ID {user_id} to delete.")
                        return False
                    conn.commit()
                    log.info(f"Successfully deleted user with ID: {user_id}")
                    return True
                except Exception as e:
                    conn.rollback()
                    log.error(f"Failed to delete user {user_id}: {e}", exc_info=True)
                    return False

    def check_tuition_data_integrity(self) -> list[dict[str, Any]]:
        """
        Finds tuitions that have missing linked data and would fail a strict JOIN.
        This is a diagnostic tool to identify data integrity problems.
        Returns a list of problematic tuition IDs and the reason for the failure.
        """
        log.info("Running tuition data integrity check...")
        # This query finds tuitions with either a missing/NULL teacher or no charge records.
        query = """
        SELECT
            t.id AS tuition_id,
            t.teacher_id,
            CASE
                WHEN t.teacher_id IS NULL THEN 'Teacher ID is NULL'
                WHEN u.id IS NULL THEN 'Teacher ID does not exist in users table'
                ELSE NULL
            END AS teacher_issue,
            CASE
                WHEN ttc.tuition_id IS NULL THEN 'No records in tuition_template_charges'
                ELSE NULL
            END AS charges_issue
        FROM tuitions t
        LEFT JOIN users u ON t.teacher_id = u.id
        LEFT JOIN tuition_template_charges ttc ON t.id = ttc.tuition_id
        WHERE
            u.id IS NULL OR ttc.tuition_id IS NULL;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    problems = cur.fetchall()
                    if problems:
                        log.warning(f"Found {len(problems)} tuitions with data integrity issues.")
                    else:
                        log.info("Tuition data integrity check passed. No issues found.")
                    return [dict(p) for p in problems]
        except Exception as e:
            log.error(f"Error during tuition integrity check: {e}", exc_info=True)
            return []

    def get_all_tuitions_raw(self) -> list[dict[str, Any]]:
        """
        Fetches the raw structural data for all tuitions, including the IDs of
        related entities. This data is intended for the service layer to orchestrate.
        """
        log.info("Executing raw query to fetch all tuition structures.")
        # This query is now simpler and more robust.
        query = """
        WITH aggregated_charges AS (
            SELECT
                tuition_id,
                jsonb_agg(
                    jsonb_build_object(
                        'cost', cost,
                        'student_id', student_id,
                        'parent_id', parent_id
                    )
                ) AS charges
            FROM tuition_template_charges
            GROUP BY tuition_id
        )
        SELECT
            t.id,
            t.subject,
            t.lesson_index,
            t.min_duration_minutes,
            t.max_duration_minutes,
            t.meeting_link->>'meeting_link' AS meeting_link, -- FIXED: Extracts the string value
            t.teacher_id,
            ac.charges
        FROM tuitions t
        LEFT JOIN aggregated_charges ac ON t.id = ac.tuition_id
        WHERE t.teacher_id IS NOT NULL AND ac.charges IS NOT NULL; -- Ensure basic data exists
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    results = cur.fetchall()
                    return [dict(row) for row in results] if results else []
        except Exception as e:
            log.error(f"Database error fetching raw tuitions: {e}", exc_info=True)
            raise

    def regenerate_all_tuitions_transaction(self, tuitions: list[dict[str, Any]]) -> bool:
        """
        Atomically regenerates all tuitions and their charges in a single transaction.
        It preserves existing meeting links based on the deterministic tuition ID.
        """
        log.info(f"Starting transaction to regenerate {len(tuitions)} tuitions.")
        
        old_meeting_links = {}
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Preserve existing meeting links
                    cur.execute("SELECT id, meeting_link FROM tuitions WHERE meeting_link IS NOT NULL;")
                    for row in cur.fetchall():
                        old_meeting_links[row[0]] = row[1]
                    log.info(f"Preserved {len(old_meeting_links)} existing meeting links.")

                    # 2. Truncate tables to clear old data efficiently
                    log.warning("Truncating tuitions and tuition_template_charges tables...")
                    cur.execute("TRUNCATE TABLE tuitions, tuition_template_charges RESTART IDENTITY CASCADE;")

                    # 3. Insert new tuitions
                    for tuition in tuitions:
                        cur.execute(
                            """
                            INSERT INTO tuitions (id, teacher_id, subject, lesson_index, min_duration_minutes, max_duration_minutes)
                            VALUES (%s, %s, %s, %s, %s, %s);
                            """,
                            (
                                tuition['id'], tuition['teacher_id'], tuition['subject'],
                                tuition['lesson_index'], tuition['min_duration_minutes'],
                                tuition['max_duration_minutes']
                            )
                        )
                        # 4. Insert corresponding charges
                        for charge in tuition['charges']:
                            cur.execute(
                                """
                                INSERT INTO tuition_template_charges (tuition_id, student_id, parent_id, cost)
                                VALUES (%s, %s, %s, %s);
                                """,
                                (tuition['id'], charge['student_id'], charge['parent_id'], charge['cost'])
                            )
                    
                    # 5. Restore meeting links
                    if old_meeting_links:
                        log.info("Restoring preserved meeting links...")
                        for tuition_id, link in old_meeting_links.items():
                             cur.execute(
                                "UPDATE tuitions SET meeting_link = %s WHERE id = %s;",
                                (json.dumps(link), tuition_id) # meeting_link is jsonb
                            )
                
                conn.commit()
                log.info("Tuition regeneration transaction committed successfully.")
                return True
        except Exception as e:
            log.critical(f"Transaction failed! Rolling back tuition regeneration. Error: {e}", exc_info=True)
            if 'conn' in locals() and conn:
                conn.rollback()
            return False

    def truncate_tuitions(self) -> None:
        """Helper to clear tuition tables if no students are found."""
        log.warning("Executing truncate on tuition-related tables.")
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("TRUNCATE TABLE tuitions, tuition_template_charges RESTART IDENTITY CASCADE;")
                conn.commit()
        except Exception as e:
            log.error(f"Failed to truncate tuition tables: {e}", exc_info=True)
            conn.rollback()


    def update_tuition_field(self, tuition_id: UUID, column_name: str, new_value: Any) -> bool:
        """
        Generic method to update a single column for a given tuition.
        Future-proofing method, not used in the current regeneration flow.
        """
        # A whitelist of updatable columns to prevent SQL injection on column names
        allowed_columns = [
            "subject", "lesson_index", "min_duration_minutes",
            "max_duration_minutes", "meeting_link", "teacher_id"
        ]
        if column_name not in allowed_columns:
            log.error(f"Attempted to update a non-allowed column: {column_name}")
            return False

        log.info(f"Updating tuition '{tuition_id}' set {column_name} to {new_value}.")
        
        # Use psycopg2.sql to safely format the query with a dynamic column name
        query = sql.SQL("UPDATE tuitions SET {field} = %s WHERE id = %s;").format(
            field=sql.Identifier(column_name)
        )
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (new_value, tuition_id))
                conn.commit()
                return cur.rowcount > 0 # Return True if a row was updated
        except Exception as e:
            log.error(f"Failed to update tuition field: {e}", exc_info=True)
            conn.rollback()
            return False

    def get_latest_timetable_solution(self) -> Optional[list[dict[str, Any]]]:
        """
        Fetches the 'solution_data' JSONB from the latest successful or manual
        timetable run. The latest run is determined by the highest 'id'.
        """
        log.info("Fetching latest timetable solution from database...")
        query = """
            SELECT solution_data
            FROM timetable_runs
            WHERE status IN ('SUCCESS', 'MANUAL')
            ORDER BY id DESC
            LIMIT 1;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    result = cur.fetchone()
                    if not result or not result[0]:
                        log.warning("No successful or manual timetable run found in the database.")
                        return None
                    
                    # The result is a tuple containing one item (the jsonb list)
                    return result[0]
        except Exception as e:
            log.error(f"Database error fetching latest timetable: {e}", exc_info=True)
            raise

