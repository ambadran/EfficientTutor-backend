-- ====================================================================
-- Phase 1: teacher_specialties Table
-- ====================================================================

-- Step 1.1: Add the 'grade' column, populate with default '8', and make it NOT NULL
ALTER TABLE teacher_specialties ADD COLUMN grade INTEGER;
UPDATE teacher_specialties SET grade = 8 WHERE grade IS NULL;
ALTER TABLE teacher_specialties ALTER COLUMN grade SET NOT NULL;

-- Step 1.2: Drop the old unique constraint and add the new one including 'grade'
ALTER TABLE teacher_specialties
DROP CONSTRAINT teacher_specialties_teacher_id_subject_educational_system_key,
ADD CONSTRAINT teacher_specialties_teacher_id_subject_system_grade_key UNIQUE (teacher_id, subject, educational_system, grade);


-- ====================================================================
-- Phase 2: student_subjects Table
-- ====================================================================

-- Step 2.1: Add the 'grade' column
ALTER TABLE student_subjects ADD COLUMN grade INTEGER;

-- Step 2.2: Populate the new 'grade' column from the corresponding students grade
UPDATE student_subjects ss
SET grade = s.grade
FROM students s
WHERE ss.student_id = s.id;

-- Step 2.3: As a safety net, set any remaining NULL grades to the default '8' and make the column NOT NULL
UPDATE student_subjects SET grade = 8 WHERE grade IS NULL;
ALTER TABLE student_subjects ALTER COLUMN grade SET NOT NULL;

-- Step 2.4: Drop the old unique constraint and add the new one
ALTER TABLE student_subjects
DROP CONSTRAINT student_subjects_student_id_subject_teacher_id_educat_key,
ADD CONSTRAINT student_subjects_student_id_subject_teacher_id_system_grade_key UNIQUE (student_id, subject, teacher_id, educational_system, grade);


-- ====================================================================
-- Phase 3: tuitions Table
-- ====================================================================

-- Step 3.1: Add the 'grade' column
ALTER TABLE tuitions ADD COLUMN grade INTEGER;

-- Step 3.2: Populate the 'grade' from the first student found in the related template charges
UPDATE tuitions t
SET grade = (
    SELECT s.grade
    FROM tuition_template_charges ttc
    JOIN students s ON ttc.student_id = s.id
    WHERE ttc.tuition_id = t.id
    LIMIT 1
);

-- Step 3.3: Safety net and NOT NULL constraint
UPDATE tuitions SET grade = 8 WHERE grade IS NULL;
ALTER TABLE tuitions ALTER COLUMN grade SET NOT NULL;


-- ====================================================================
-- Phase 4: tuition_logs Table
-- ====================================================================

-- Step 4.1: Add the 'grade' column
ALTER TABLE tuition_logs ADD COLUMN grade INTEGER;

-- Step 4.2: Populate the 'grade' from the first student found in the related log charges
UPDATE tuition_logs tl
SET grade = (
    SELECT s.grade
    FROM tuition_log_charges tlc
    JOIN students s ON tlc.student_id = s.id
    WHERE tlc.tuition_log_id = tl.id
    LIMIT 1
);

-- Step 4.3: Safety net and NOT NULL constraint
UPDATE tuition_logs SET grade = 8 WHERE grade IS NULL;
ALTER TABLE tuition_logs ALTER COLUMN grade SET NOT NULL;


-- ====================================================================
-- Phase 5: Insert New Teacher Specialty Data
-- ====================================================================
INSERT INTO teacher_specialties (teacher_id, subject, educational_system, grade)
VALUES
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'Math', 'IGCSE', 10),
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'Physics', 'IGCSE', 10),
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'Math', 'IGCSE', 8),
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'Physics', 'IGCSE', 8),
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'Chemistry', 'IGCSE', 8),
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'Biology', 'IGCSE', 8),
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'IT', 'IGCSE', 8),
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'Math', 'IGCSE', 7),
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'Physics', 'IGCSE', 7),
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'Chemistry', 'IGCSE', 7),
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'Biology', 'IGCSE', 7),
    ('dcef54de-bc89-4388-a7a8-dba5d8327447', 'IT', 'IGCSE', 7)
ON CONFLICT (teacher_id, subject, educational_system, grade) DO NOTHING;


-- ====================================================================
-- Phase 6: Add Final Foreign Key Constraints
-- ====================================================================

-- For student_subjects
ALTER TABLE student_subjects
ADD CONSTRAINT fk_student_subjects_to_teacher_specialties
FOREIGN KEY (teacher_id, subject, educational_system, grade)
REFERENCES teacher_specialties (teacher_id, subject, educational_system, grade)
ON UPDATE CASCADE ON DELETE RESTRICT;

-- For tuitions
ALTER TABLE tuitions
ADD CONSTRAINT fk_tuitions_to_teacher_specialties
FOREIGN KEY (teacher_id, subject, educational_system, grade)
REFERENCES teacher_specialties (teacher_id, subject, educational_system, grade)
ON UPDATE CASCADE ON DELETE RESTRICT;
