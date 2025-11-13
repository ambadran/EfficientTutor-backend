-- Create the 'admins' table with a 1-to-1 relationship to 'users'.
CREATE TABLE admins (
    id UUID PRIMARY KEY NOT NULL REFERENCES users(id) ON DELETE CASCADE
);


-- Create a new admin user.
DO $$
DECLARE
    new_admin_id UUID;
BEGIN
    -- 1. Insert the user record with role 'admin'
    INSERT INTO users (
        id,
        email,
        password,
        first_name,
        last_name,
        role,
        timezone
    )
    VALUES (
        gen_random_uuid(),
        'admin@et.com',
        '', -- REPLACE THIS
        'AbdulRahman',
        'Badran',
        'admin',
        'Africa/Cairo'
    )
    RETURNING id INTO new_admin_id;

    -- 2. Insert the corresponding admin record
    INSERT INTO admins (id)
    VALUES (new_admin_id);

    RAISE NOTICE 'Admin user created with ID: %', new_admin_id;
END $$;
