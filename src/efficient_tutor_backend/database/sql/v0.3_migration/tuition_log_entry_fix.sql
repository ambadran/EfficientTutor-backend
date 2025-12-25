-- Fix 1: Global Cost Reset
-- Issue: Data migration left costs split/incorrect.
-- Rule: The standard cost for a session is 6.00 per student.
UPDATE tuition_log_charges SET cost = 6.00;

-- Fix 2: Sibling Discount Exception (Omran & Mila)
-- Rule: If BOTH Omran Omran and Mila Omran are in the same session,
-- their individual cost is reduced to 4.50.

WITH SiblingIDs AS (
    -- Find the UUIDs for Omran and Mila
    SELECT u.id 
    FROM users u
    JOIN students s ON u.id = s.id
    WHERE (u.first_name = 'Omran' AND u.last_name = 'Omran')
       OR (u.first_name = 'Mila' AND u.last_name = 'Omran')
),
LogsWithBothSiblings AS (
    -- Find logs that have charges for BOTH siblings
    SELECT tuition_log_id
    FROM tuition_log_charges
    WHERE student_id IN (SELECT id FROM SiblingIDs)
    GROUP BY tuition_log_id
    HAVING COUNT(DISTINCT student_id) = 2 -- Ensures both unique IDs are present in this log
)
-- Apply the discount only to those specific logs and those specific students
UPDATE tuition_log_charges tlc
SET cost = 4.50
FROM LogsWithBothSiblings target_logs
WHERE tlc.tuition_log_id = target_logs.tuition_log_id
  AND tlc.student_id IN (SELECT id FROM SiblingIDs);