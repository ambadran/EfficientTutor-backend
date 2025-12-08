-- Phase 1: Update the ENUM type
-- We use separate ALTER TYPE commands because they cannot be combined in one statement.
ALTER TYPE availability_type_enum ADD VALUE IF NOT EXISTS 'work';
ALTER TYPE availability_type_enum ADD VALUE IF NOT EXISTS 'personal';

-- Phase 2: Rename the table
ALTER TABLE student_availability_intervals RENAME TO availability_intervals;

-- Phase 3: Generalize the user column
-- Step 3.1: Rename the column
ALTER TABLE availability_intervals RENAME COLUMN student_id TO user_id;

-- Step 3.2: Drop the old foreign key constraint that pointed specifically to 'students'
ALTER TABLE availability_intervals DROP CONSTRAINT student_availability_intervals_student_id_fkey;

-- Step 3.3: Add the new foreign key constraint pointing to the generic 'users' table
-- This works because Students and Teachers both share the same ID as their User record (1-to-1).
ALTER TABLE availability_intervals 
ADD CONSTRAINT availability_intervals_user_id_fkey 
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Step 3.4: Rename the index and check constraint to match the new naming convention
ALTER INDEX idx_student_availability_student_id RENAME TO idx_availability_intervals_user_id;
ALTER TABLE availability_intervals RENAME CONSTRAINT student_availability_intervals_day_of_week_check TO availability_intervals_day_of_week_check;
ALTER TABLE availability_intervals RENAME CONSTRAINT student_availability_intervals_pkey TO availability_intervals_pkey;
