-- Phase 1: Create the 'timetable_run_user_solutions' table.
-- This table links a specific timetable run to the solution generated for a specific user.
CREATE TABLE timetable_run_user_solutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timetable_run_id BIGINT NOT NULL REFERENCES timetable_runs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Ensure a user has only one solution set per timetable run.
    UNIQUE(timetable_run_id, user_id)
);

-- Index for faster lookups by run_id
CREATE INDEX idx_timetable_run_user_solutions_run_id ON timetable_run_user_solutions(timetable_run_id);


-- Phase 2: Create the 'timetable_solution_slots' table.
-- This table holds the actual time slots assigned to the user in the solution.
CREATE TABLE timetable_solution_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES timetable_run_user_solutions(id) ON DELETE CASCADE,
    
    name TEXT NOT NULL,
    
    -- The "Object UUID" requirement is handled by two nullable foreign keys
    -- with a check constraint to ensure exactly one is set.
    tuition_id UUID REFERENCES tuitions(id) ON DELETE CASCADE,
    availability_interval_id UUID REFERENCES availability_intervals(id) ON DELETE CASCADE,
    
    -- Time details
    day_of_week INTEGER NOT NULL CHECK (day_of_week >= 1 AND day_of_week <= 7),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    
    -- Array of participants (Teacher + Students, or just User)
    participant_ids UUID[] NOT NULL DEFAULT '{}',
    
    -- Constraint: Exactly one of tuition_id or availability_interval_id must be set.
    -- (A OR B) AND NOT (A AND B) is XOR.
    CONSTRAINT check_slot_source_xor CHECK (
        (tuition_id IS NOT NULL AND availability_interval_id IS NULL) OR
        (tuition_id IS NULL AND availability_interval_id IS NOT NULL)
    )
);

-- Index for faster lookups by solution_id
CREATE INDEX idx_timetable_solution_slots_solution_id ON timetable_solution_slots(solution_id);


-- Phase 3: Rename the old solution_data column
ALTER TABLE timetable_runs
RENAME COLUMN solution_data TO legacy_solution_data;

-- sth I forgot to add
UPDATE parents set currency = 'kwd';
