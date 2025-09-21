-- Step 1: Create a custom ENUM type for subjects.
-- This enforces data integrity at the database level.
-- The names match your Python Enum for easy mapping.
CREATE TYPE subject_enum AS ENUM (
    'Math',
    'Physics',
    'Chemistry',
    'Biology',
    'IT',
    'Geography'
);

-- Step 2: Create the corrected tuitions table.
-- Removed 'priority', added 'cost_per_hour', and uses the new subject_enum type.
CREATE TABLE tuitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Core Tuition Details
    student_ids UUID[] NOT NULL,
    subject subject_enum NOT NULL, -- Using the new ENUM type
    lesson_index INTEGER NOT NULL,
    cost_per_hour NUMERIC(10, 2) NOT NULL, -- Added this crucial column
    
    -- Parameters for the CSP (can be edited by admin)
    min_duration_minutes INTEGER NOT NULL,
    max_duration_minutes INTEGER NOT NULL,
    
    -- Tracking
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure a student group cant have the same lesson twice
    UNIQUE(student_ids, subject, lesson_index)
);

-- Optional: Create a trigger function to automatically update the 'updated_at' timestamp
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_timestamp
BEFORE UPDATE ON tuitions
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();



-- Create a new ENUM type for user roles to ensure data integrity.
-- This prevents any invalid roles from being inserted into the database.
CREATE TYPE user_role AS ENUM ('admin', 'parent', 'student');

-- Add the new 'role' column to the 'users' table.
-- We default new users to 'parent', as they will be signing up through the parent frontend.
ALTER TABLE users
ADD COLUMN role user_role NOT NULL DEFAULT 'parent';

-- Add a new column to the 'students' table to store the one-time generated password for the parent to view.
-- It is nullable because we should clear it after the students first login for security.
ALTER TABLE students
ADD COLUMN generated_password TEXT;

-- Add a new column to the 'students' table to store PDF notes.
-- A JSONB column is perfect for storing an array of objects.
ALTER TABLE students
ADD COLUMN notes JSONB;

-- Add a new column to the 'tuitions' table for the meeting link.
ALTER TABLE tuitions
ADD COLUMN meeting_link TEXT;



-- Create a table to store records of every tuition session that occurs.
-- This table is the source of truth for the "Detailed Logs" page.
CREATE TABLE tuition_logs (
    -- A unique identifier for this specific log entry.
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- An optional link to the planned tuition session.
    -- This is NULLABLE, as you requested, to allow for logging ad-hoc sessions
    -- that were not planned in the 'tuitions' table.
    -- ON DELETE SET NULL ensures that if a planned tuition is deleted, the log record remains.
    tuition_id UUID REFERENCES tuitions(id) ON DELETE SET NULL,
    
    -- The parent account this log belongs to. If the parent is deleted, their logs are also deleted.
    parent_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Details of the session, captured at the time it was logged.
    subject subject_enum NOT NULL,
    attendee_names TEXT[] NOT NULL, -- An array of student first names, as requested.
    lesson_index INTEGER, -- e.g., the 1st, 2nd lesson of the week. Can be NULL.
    cost_per_hour NUMERIC(10, 2) NOT NULL,
    
    -- The actual start and end times of the session.
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL
);

-- Create a table to store records of every payment made by a parent.
-- This table is the source of truth for calculating payment summaries.
CREATE TABLE payment_logs (
    -- A unique identifier for this specific payment.
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- The parent account that made the payment.
    parent_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- The date and time the payment was recorded. Defaults to the current time.
    payment_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- The amount paid. Using NUMERIC is essential for financial data to avoid floating-point errors.
    amount_paid NUMERIC(10, 2) NOT NULL
);

-- Optional: Add indexes to frequently queried columns to improve performance
-- as the tables grow larger.
CREATE INDEX idx_tuition_logs_parent ON tuition_logs(parent_user_id);
CREATE INDEX idx_payment_logs_parent ON payment_logs(parent_user_id);


-- This query updates the 'notes' column for a single student identified by their first_name.
-- It uses COALESCE to safely handle cases where the 'notes' column is currently NULL,
-- initializing it as an empty JSON array ('[]') before appending.
-- The '||' operator is then used to append the new note object to the JSONB array.

UPDATE students
SET
    notes = COALESCE(notes, '[]'::jsonb) || '{
        "id": "ali-89",
        "name": "Biology HW",
        "description": "Biology",
        "url": "https://web.goodnotes.com/s/Wr9h11Bw2nfrCxB4cdHzzY"

    }'::jsonb
WHERE
    first_name = 'Abdullah';

-- Create the new ENUM type for log statuses
CREATE TYPE log_status_enum AS ENUM ('ACTIVE', 'VOID');

-- == Rename 'cost_per_hour' to 'cost' for clarity ==
ALTER TABLE students RENAME COLUMN cost_per_hour TO cost;
ALTER TABLE tuitions RENAME COLUMN cost_per_hour TO cost;
ALTER TABLE tuition_logs RENAME COLUMN cost_per_hour TO cost;

-- == Add columns to 'tuition_logs' for the correction system ==
ALTER TABLE tuition_logs
ADD COLUMN status log_status_enum NOT NULL DEFAULT 'ACTIVE',
ADD COLUMN corrected_from_log_id UUID REFERENCES tuition_logs(id) DEFAULT NULL;

-- == Add a 'notes' column to 'payment_logs' for adjustments ==
ALTER TABLE payment_logs
ADD COLUMN notes TEXT;

-- Add an index to the new status column for faster queries
CREATE INDEX idx_tuition_logs_status ON tuition_logs(status);


-- Create the new ENUM type for the log creation method
CREATE TYPE tuition_log_create_type_enum AS ENUM ('SCHEDULED', 'CUSTOM');

-- Add the new column to the tuition_logs table
ALTER TABLE tuition_logs
ADD COLUMN create_type tuition_log_create_type_enum NOT NULL DEFAULT 'CUSTOM';

UPDATE tuition_logs
SET
    start_time = start_time - INTERVAL '3 hours',
    end_time = end_time - INTERVAL '3 hours';

/* VERY IMPORTANT PIECE OF CODE TO VIEW THE DATA WITH CORRECT +/- UTC hours wanted
SET timezone = 'Africa/Cairo';
