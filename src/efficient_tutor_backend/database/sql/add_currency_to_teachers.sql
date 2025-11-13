-- Add a 'currency' column to the 'teachers' table for financial consistency.
-- It is non-nullable and defaults to 'EGP', matching the 'parents' table.
ALTER TABLE teachers
ADD COLUMN currency TEXT NOT NULL DEFAULT 'EGP';
