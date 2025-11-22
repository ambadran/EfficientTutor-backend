-- Phase 1: Add the educational_system column as nullable
ALTER TABLE student_subjects
ADD COLUMN educational_system educational_system_enum;

-- Phase 2: Update existing rows to have a default value
UPDATE student_subjects
SET educational_system = 'IGCSE'
WHERE educational_system IS NULL;

-- Phase 3: Alter the column to be NOT NULL
ALTER TABLE student_subjects
ALTER COLUMN educational_system SET NOT NULL;

-- Phase 4: Drop the old unique constraint and add a new one including the educational_system
-- The original constraint name was found in the models.py file
ALTER TABLE student_subjects
DROP CONSTRAINT student_subjects_student_id_subject_teacher_id_key,
ADD CONSTRAINT student_subjects_student_id_subject_teacher_id_educat_key UNIQUE (student_id, subject, teacher_id, educational_system);
