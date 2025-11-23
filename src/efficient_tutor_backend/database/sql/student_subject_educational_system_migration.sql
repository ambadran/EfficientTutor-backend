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


/* Now updating the tuitions and tuitions logs tables */

-- Migration for 'tuitions' table
ALTER TABLE tuitions
ADD COLUMN educational_system educational_system_enum;

UPDATE tuitions
SET educational_system = 'IGCSE'
WHERE educational_system IS NULL;

ALTER TABLE tuitions
ALTER COLUMN educational_system SET NOT NULL;

-- Migration for 'tuition_logs' table
ALTER TABLE tuition_logs
ADD COLUMN educational_system educational_system_enum;

UPDATE tuition_logs
SET educational_system = 'IGCSE'
WHERE educational_system IS NULL;

ALTER TABLE tuition_logs
ALTER COLUMN educational_system SET NOT NULL;

-- Phase 5: Add composite foreign key constraints to link to teacher_specialties

-- For student_subjects: Ensures a student is only assigned to a subject/system
-- that the teacher is qualified for.
ALTER TABLE student_subjects
ADD CONSTRAINT fk_student_subjects_to_teacher_specialties
FOREIGN KEY (teacher_id, subject, educational_system)
REFERENCES teacher_specialties (teacher_id, subject, educational_system)
ON UPDATE CASCADE ON DELETE RESTRICT;

-- For tuitions: Ensures a tuition template is only created for a valid specialty.
ALTER TABLE tuitions
ADD CONSTRAINT fk_tuitions_to_teacher_specialties
FOREIGN KEY (teacher_id, subject, educational_system)
REFERENCES teacher_specialties (teacher_id, subject, educational_system)
ON UPDATE CASCADE ON DELETE RESTRICT;
