'''

'''
import os
import logging
from uuid import UUID
from contextlib import contextmanager
from typing import Any, Optional
from datetime import datetime
from decimal import Decimal

import psycopg2
import psycopg2.extras
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

from ..common.logger import log
from ..common.exceptions import UserNotFoundError, UnauthorizedRoleError

# Enabling UUID in psycopg2 queries
psycopg2.extras.register_uuid()

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
            raise
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
            raise
        return results

    #NEW
    def get_parent_ids_for_teacher(self, teacher_id: UUID) -> list[UUID]:
        """
        Finds all unique parent IDs that are linked to a teacher through
        historical tuition logs.
        """
        log.info(f"Fetching unique parent IDs for teacher {teacher_id}.")
        query = """
            SELECT DISTINCT tlc.parent_id
            FROM tuition_logs tl
            JOIN tuition_log_charges tlc ON tl.id = tlc.tuition_log_id
            WHERE tl.teacher_id = %s;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (teacher_id,))
                    return [row[0] for row in cur.fetchall()]
        except Exception as e:
            log.error(f"Database error fetching parent IDs for teacher {teacher_id}: {e}", exc_info=True)
            raise
    #NEW
    def get_users_by_ids(self, user_ids: list[UUID]) -> list[dict]:
        """
        Fetches and hydrates a list of users from a list of user IDs.
        This is an efficient bulk version of get_user_by_id.
        """
        if not user_ids:
            return []
        log.info(f"Fetching hydrated user data for {len(user_ids)} users.")
        # This is the same unified query from _get_unified_user, but adapted for a list of IDs
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
            WHERE u.id = ANY(%s::uuid[]);
        """
        try:
            str_user_ids = [str(uid) for uid in user_ids]
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (str_user_ids,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            log.error(f"Database error in get_users_by_ids: {e}", exc_info=True)
            raise

    def get_students_for_teacher(self, teacher_id: UUID) -> list[dict]:
        """
        Finds all unique students linked to a teacher via tuition_logs
        and returns their fully hydrated user data.
        """
        log.info(f"Fetching all students for teacher {teacher_id}.")
        # First, find all unique student IDs associated with the teacher
        student_ids_query = """
            SELECT DISTINCT tlc.student_id
            FROM tuition_logs tl
            JOIN tuition_log_charges tlc ON tl.id = tlc.tuition_log_id
            WHERE tl.teacher_id = %s;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(student_ids_query, (teacher_id,))
                    student_ids = [row[0] for row in cur.fetchall()]
            
            if not student_ids:
                return []
            
            # Now, use our existing bulk fetcher to get their full details
            return self.get_users_by_ids(student_ids)

        except Exception as e:
            log.error(f"Database error fetching students for teacher {teacher_id}: {e}", exc_info=True)
            raise

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
            raise
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

    # -------------------------- Tuitions ----------------------------------

    # -- read transactions ---
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

    def _get_all_tuitions_raw_base(self, where_clause: str = "", params: Optional[dict] = None) -> list[dict]:
        """
        PRIVATE HELPER: The single source of truth for fetching raw tuition data.
        It accepts an optional WHERE clause to allow for flexible filtering.
        """
        # This is the true "base" query, with no WHERE clause at the end.
        base_query = """
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
                t.meeting_link->>'meeting_link' AS meeting_link,
                t.teacher_id,
                ac.charges
            FROM tuitions t
            LEFT JOIN aggregated_charges ac ON t.id = ac.tuition_id
        """
        
        # Safely append the WHERE clause to the base query
        final_query = f"{base_query} {where_clause}"

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(final_query, params)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            log.error(f"DB error fetching raw tuitions with clause '{where_clause}': {e}", exc_info=True)
            raise

    def get_tuition_raw_by_id(self, tuition_id: UUID) -> Optional[dict]:
        """Fetches a single raw tuition by its ID."""
        log.info(f"Fetching raw tuition for id {tuition_id}.")
        where = "WHERE t.id = %(tuition_id)s"
        results = self._get_all_tuitions_raw_base(where_clause=where, params={'tuition_id': tuition_id})
        return results[0] if results else None

    def get_all_tuitions_raw(self) -> list[dict[str, Any]]:
        """
        NEW PUBLIC METHOD: Fetches all valid tuitions (replaces your old implementation).
        """
        log.info("Executing raw query to fetch all tuition structures.")
        where = "WHERE t.teacher_id IS NOT NULL AND ac.charges IS NOT NULL"
        return self._get_all_tuitions_raw_base(where_clause=where)

    def get_all_tuitions_raw_for_teacher(self, teacher_id: UUID) -> list[dict]:
        """Fetches all raw tuition data for a specific teacher."""
        log.info(f"Fetching all raw tuitions for teacher {teacher_id}.")
        where = "WHERE t.teacher_id = %(viewer_id)s AND ac.charges IS NOT NULL"
        return self._get_all_tuitions_raw_base(where_clause=where, params={'viewer_id': teacher_id})

    def get_all_tuitions_raw_for_parent(self, parent_id: UUID) -> list[dict]:
        """Fetches all raw tuition data relevant to a specific parent."""
        log.info(f"Fetching all raw tuitions for parent {parent_id}.")
        where = """
            WHERE t.id IN (
                SELECT DISTINCT tuition_id FROM tuition_template_charges WHERE parent_id = %(viewer_id)s
            )
            AND t.teacher_id IS NOT NULL AND ac.charges IS NOT NULL
        """
        return self._get_all_tuitions_raw_base(where_clause=where, params={'viewer_id': parent_id})

    def get_all_tuitions_raw_for_student(self, student_id: UUID) -> list[dict]:
        """Fetches all raw tuition data relevant to a specific student."""
        log.info(f"Fetching all raw tuitions for student {student_id}.")
        where = """
            WHERE t.id IN (
                SELECT DISTINCT tuition_id FROM tuition_template_charges WHERE student_id = %(viewer_id)s
            )
            AND t.teacher_id IS NOT NULL AND ac.charges IS NOT NULL
        """
        return self._get_all_tuitions_raw_base(where_clause=where, params={'viewer_id': student_id})

    # ---- Write transactions ----------

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

    # -- Timetable stuff -----

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

    # --- Finance Log Creation ---

    def create_tuition_log_and_charges(
        self,
        teacher_id: UUID,
        subject: str,
        start_time: datetime,
        end_time: datetime,
        create_type: str,
        charges: list[dict[str, Any]],
        tuition_id: Optional[UUID] = None,
        lesson_index: Optional[int] = None,
        corrected_from_log_id: Optional[UUID] = None
    ) -> Optional[UUID]:
        """
        Atomically creates a new tuition log and all its associated student charges
        in a single transaction.
        
        Returns the new tuition_log ID on success, None on failure.
        """
        log.info(f"Creating new {create_type} tuition log with {len(charges)} charges.")
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Insert the main tuition_log record
                    cur.execute(
                        """
                        INSERT INTO tuition_logs (
                            teacher_id, subject, start_time, end_time, create_type,
                            tuition_id, lesson_index, corrected_from_log_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
                        """,
                        (
                            teacher_id, subject, start_time, end_time, create_type,
                            tuition_id, lesson_index, corrected_from_log_id
                        )
                    )
                    new_log_id = cur.fetchone()[0]

                    # 2. Insert each associated student charge
                    for charge in charges:
                        cur.execute(
                            """
                            INSERT INTO tuition_log_charges (tuition_log_id, student_id, parent_id, cost)
                            VALUES (%s, %s, %s, %s);
                            """,
                            (new_log_id, charge['student_id'], charge['parent_id'], charge['cost'])
                        )
                
                conn.commit()
                log.info(f"Successfully created tuition log {new_log_id}.")
                return new_log_id
        except Exception as e:
            log.error(f"Transaction failed! Rolling back tuition log creation. Error: {e}", exc_info=True)
            if 'conn' in locals() and conn:
                conn.rollback()
            raise

    def create_payment_log(
        self,
        parent_user_id: UUID,
        teacher_id: UUID,
        amount_paid: Decimal,
        notes: Optional[str] = None,
        corrected_from_log_id: Optional[UUID] = None
    ) -> Optional[UUID]:
        """Creates a new payment log entry and returns its ID."""
        log.info(f"Creating new payment log for parent {parent_user_id}.")
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO payment_logs (parent_user_id, teacher_id, amount_paid, notes, corrected_from_log_id)
                        VALUES (%s, %s, %s, %s, %s) RETURNING id;
                        """,
                        (parent_user_id, teacher_id, amount_paid, notes, corrected_from_log_id)
                    )
                    new_log_id = cur.fetchone()[0]
                conn.commit()
                log.info(f"Successfully created payment log {new_log_id}.")
                return new_log_id
        except Exception as e:
            log.error(f"Failed to create payment log: {e}", exc_info=True)
            conn.rollback()
            raise

    # --- Finance Log Updates (Voiding) ---

    def set_log_status(self, table_name: str, log_id: UUID, status: str) -> bool:
        """Generic helper to set the status of a log in a given table."""
        log.info(f"Setting status for log {log_id} in table '{table_name}' to '{status}'.")
        # Use psycopg2.sql for safe table name injection
        query = sql.SQL("UPDATE {table} SET status = %s WHERE id = %s;").format(
            table=sql.Identifier(table_name)
        )
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (status, log_id))
                conn.commit()
                return cur.rowcount > 0 # True if a row was updated
        except Exception as e:
            log.error(f"Failed to set log status for {log_id}: {e}", exc_info=True)
            conn.rollback()
            return False

    # --- Finance Log Retrieval ---

    def get_earliest_log_start_time(self) -> Optional[datetime]:
        """Finds the earliest start_time across all tuition logs for week number calculation."""
        log.info("Fetching the earliest tuition log start time.")
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT MIN(start_time) FROM tuition_logs WHERE status = 'ACTIVE';")
                    result = cur.fetchone()
                    return result[0] if result else None
        except Exception as e:
            log.error(f"Failed to fetch earliest log start time: {e}", exc_info=True)
            return None
    
    def _get_hydrated_logs(self, where_clause: sql.SQL, params: tuple) -> list[dict]:
        """
        Private helper to fetch and construct rich tuition log data using a dynamic WHERE clause.
        This efficiently gathers all related data in a single query.
        """
        #TODO: MUST LOG ERROR OR CRITICAL IF BROKEN DATA FOUND!!!!
        # This query joins all necessary tables and uses JSON aggregation
        # to build a nested structure that matches our Pydantic models.
        query = sql.SQL("""
            WITH aggregated_charges AS (
                SELECT
                    tlc.tuition_log_id,
                    jsonb_agg(
                        jsonb_build_object(
                            'cost', tlc.cost,
                            'student', to_jsonb(s_user.*) || to_jsonb(s.*),
                            'parent', to_jsonb(p_user.*) || to_jsonb(p.*)
                        )
                    ) AS charges
                FROM tuition_log_charges tlc
                JOIN users s_user ON tlc.student_id = s_user.id
                JOIN students s ON tlc.student_id = s.id
                JOIN users p_user ON tlc.parent_id = p_user.id
                JOIN parents p ON tlc.parent_id = p.id
                GROUP BY tlc.tuition_log_id
            )
            SELECT
                tl.id, tl.subject, tl.lesson_index, tl.start_time,
                tl.end_time, tl.status, tl.create_type, tl.corrected_from_log_id,
                to_jsonb(t_user.*) AS teacher,
                ac.charges
            FROM tuition_logs tl
            JOIN aggregated_charges ac ON tl.id = ac.tuition_log_id
            JOIN users t_user ON tl.teacher_id = t_user.id
            {where_clause};
        """).format(where_clause=where_clause)

        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, params)
                    results = cur.fetchall()
                    if not results:
                        log.warning(f"No hydrated logs found for the given query.")
                    return [dict(row) for row in results]
        except Exception as e:
            log.error(f"Database error in _get_hydrated_logs: {e}", exc_info=True)
            raise # Re-raise the exception for the service layer to handle

    def get_tuition_log_by_id(self, log_id: UUID) -> Optional[dict]:
        """Fetches a single hydrated tuition log by its ID."""
        log.info(f"Fetching tuition log for id {log_id}.")
        where = sql.SQL("WHERE tl.id = %s")
        results = self._get_hydrated_logs(where, (log_id,))
        return results[0] if results else None

    def get_tuition_logs_by_teacher(self, teacher_id: UUID) -> list[dict]:
        """Fetches all hydrated tuition logs for a specific teacher."""
        log.info(f"Fetching tuition logs for teacher {teacher_id}.")
        where = sql.SQL("WHERE tl.teacher_id = %s ORDER BY tl.start_time ASC")
        return self._get_hydrated_logs(where, (teacher_id,))
    
    def get_tuition_logs_by_parent(self, parent_id: UUID) -> list[dict]:
        """Fetches all hydrated tuition logs that a parent's child attended."""
        log.info(f"Fetching tuition logs for parent {parent_id}.")
        try:
            log_ids_query = "SELECT DISTINCT tuition_log_id FROM tuition_log_charges WHERE parent_id = %s"
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(log_ids_query, (parent_id,))
                    log_ids = [row[0] for row in cur.fetchall()]
                    if not log_ids:
                        log.warning(f"No tuition logs found for parent {parent_id}.")
                        return []
            
            # Now fetch the full logs for these specific IDs
            where = sql.SQL("WHERE tl.id = ANY(%s) ORDER BY tl.start_time ASC")
            return self._get_hydrated_logs(where, (log_ids,))
        except Exception as e:
            log.error(f"Database error fetching logs by parent {parent_id}: {e}", exc_info=True)
            raise
            
    def get_payment_logs_by_teacher(self, teacher_id: UUID) -> list[dict]:
        """Fetches all hydrated payment logs for a specific teacher."""
        log.info(f"Fetching payment logs for teacher {teacher_id}.")
        # Similar hydration query for payment logs
        query = """
            SELECT
                pl.*,
                to_jsonb(p_user.*) || to_jsonb(p.*) as parent,
                to_jsonb(t_user.*) as teacher
            FROM payment_logs pl
            JOIN users p_user ON pl.parent_user_id = p_user.id
            JOIN parents p ON pl.parent_user_id = p.id
            JOIN users t_user ON pl.teacher_id = t_user.id
            WHERE pl.teacher_id = %s
            ORDER BY pl.payment_date DESC;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (teacher_id,))
                    results = cur.fetchall()
                    if not results:
                        log.warning(f"No payment logs found for teacher {teacher_id}.")
                    return [dict(row) for row in results]
        except Exception as e:
            log.error(f"Database error fetching payment logs by teacher {teacher_id}: {e}", exc_info=True)
            raise

    def get_payment_logs_by_parent(self, parent_id: UUID) -> list[dict]:
        """Fetches all hydrated payment logs for a specific parent."""
        log.info(f"Fetching payment logs for parent {parent_id}.")
        query = """
            SELECT
                pl.*,
                to_jsonb(p_user.*) || to_jsonb(p.*) as parent,
                to_jsonb(t_user.*) as teacher
            FROM payment_logs pl
            JOIN users p_user ON pl.parent_user_id = p_user.id
            JOIN parents p ON pl.parent_user_id = p.id
            JOIN users t_user ON pl.teacher_id = t_user.id
            WHERE pl.parent_user_id = %s
            ORDER BY pl.payment_date DESC;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (parent_id,))
                    results = cur.fetchall()
                    if not results:
                        log.warning(f"No payment logs found for parent {parent_id}.")
                    return [dict(row) for row in results]
        except Exception as e:
            log.error(f"Database error fetching payment logs by parent {parent_id}: {e}", exc_info=True)
            raise

    def identify_user_role(self, user_id: UUID) -> str:
        """
        Fetches the role for a specific user ID.
        
        Raises:
            UserNotFoundError: If no user is found with the given ID.
        """
        log.info(f"Identifying role for user_id: {user_id}")
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT role FROM users WHERE id = %s;", (user_id,))
                    result = cur.fetchone()
                    if result:
                        return result[0]
                    # CHANGED: Raise an exception instead of returning None
                    raise UserNotFoundError(f"User with ID {user_id} not found.")
        except Exception as e:
            # Re-raise our specific error, but log the original DB error
            if not isinstance(e, UserNotFoundError):
                log.error(f"Database error identifying role for user {user_id}: {e}", exc_info=True)
            raise


    # --- Financial Summary Aggregations ---

    def get_parent_financial_aggregates(self, parent_id: UUID) -> dict[str, Decimal]:
        """
        Calculates the total charges and total payments for a single parent.

        Returns a dictionary with 'total_charges' and 'total_payments'.
        """
        log.info(f"Fetching financial aggregates for parent {parent_id}.")
        query = """
            SELECT
                (
                    SELECT COALESCE(SUM(tlc.cost), 0)
                    FROM tuition_log_charges tlc
                    JOIN tuition_logs tl ON tlc.tuition_log_id = tl.id
                    WHERE tlc.parent_id = %(user_id)s AND tl.status = 'ACTIVE'
                ) AS total_charges,
                (
                    SELECT COALESCE(SUM(pl.amount_paid), 0)
                    FROM payment_logs pl
                    WHERE pl.parent_user_id = %(user_id)s AND pl.status = 'ACTIVE'
                ) AS total_payments;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, {'user_id': parent_id})
                    result = cur.fetchone()
                    return dict(result) if result else {'total_charges': 0, 'total_payments': 0}
        except Exception as e:
            log.error(f"Database error fetching parent financial aggregates for {parent_id}: {e}", exc_info=True)
            raise

    def get_teacher_parent_balances(self, teacher_id: UUID) -> list[dict[str, Any]]:
        """
        For a given teacher, calculates the financial balance (payments - charges)
        for every parent they have interacted with. This is a building block
        for calculating the teacher's total amount owed.
        """
        log.info(f"Fetching per-parent balances for teacher {teacher_id}.")
        query = """
            WITH parent_charges AS (
                SELECT tlc.parent_id, SUM(tlc.cost) as total_charges
                FROM tuition_log_charges tlc
                JOIN tuition_logs tl ON tlc.tuition_log_id = tl.id
                WHERE tl.teacher_id = %(teacher_id)s AND tl.status = 'ACTIVE'
                GROUP BY tlc.parent_id
            ),
            parent_payments AS (
                SELECT pl.parent_user_id as parent_id, SUM(pl.amount_paid) as total_payments
                FROM payment_logs pl
                WHERE pl.teacher_id = %(teacher_id)s AND pl.status = 'ACTIVE'
                GROUP BY pl.parent_user_id
            )
            SELECT
                pc.parent_id,
                (COALESCE(pp.total_payments, 0) - pc.total_charges) as balance
            FROM parent_charges pc
            LEFT JOIN parent_payments pp ON pc.parent_id = pp.parent_id;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, {'teacher_id': teacher_id})
                    results = cur.fetchall()
                    if not results:
                        log.warning(f"No parent balances found for teacher {teacher_id}.")
                    return [dict(row) for row in results]
        except Exception as e:
            log.error(f"Database error fetching teacher parent balances for {teacher_id}: {e}", exc_info=True)
            raise

    def count_teacher_logs_this_month(self, teacher_id: UUID) -> int:
        """
        Counts the number of ACTIVE tuition logs for a teacher in the current calendar month.
        """
        log.info(f"Counting this month's logs for teacher {teacher_id}.")
        # date_trunc('month', NOW()) gets the first moment of the current month.
        query = """
            SELECT COUNT(*)
            FROM tuition_logs
            WHERE teacher_id = %s
              AND status = 'ACTIVE'
              AND start_time >= date_trunc('month', NOW())
              AND start_time < date_trunc('month', NOW()) + interval '1 month';
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (teacher_id,))
                    result = cur.fetchone()
                    return result[0] if result else 0
        except Exception as e:
            log.error(f"Database error counting teacher's monthly logs for {teacher_id}: {e}", exc_info=True)
            raise

    def count_parent_active_logs(self, parent_id: UUID) -> int:
        #TODO: THIS METHOD IS OBSOLETE AND NOT NEEDED, SHOULD BE DELTEED AND REPLACED WHEN IMPLEMENTED PROPER unpaid_count
        """Counts the total number of ACTIVE tuition logs a parent is associated with."""
        log.info(f"Counting active logs for parent {parent_id}.")
        query = """
            SELECT COUNT(DISTINCT tl.id)
            FROM tuition_logs tl
            JOIN tuition_log_charges tlc ON tl.id = tlc.tuition_log_id
            WHERE tlc.parent_id = %s AND tl.status = 'ACTIVE';
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (parent_id,))
                    result = cur.fetchone()
                    return result[0] if result else 0
        except Exception as e:
            log.error(f"Database error counting parent's active logs for {parent_id}: {e}", exc_info=True)
            raise

    def get_total_payments_for_parents(self, parent_ids: list[UUID]) -> dict[UUID, Decimal]:
        """
        Fetches the total sum of ACTIVE payments for a given list of parent IDs.
        """
        if not parent_ids:
            return {}
        log.info(f"Fetching total payments for {len(parent_ids)} parents.")
        # FIXED: Add ::uuid[] to explicitly cast the array parameter to a UUID array.
        query = """
            SELECT parent_user_id, SUM(amount_paid)
            FROM payment_logs
            WHERE parent_user_id = ANY(%s::uuid[]) AND status = 'ACTIVE'
            GROUP BY parent_user_id;
        """
        try:
            # Convert UUID objects to strings for the driver, the DB will cast them back.
            str_parent_ids = [str(pid) for pid in parent_ids]
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (str_parent_ids,))
                    results = {pid: Decimal(0) for pid in parent_ids}
                    for row in cur.fetchall():
                        results[row[0]] = row[1]
                    return results
        except Exception as e:
            log.error(f"Database error fetching total payments for parents: {e}", exc_info=True)
            raise

