-- Step 1: Create the Platform Enum
-- Using generic WEB type for future-proofing, though not actively used in Phase 1
CREATE TYPE platform_type_enum AS ENUM ('IOS', 'ANDROID', 'WEB');

-- Step 2: Create the user_devices table
CREATE TABLE user_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    platform platform_type_enum NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Step 3: Indexes
-- Index for finding all devices of a user (Phase 2 sync)
CREATE INDEX idx_user_devices_user_id ON user_devices(user_id);

-- Note: 'token' is UNIQUE, so it gets an implicit index.
