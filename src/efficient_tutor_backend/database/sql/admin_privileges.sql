-- Phase 1: Create the new ENUM type and add the column to the 'admins' table.

CREATE TYPE admin_privilege_type AS ENUM ('ReadOnly', 'Normal', 'Master');

ALTER TABLE admins
ADD COLUMN privileges admin_privilege_type NOT NULL DEFAULT 'Normal';


-- Phase 2: Enforce the "EXACTLY ONE Master" rule.
-- This partial unique index ensures that only one row in the table can have the value 'Master'.
-- It works by creating a unique index on a constant value, but only for rows that match the WHERE clause.
CREATE UNIQUE INDEX one_master_admin_idx ON admins ((privileges = 'Master')) WHERE privileges = 'Master';


-- Phase 3: Enforce the "AT LEAST ONE Master" and "No Master Deletion" rules using a trigger.

CREATE OR REPLACE FUNCTION check_master_admin_integrity()
RETURNS TRIGGER AS $$
DECLARE
    master_count INTEGER;
BEGIN
    -- Check if the operation is on the 'Master' user
    IF OLD.privileges = 'Master' THEN
        -- Count how many 'Master' users exist. In a BEFORE trigger, this will include the one being changed/deleted.
        SELECT COUNT(*) INTO master_count FROM admins WHERE privileges = 'Master';

        -- If this is the last master user, prevent the change.
        IF master_count <= 1 THEN
            RAISE EXCEPTION 'Cannot delete or change the last Master admin. Transfer the Master privilege to another user first.';
        END IF;
    END IF;

    -- If the check passes, allow the operation to proceed.
    IF (TG_OP = 'DELETE') THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger to run BEFORE any DELETE operation.
CREATE TRIGGER before_delete_admin_trigger
BEFORE DELETE ON admins
FOR EACH ROW EXECUTE FUNCTION check_master_admin_integrity();

-- Create the trigger to run BEFORE any UPDATE operation.
CREATE TRIGGER before_update_admin_trigger
BEFORE UPDATE OF privileges ON admins
FOR EACH ROW EXECUTE FUNCTION check_master_admin_integrity();


-- Phase 4: Initialize the first Master user.
-- This updates the admin user created previously to 'Master', satisfying the new constraints.
UPDATE admins
SET privileges = 'Master'
WHERE id = (SELECT id FROM users WHERE email = 'admin@example.com');
