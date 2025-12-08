-- Phase 1: Add the new column (nullable)
ALTER TABLE students
ADD COLUMN educational_system educational_system_enum;

-- Phase 2: Seed existing students with a default value
UPDATE students
SET educational_system = 'IGCSE';
