-- Phase 1: Add the 'birth_date' column to the 'teachers' table.
-- This column will store the teachers date of birth.
ALTER TABLE teachers
ADD COLUMN birth_date DATE;

-- Phase 2: Create the new 'educational_system_enum' type.
-- This ENUM will store the different educational systems a teacher can specialize in.
CREATE TYPE educational_system_enum AS ENUM (
    'IGCSE',
    'SAT',
    'National-EG',
    'National-KW'
);

-- Phase 3: Create the 'teacher_specialties' table.
-- This table will store the subjects and educational systems each teacher is specialized in.
CREATE TABLE teacher_specialties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
    subject subject_enum NOT NULL,
    educational_system educational_system_enum NOT NULL,
    
    -- A teacher can only have one entry for a specific subject and educational system combination.
    UNIQUE(teacher_id, subject, educational_system)
);

-- Add an index for faster lookups by teacher_id.
CREATE INDEX idx_teacher_specialties_teacher_id ON teacher_specialties(teacher_id);

