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
