/******* unrelated teacher for testing ******/
-- First, insert the user record
INSERT INTO users (
    id, 
    email, 
    password, 
    first_name, 
    last_name, 
    role, 
    timezone
) 
VALUES (
    gen_random_uuid(), 
    'teacher@example.com', 
    'hashed_password_here', 
    'John', 
    'Doe', 
    'teacher', 
    'Africa/Cairo'
);

-- Then, insert the teacher record using the same ID
INSERT INTO teachers (id)
SELECT id FROM users WHERE email = 'teacher@example.com';

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
        "name": "Math Algebra Practice",
        "description": "Math Worksheet",
        "url": "https://share.goodnotes.com/s/Hzjfmcn689fN3UNBrGoXBI"

    }'::jsonb
WHERE
    first_name = 'Mila';

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

/* VERY IMPORTANT PIECE OF CODE TO VIEW THE DATA WITH CORRECT +/- UTC hours wanted */
SET timezone = 'Africa/Cairo';

-- Phase 1, Step 1: Add the new column to the tuition_logs table.
-- We are adding an array of UUIDs.
ALTER TABLE tuition_logs
ADD COLUMN attendee_ids UUID[];

-- Phase 1, Step 2: Migrate data from 'attendee_names' to 'attendee_ids'.
-- This is the "smart" query that matches first names to student IDs.
UPDATE tuition_logs
SET attendee_ids = subquery.ids
FROM (
    -- This subquery creates a temporary table mapping each logs ID
    -- to a correctly constructed array of student UUIDs.
    SELECT
        tl.id AS log_id,
        array_agg(s.id) AS ids
    FROM
        tuition_logs tl,
        -- 'unnest' turns the text array of names into a temporary table of rows,
        -- allowing us to join on it.
        unnest(tl.attendee_names) AS name_to_match
    -- We join the un-nested names with the students table on their first name.
    JOIN students s ON s.first_name = name_to_match
    GROUP BY
        tl.id
) AS subquery
WHERE tuition_logs.id = subquery.log_id;



/* The new design */
-- ====================================================================
-- Step 1: Create New Tables & Establish Relationships
-- ====================================================================

-- Create the `parents` table with a 1-to-1 relationship to `users`
CREATE TABLE parents (
    id UUID PRIMARY KEY NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    currency TEXT NOT NULL DEFAULT 'EGP'
);

-- Create the `teachers` table with a 1-to-1 relationship to `users`
CREATE TABLE teachers (
    id UUID PRIMARY KEY NOT NULL REFERENCES users(id) ON DELETE CASCADE
    -- Add any teacher-specific fields here in the future, e.g., qualifications, bio, etc.
);

-- Create the table for tuition template charges
CREATE TABLE tuition_template_charges (
    id UUID PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
    tuition_id UUID NOT NULL REFERENCES tuitions(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    parent_id UUID NOT NULL REFERENCES parents(id) ON DELETE CASCADE,
    cost NUMERIC(10, 2) NOT NULL
);

-- Create the table for actual tuition log charges
CREATE TABLE tuition_log_charges (
    id UUID PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
    tuition_log_id UUID NOT NULL REFERENCES tuition_logs(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    parent_id UUID NOT NULL REFERENCES parents(id) ON DELETE CASCADE,
    cost NUMERIC(10, 2) NOT NULL
);


-- ====================================================================
-- Step 2: Alter Existing Tables
-- ====================================================================

-- Add teacher_id to the `tuitions` table
ALTER TABLE tuitions
ADD COLUMN teacher_id UUID REFERENCES teachers(id) ON DELETE SET NULL;

-- Add teacher_id to the `tuition_logs` table
ALTER TABLE tuition_logs
ADD COLUMN teacher_id UUID REFERENCES teachers(id) ON DELETE SET NULL;

-- Add status and correction columns to `payment_logs`
ALTER TABLE payment_logs
ADD COLUMN status log_status_enum NOT NULL DEFAULT 'ACTIVE',
ADD COLUMN corrected_from_log_id UUID REFERENCES payment_logs(id) DEFAULT NULL;


-- ====================================================================
-- Step 3: Data Migration
-- ====================================================================

-- First, populate the new `parents` table by finding all users who are listed
-- as a parent in the `students` table.
INSERT INTO parents (id)
SELECT DISTINCT user_id FROM students
ON CONFLICT (id) DO NOTHING; -- Prevents errors if a parent ID is already there

-- Now, migrate the historical data from `tuition_logs` into `tuition_log_charges`
INSERT INTO tuition_log_charges (tuition_log_id, student_id, parent_id, cost)
SELECT
    tl.id AS tuition_log_id,
    s.id AS student_id,
    s.user_id AS parent_id,
    -- For now, we assume the cost is divided equally among all attendees.
    -- This is the best we can do with the old data structure.
    tl.cost / array_length(tl.attendee_ids, 1) AS cost
FROM
    tuition_logs tl,
    -- Unnest the array of student IDs to process them one by one
    unnest(tl.attendee_ids) AS student_id_from_array
-- Join with the students table to get the students parent_id
JOIN students s ON s.id = student_id_from_array
-- Ensure the log is active before migrating
WHERE tl.status = 'ACTIVE';

-- another update
-- Step 1: Add the new 'parent_id' column, allowing it to be temporarily null.
ALTER TABLE students
ADD COLUMN parent_id UUID;

-- Step 2: Copy all existing parent IDs from the old 'user_id' column to the new 'parent_id' column.
UPDATE students
SET parent_id = user_id;

-- Step 3: Add the new, more specific foreign key constraint to 'parent_id'.
-- This ensures it correctly links to the 'parents' table.
ALTER TABLE students
ADD CONSTRAINT students_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES parents(id) ON DELETE CASCADE;

-- Step 4: Now that the column is populated, make it non-nullable.
ALTER TABLE students
ALTER COLUMN parent_id SET NOT NULL;


-- ====================================================================
-- Step 4: Cleanup Script (DO NOT RUN UNTIL THE ENTIRE REFACTOR IS COMPLETE AND TESTED)
-- ====================================================================

/*
-- Save this script for later. It will remove the old, now-redundant columns.

-- Drop old name columns from `students`
ALTER TABLE students DROP COLUMN first_name, DROP COLUMN last_name;

ALTER TABLE tuition_logs DROP COLUMN parent_user_id;
ALTER TABLE tuition_logs DROP COLUMN attendee_names; -- If you haven't already
ALTER TABLE tuition_logs DROP COLUMN attendee_ids;
ALTER TABLE tuition_logs DROP COLUMN cost;
ALTER TABLE tuition_logs DROP COLUMN lesson_index; -- No longer needed as part of log


-- You may also want to clean up the `tuitions` table if its structure has changed.
-- For example, if cost and student info are now only in the template charges table.
ALTER TABLE tuitions DROP COLUMN student_ids;
ALTER TABLE tuitions DROP COLUMN cost;


-- To be run after the full application refactor is complete and tested.
-- Step 1: Drop the old foreign key constraint from the 'user_id' column.
-- Note: Your constraint name might be different. Use `\d students` in pgcli to confirm.
ALTER TABLE students
DROP CONSTRAINT students_user_id_fkey;

-- Step 2: Drop the old, now-redundant 'user_id' column.
ALTER TABLE students
DROP COLUMN user_id;
*/

/* VERY IMPORTANT: manually inserting the payment logs */
INSERT INTO payment_logs (parent_user_id, amount_paid, status, notes, corrected_from_log_id, teacher_id)
VALUES (
    (SELECT id FROM users WHERE email = 'aymanmagdy2007@gmail.com'),
    60,
    'ACTIVE',
    NULL,
    NULL,
    'dcef54de-bc89-4388-a7a8-dba5d8327447'
);
/********************************************************/

-- This script populates the `tuition_template_charges` table based on
-- the data in your existing `tuitions` table.
INSERT INTO tuition_template_charges (tuition_id, student_id, parent_id, cost)
SELECT
    t.id AS tuition_id,
    s.id AS student_id,
    s.parent_id AS parent_id,
    -- Assumes the template cost is divided equally among all students in the template.
    t.cost / array_length(t.student_ids, 1) AS cost
FROM
    tuitions t,
    -- Unnest the array of student IDs to process them one by one
    unnest(t.student_ids) AS student_id_from_array
-- Join with the students table to get each students parent_id
JOIN students s ON s.id = student_id_from_array;


/************************************************************************************/
/***************************** Finance Migration ************************************/
/************************************************************************************/
/** V IMP: these are the steps to migrate all old tuition_log data to the new format **/
/* Step 1: Clear any existing data in the target table. */
TRUNCATE TABLE tuition_log_charges RESTART IDENTITY CASCADE;

/* Step 2, Part A: Migrate logs that have explicit `attendee_ids`. */
INSERT INTO tuition_log_charges (tuition_log_id, student_id, parent_id, cost)
SELECT tl.id, s.id, s.parent_id, tl.cost / array_length(tl.attendee_ids, 1)
FROM tuition_logs tl, unnest(tl.attendee_ids) AS aid
JOIN students s ON s.id = aid
WHERE tl.status = 'ACTIVE' AND array_length(tl.attendee_ids, 1) > 0;

/* Step 2, Part B: Migrate logs that reference a `tuition_id` template. */
INSERT INTO tuition_log_charges (tuition_log_id, student_id, parent_id, cost)
SELECT tl.id, s.id, s.parent_id, t.cost / array_length(t.student_ids, 1)
FROM tuition_logs tl
JOIN tuitions t ON tl.tuition_id = t.id
JOIN unnest(t.student_ids) AS aid ON true
JOIN students s ON s.id = aid
WHERE tl.status = 'ACTIVE' AND (tl.attendee_ids IS NULL OR array_length(tl.attendee_ids, 1) IS NULL);

/* Step 2, Part C: Migrate logs that only have `attendee_names`. */
INSERT INTO tuition_log_charges (tuition_log_id, student_id, parent_id, cost)
SELECT tl.id, s.id, s.parent_id, tl.cost / array_length(tl.attendee_names, 1)
FROM tuition_logs tl, unnest(tl.attendee_names) AS aname
JOIN students s ON s.first_name = aname
WHERE tl.status = 'ACTIVE' AND (tl.attendee_ids IS NULL OR array_length(tl.attendee_ids, 1) IS NULL) AND tl.tuition_id IS NULL;

/* unrelated important step: update the teacher_id column for the newest ones */
UPDATE tuition_logs SET teacher_id = 'dcef54de-bc89-4388-a7a8-dba5d8327447';

/* another important step is to update the tuition_template_charges too */
/* part 1: delete any data in the current tuition_template_charges */
TRUNCATE TABLE tuition_template_charges RESTART IDENTITY CASCADE;

/* part 2: load */
INSERT INTO tuition_template_charges (tuition_id, student_id, parent_id, cost)
SELECT
    t.id AS tuition_id,
    s.id AS student_id,
    s.parent_id AS parent_id,
    t.cost / array_length(t.student_ids, 1) AS cost
FROM
    tuitions t,
    unnest(t.student_ids) AS student_id_from_array
JOIN students s ON s.id = student_id_from_array;

/* Step 3: make sure the number of logs in the tuition_logs are all mapped in the tuition_charges */
-- select COUNT(*) from tuition_logs;
-- select COUNT(DISTINCT tuition_log_id) FROM tuition_log_charges;

/* in case, there is a mismatch, I can identify them exactly using this */
-- SELECT tl.*
-- FROM tuition_logs tl
-- LEFT JOIN tuition_log_charges tlc ON tl.id = tlc.tuition_log_id
-- WHERE tlc.tuition_log_id IS NULL; 

/* Step 4: Delete the old duplicated logs of abdullah & jacob */
/* part a: identify them from frontend, the dates are (sep 16 and sep 11) */
/* part b: get the id */
-- SELECT * FROM tuition_logs WHERE start_time::date = '2025-09-11';
-- SELECT * FROM tuition_logs WHERE start_time::date = '2025-09-16';
/* part c: delete them */
DELETE from tuition_logs WHERE id = 'c0248183-86b6-4e74-a8c7-4ce9bf48ba5a';
DELETE from tuition_logs WHERE id = '70eebd82-9743-4b35-9262-b5d2782f0ddc';

/* Then finally check again using step 3 */

-- ====================================================================
-- Step 4: Cleanup Script (DO NOT RUN UNTIL THE ENTIRE REFACTOR IS COMPLETE AND TESTED)
-- ====================================================================

-- Save this script for later. It will remove the old, now-redundant columns.

-- Drop old name columns from `students`
ALTER TABLE students DROP COLUMN first_name, DROP COLUMN last_name;

ALTER TABLE tuition_logs DROP COLUMN parent_user_id;
ALTER TABLE tuition_logs DROP COLUMN attendee_names;
ALTER TABLE tuition_logs DROP COLUMN attendee_ids;
ALTER TABLE tuition_logs DROP COLUMN cost;

-- You may also want to clean up the `tuitions` table if its structure has changed.
-- For example, if cost and student info are now only in the template charges table.
ALTER TABLE tuitions DROP COLUMN student_ids;
ALTER TABLE tuitions DROP COLUMN cost;


-- To be run after the full application refactor is complete and tested.
-- Step 1: Drop the old foreign key constraint from the 'user_id' column.
-- Note: Your constraint name might be different. Use `\d students` in pgcli to confirm.
ALTER TABLE students
DROP CONSTRAINT students_user_id_fkey;

-- Step 2: Drop the old, now-redundant user_id column.
ALTER TABLE students
DROP COLUMN user_id;

-- rename the parent_user_id to parent_id
ALTER TABLE payment_logs
RENAME COLUMN parent_user_id TO parent_id;

ALTER TABLE users
ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- fix the tuition log of abdullah & yassin on oct 6th
-- fix the tuition log for abdullah, jacob, yassin on oct 28th
/* ********************************************************************* */
/* ********************************************************************* */
/* ********************************************************************* */



/* ********************************************************************* */
/* ********************************************************************* */
/* **************** Creating the new 'notes' Table ********************* */
-- Step 1: Create the new 'NoteTypeEnum'
CREATE TYPE NoteTypeEnum AS ENUM (
    'STUDY_NOTES',
    'HOMEWORK',
    'PAST_PAPERS'
);

-- Step 2: Create the 'notes' table
CREATE TABLE notes (
    -- The Primary Key for the note
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- The Foreign Key linking to the student (the "one-to-many" link)
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    
    -- Columns you requested
    name TEXT NOT NULL,
    subject subject_enum NOT NULL,
    description TEXT,
    note_type NoteTypeEnum NOT NULL,
    
    -- Suggested new columns
    url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Step 3: Add an index for the foreign key to speed up queries
CREATE INDEX idx_notes_student_id ON notes(student_id);
ALTER TABLE notes
ADD COLUMN teacher_id UUID REFERENCES teachers(id) ON DELETE SET NULL;
/* ************************* Migrating Data **************************** */
INSERT INTO notes (
    student_id,
    name,
    description,
    url,
    subject,
    note_type
)
SELECT
    -- 1. Get the students ID from the `students` table
    s.id AS student_id,

    -- 2. Extract the text fields directly from the JSON
    note_element->>'name' AS name,
    note_element->>'description' AS description,
    note_element->>'url' AS url,

    -- 3. Infer the `subject` from the name or description
    (CASE
        WHEN note_element->>'name' ILIKE '%math%' OR note_element->>'description' ILIKE '%math%' OR note_element->>'name' ILIKE '%numbers%' THEN 'Math'
        WHEN note_element->>'name' ILIKE '%physics%' OR note_element->>'description' ILIKE '%physics%' OR note_element->>'name' ILIKE '%hooke%' THEN 'Physics'
        WHEN note_element->>'name' ILIKE '%chemistry%' OR note_element->>'description' ILIKE '%chemistry%' THEN 'Chemistry'
        WHEN note_element->>'name' ILIKE '%biology%' OR note_element->>'description' ILIKE '%biology%' THEN 'Biology'
        WHEN note_element->>'name' ILIKE '%it%' OR note_element->>'description' ILIKE '%it%' THEN 'IT'
        WHEN note_element->>'name' ILIKE '%geography%' OR note_element->>'description' ILIKE '%geography%' THEN 'Geography'
        ELSE 'Math' -- Default fallback, see warning below
    END)::subject_enum AS subject,

    -- 4. Infer the `note_type` from the name or description
    (CASE
        WHEN note_element->>'name' ILIKE '%past paper%' OR note_element->>'description' ILIKE '%past paper%' THEN 'PAST_PAPERS'
        WHEN note_element->>'name' ILIKE '%homework%' OR note_element->>'description' ILIKE '%homework%' OR note_element->>'name' ILIKE '%hw%' THEN 'HOMEWORK'
        ELSE 'STUDY_NOTES' -- Default fallback
    END)::NoteTypeEnum AS note_type
FROM
    students s,
    -- This function expands the JSON array into individual rows
    jsonb_array_elements(s.notes) AS note_element
WHERE
    -- Only run on students who have notes to migrate
    s.notes IS NOT NULL AND jsonb_array_length(s.notes) > 0;
UPDATE notes
SET teacher_id = 'dcef54de-bc89-4388-a7a8-dba5d8327447';
ALTER TABLE notes
ALTER COLUMN teacher_id SET NOT NULL;
/* ******************* Delete student notes column ********************* */
ALTER TABLE students
DROP COLUMN notes;
/* ********************************************************************* */
/* ********************************************************************* */
/* ********************************************************************* */


/* ********************************************************************* */
/* ********************************************************************* */
/* ************ Creating the new 'meeting_link' Table ****************** */
-- Step 1: Create the new 'MeetingLinkType' enum
CREATE TYPE MeetingLinkType AS ENUM (
    'GOOGLE_MEET',
    'ZOOM'
);

-- Step 2: Create the 'meeting_links' table
CREATE TABLE meeting_links (
    -- This is the 1-to-1 relationship enforcement.
    -- It is both the Primary Key and the Foreign Key.
    tuition_id UUID PRIMARY KEY NOT NULL REFERENCES tuitions(id) ON DELETE CASCADE,
    
    -- The type of meeting (Zoom, Google Meet, etc.)
    meeting_link_type MeetingLinkType NOT NULL,

    -- The full URL for joining the meeting (e.g., https://zoom.us/j/...)
    meeting_link TEXT NOT NULL,
    
    -- The numeric/string ID of the meeting (optional, but good for API use)
    meeting_id TEXT,
    
    -- The meeting password (optional)
    meeting_password TEXT
);
/* ************************* Migrating Data **************************** */
INSERT INTO meeting_links (
    tuition_id,
    meeting_link_type,
    meeting_link,
    meeting_id
)
SELECT
    id AS tuition_id,

    -- Infer the meeting type based on the URL
    (CASE
        WHEN meeting_link->>'meeting_link' ILIKE '%zoom.us%' THEN 'ZOOM'
        WHEN meeting_link->>'meeting_link' ILIKE '%meet.google.com%' THEN 'GOOGLE_MEET'
        ELSE 'ZOOM' -- Fallback based on your example
    END)::MeetingLinkType AS meeting_link_type,
    
    -- Extract the data from the JSON fields
    meeting_link->>'meeting_link' AS meeting_link,
    meeting_link->>'meeting_id' AS meeting_id
FROM
    tuitions
WHERE
    -- Only migrate rows that actually have meeting link data
    meeting_link IS NOT NULL
    AND meeting_link->>'meeting_link' IS NOT NULL;
/* ******************* Delete student notes column ********************* */
ALTER TABLE tuitions
DROP COLUMN meeting_link;
/* ********************************************************************* */
/* ********************************************************************* */
/* ********************************************************************* */

