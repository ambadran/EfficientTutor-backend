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

/* TODO: fix the date on the Abdullah Chemistry tuition on Nov25 3:06PM to 4:32PM, i forgot to put the right date. I think it was put on Nov11 by accident */
