-- Phase 1: Create the new relational table for student availability.

-- Step 1: Create the 'availability_type_enum' ENUM.
-- This captures the known types from your Pydantic models and data.
-- It can be easily extended in the future if new types are needed.
CREATE TYPE availability_type_enum AS ENUM (
    'sleep',
    'school',
    'sports',
    'others'
);

-- Step 2: Create the 'student_availability_intervals' table.
CREATE TABLE student_availability_intervals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    
    -- Using integer for day of week (ISO 8601 standard: 1=Monday, 7=Sunday)
    day_of_week INTEGER NOT NULL CHECK (day_of_week >= 1 AND day_of_week <= 7),
    
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    availability_type availability_type_enum NOT NULL
);

-- Add an index for faster lookups of a students availability.
CREATE INDEX idx_student_availability_student_id ON student_availability_intervals(student_id);


-- Phase 2: Migrate data from the 'student_data' JSONB column.
-- This script is idempotent (safe to run multiple times).
INSERT INTO student_availability_intervals (student_id, day_of_week, start_time, end_time, availability_type)
SELECT
    s.id AS student_id,
    -- Convert the day name (key) into its standard integer representation.
    CASE
        WHEN day_data.day_name = 'monday' THEN 1
        WHEN day_data.day_name = 'tuesday' THEN 2
        WHEN day_data.day_name = 'wednesday' THEN 3
        WHEN day_data.day_name = 'thursday' THEN 4
        WHEN day_data.day_name = 'friday' THEN 5
        WHEN day_data.day_name = 'saturday' THEN 6
        WHEN day_data.day_name = 'sunday' THEN 7
    END AS day_of_week,
    
    -- Extract and cast the time and type values.
    (interval_data.interval->>'start')::TIME AS start_time,
    (interval_data.interval->>'end')::TIME AS end_time,
    (interval_data.interval->>'type')::availability_type_enum AS availability_type
FROM
    students s,
    -- Unpack the availability object into key/value pairs (day_name, intervals_array)
    jsonb_each(s.student_data->'availability') AS day_data(day_name, intervals_array),
    -- Unpack the intervals array into individual interval objects
    jsonb_array_elements(day_data.intervals_array) AS interval_data(interval)
WHERE
    s.student_data ? 'availability'
ON CONFLICT DO NOTHING; -- Prevents errors if you run the script more than once.

-- then drop the column
ALTER TABLE students
DROP COLUMN student_data;

