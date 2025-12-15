# EfficientTutor Test Database Workflow

This document details the comprehensive workflow for managing the local test database, migrating legacy production data, and generating the hybrid dataset required for running the full test suite.

## 🌍 Context: The v0.2 to v0.3 Transition

The project is currently transitioning from version `v0.2` to `v0.3`.
*   **Production State:** The live database uses the **v0.2** schema (deprecated). It is missing new tables, columns, and constraints required by the latest backend code.
*   **Backend Expectation:** The latest FastAPI code expects the **v0.3** schema.
*   **Testing Challenge:** Running tests against a raw production dump fails because the schema is wrong. Running tests against an empty schema fails because the tests expect specific "Golden Master" records (specific UUIDs defined in `tests/constants.py`) to exist.

To bridge this gap, we use a multi-step pipeline to creating a **Hybrid Database** containing both:
1.  **Manual "Golden Master" Data:** Fixed records required by unit tests.
2.  **Automated Production Data:** Volume data from production, migrated and anonymized, for realistic load and frontend testing.

---

## 🚀 The Workflow Pipeline

### Step 1: Restore Production Data
**Script:** `scripts/reset_test_db.sh`

This script performs a hard reset of the local test database.
1.  **Cleanup:** Wipes the local `efficient_tutor_test_db` database.
2.  **Creation:** Re-creates the empty database.
3.  **Restore:** Uses `pg_restore` to import the **v0.2** schema and data exactly as it exists in production.

**Options:**
*   `--download-recent`: Downloads a fresh backup from the production database URL (defined in `.env` as `DATABASE_URL_PROD_CLI`) before restoring. If omitted, it uses the existing `prod_backup.dump` in the `scripts/` directory.

### Step 2: Migrate to v0.3
**Script:** `scripts/v0.3_migration/run_migrations.py`

Since the local DB is now in v0.2 format, we must upgrade it. This script orchestrates the entire upgrade process in a specific order:

1.  **SQL Migrations:** Executes SQL scripts located in `src/efficient_tutor_backend/database/sql/`. This updates the schema (tables, columns, constraints) and performs basic data migration.
2.  **Tuition ID Fix (Deterministic Regeneration):**
    *   Calls `scripts/v0.3_migration/fix_tuition_ids.py`.
    *   Rebuilds the `tuitions` table using deterministic UUIDs (based on subject, grade, and participants) to ensure consistency.
    *   Preserves linkages for existing `tuition_logs`, ensuring they point to the new deterministic IDs.
3.  **Timetable Synthesis:**
    *   Calls `scripts/v0.3_migration/synthesize_timetable.py`.
    *   Populates the empty `timetable` tables with a realistic schedule based on the (now deterministic) tuitions.
4.  **Normalize Passwords:**
    *   Calls `scripts/v0.3_migration/update_passwords.py`.
    *   Updates legacy passwords to the new v0.3 hashing standard.
    *   Sets generated test passwords for standardized testing access.

**Flags:**
*   `--sql-only`: If provided, the script will ONLY run the SQL migration files (Step 1) and skip the Python-based post-processing steps (ID fix, Timetable, Passwords). Useful for debugging SQL issues.

### Step 3: Data Generation & Seeding

At this stage, the local DB has v0.3 schema and production data, but **pytest will still fail** because the specific UUIDs in `tests/constants.py` (which the tests rely on) might not exist or be in the expected state.

We use a **"Extract -> Merge -> Load"** strategy to solve this.

#### The Extractor (Generate Test Data)
**Script:** `scripts/generate_test_data.py`

This script connects to the now-migrated local database and "extracts" the data into Python code files located in `tests/database/data/auto_*.py`.

*   **Function:** Reads rows from tables (Users, Tuitions, Logs, Timetables, etc.).
*   **Anonymization:**
    *   By default, PII (Names, Emails) is replaced with `Faker` data.
    *   **Toggle:** You can disable this using the `--no-anonymize` flag if you need real production data for debugging.
*   **Passwords:** All extracted users will have their password set to the hash of `'testtest'`.

#### The Loader (Seed Test DB)
**Script:** `tests/database/seed_test_db.py`

This is the final step that prepares the database for `pytest`.

1.  **Truncate:** Clears all data from the tables to ensure a clean slate.
2.  **Merge:** It imports data from two sources:
    *   **Manual Data (`tests/database/data/*.py`):** The hand-crafted records matching `tests/constants.py`.
    *   **Auto Data (`tests/database/data/auto_*.py`):** The massive dataset generated in the extraction step.
3.  **Deduplication:** It intelligently merges these lists. If a record in "Auto" has the same ID (or unique constraint) as a record in "Manual", the "Manual" version takes precedence to ensure test stability.
4.  **Topological Insert:** It inserts records in strict dependency order to satisfy Foreign Key constraints.

---

## 🏁 Result

After completing this pipeline, you have a local database that:
1.  **Passes Tests:** Contains all specific records required by `pytest`.
2.  **Realistic:** Contains thousands of records from production for frontend development and performance checking.
3.  **Consistent:** Tuitions have deterministic IDs and a valid schedule.
4.  **Safe:** PII is anonymized (unless opted out).
5.  **Accessible:** Passwords are set to `'testtest'`.

## 🛠️ Quick Command Reference

All scripts are directory-agnostic and can be run from the project root.

```bash
# 1. Reset & Restore
# Option A: Use existing dump
./scripts/reset_test_db.sh
# Option B: Download fresh dump from production (requires PROD env var)
./scripts/reset_test_db.sh --download-recent

# 2. Migrate to v0.3 (Runs SQL, ID Fixes, Timetable Synthesis, and Password Updates)
uv run scripts/v0.3_migration/run_migrations.py

# --- Optional Granular Migration Commands ---
# 2a. Run ONLY SQL migrations (skips python scripts)
uv run scripts/v0.3_migration/run_migrations.py --sql-only

# 2b. Run ONLY Tuition ID Fix (Requires Step 2a complete)
python scripts/v0.3_migration/fix_tuition_ids.py

# 2c. Run ONLY Timetable Synthesis (Requires Step 2b complete)
python scripts/v0.3_migration/synthesize_timetable.py

# 2d. Run ONLY Password Updates (Can be run anytime after Step 2a)
python scripts/v0.3_migration/update_passwords.py
# --------------------------------------------

# 3. Generate Data Files (Extract)
# Note: This overwrites files in tests/database/data/auto_*.py
# Default (Anonymized):
uv run scripts/generate_test_data.py --db-url $DATABASE_URL_TEST_CLI
# Debug Mode (Real Names/Emails):
uv run scripts/generate_test_data.py --db-url $DATABASE_URL_TEST_CLI --no-anonymize

# 4. Seed (Load)
# This truncates the DB and re-inserts the merged (Manual + Auto) data
uv run tests/database/seed_test_db.py
```