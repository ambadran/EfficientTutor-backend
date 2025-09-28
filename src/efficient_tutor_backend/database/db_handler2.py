'''

'''
import os
import logging
import uuid
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
        if not DatabaseHandler._pool
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
    def get_enum_labels(self, type_name: str) -> List[str]:
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
                        log.warning(f"No labels found for ENUM type '{type_name}'.")
                        return []
                    labels = [row[0] for row in results]
                    log.info(f"Successfully fetched labels for '{type_name}': {labels}")
                    return labels
        except Exception as e:
            log.error(f"Failed to fetch ENUM labels for '{type_name}': {e}", exc_info=True)
            return []
            
    # --- User Retrieval (Read Operations) ---
    def _get_unified_user(self, key_column: str, value: Any) -> Optional[Dict[str, Any]]:
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

    def get_user_by_id(self, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Fetches a complete, unified user record by their UUID."""
        return self._get_unified_user('id', user_id)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Fetches a complete, unified user record by their email."""
        return self._get_unified_user('email', email)
        
    def get_students_by_parent_id(self, parent_id: uuid.UUID) -> List[Dict[str, Any]]:
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
    def create_parent(self, email: str, password: str, first_name: str, last_name: str, currency: str = 'EGP') -> Optional[uuid.UUID]:
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
                    
    # ... Other creation methods for Teacher, Student, etc. would follow a similar pattern ...

    # --- User Deletion ---
    def delete_user(self, user_id: uuid.UUID) -> bool:
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
