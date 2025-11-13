-- Phase 1: Create the new relational tables for student subjects.

-- Step 1: Create the 'student_subjects' table.
-- This table holds the specific subjects a student is enrolled in.
CREATE TABLE student_subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject subject_enum NOT NULL,
    lessons_per_week INTEGER NOT NULL DEFAULT 1,
    
    -- A student can only have one entry for a specific subject.
    UNIQUE(student_id, subject)
);

-- Add an index for faster lookups by student_id.
CREATE INDEX idx_student_subjects_student_id ON student_subjects(student_id);


-- Step 2: Create the 'student_subject_sharings' linking table.
-- This table models the many-to-many relationship for sharing.
CREATE TABLE student_subject_sharings (
    -- Foreign key to the specific student subject being shared.
    student_subject_id UUID NOT NULL REFERENCES student_subjects(id) ON DELETE CASCADE,
    
    -- Foreign key to the student with whom the subject is being shared.
    shared_with_student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    
    -- The primary key ensures that a subject cant be shared with the same student more than once.
    PRIMARY KEY (student_subject_id, shared_with_student_id)
);

-- Add indexes for faster lookups in both directions.
CREATE INDEX idx_student_subject_sharings_subject_id ON student_subject_sharings(student_subject_id);
CREATE INDEX idx_student_subject_sharings_student_id ON student_subject_sharings(shared_with_student_id);


-- Phase 2: Migrate data from the old 'student_data' JSONB column.
-- This script is designed to be idempotent (safe to run multiple times).

-- Use a temporary table to store the mapping between the old structure and the new student_subject IDs.
-- This is crucial for migrating the 'sharedWith' relationships correctly.
CREATE TEMPORARY TABLE subject_migration_map (
    student_id UUID,
    subject_name TEXT,
    new_subject_id UUID
);

-- Part A: Migrate the core subject data.
-- This uses jsonb_array_elements to unpack the 'subjects' array.
INSERT INTO student_subjects (student_id, subject, lessons_per_week)
SELECT
    s.id as student_id,
    (json_subject.subject_data->>'name')::subject_enum as subject,
    (json_subject.subject_data->>'lessonsPerWeek')::INTEGER as lessons_per_week
FROM
    students s,
    jsonb_array_elements(s.student_data->'subjects') as json_subject(subject_data)
WHERE s.student_data ? 'subjects'
ON CONFLICT (student_id, subject) DO NOTHING;

-- Part B: Populate the temporary map with the newly created subject IDs.
INSERT INTO subject_migration_map (student_id, subject_name, new_subject_id)
SELECT
    ss.student_id,
    ss.subject::TEXT,
    ss.id
FROM
    student_subjects ss;

-- Part C: Migrate the 'sharedWith' relationships using the map.
WITH UnnestedShares AS (
    SELECT
        s.id as student_id,
        json_subject.subject_data->>'name' as subject_name,
        shared_with_uuid_element.value as shared_with_student_id_text
    FROM
        students s,
        jsonb_array_elements(s.student_data->'subjects') as json_subject(subject_data),
        jsonb_array_elements_text(json_subject.subject_data->'sharedWith') as shared_with_uuid_element
    WHERE
        s.student_data ? 'subjects' AND
        jsonb_typeof(json_subject.subject_data->'sharedWith') = 'array' AND
        jsonb_array_length(json_subject.subject_data->'sharedWith') > 0
)
INSERT INTO student_subject_sharings (student_subject_id, shared_with_student_id)
SELECT
    map.new_subject_id,
    (us.shared_with_student_id_text)::UUID
FROM
    UnnestedShares us
JOIN
    subject_migration_map map ON map.student_id = us.student_id AND map.subject_name = us.subject_name
ON CONFLICT (student_subject_id, shared_with_student_id) DO NOTHING;

-- Clean up the temporary table.
DROP TABLE subject_migration_map;


-- Phase 3: Clean up the JSONB column.
-- This removes the 'subjects' key from the 'student_data' JSONB column,
-- leaving the 'availability' data for the next phase.
-- Run this only after verifying the migration was successful.
UPDATE students
SET student_data = student_data - 'subjects'
WHERE student_data ? 'subjects';
