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

Since the local DB is now in v0.2 format, we must upgrade it. This script:
1.  Executes SQL scripts located in `src/efficient_tutor_backend/database/sql/`.
2.  **Schema Updates:** Adds new tables, columns, and constraints.
3.  **Data Migration:** Transforms existing data to fit the new structure (filling blanks, mapping enums, etc.).

### Step 3: Normalize Passwords
**Script:** `scripts/v0.3_migration/update_passwords.py`

The v0.2 database used an incompatible hashing method.
1.  This script takes known plain-text passwords (collected securely).
2.  Re-hashes them using the v0.3 compliant method (e.g., `bcrypt`).
3.  Updates the user records in the local database.
4.  *Note:* For the test environment, generated users (in Step 4) will have their passwords standardized to the hash of `'testtest'`.

---

## 🧬 Data Generation & Seeding

At this stage, the local DB has v0.3 schema and production data, but **pytest will still fail** because the specific UUIDs in `tests/constants.py` (which the tests rely on) might not exist or be in the expected state.

We use a **"Extract -> Merge -> Load"** strategy to solve this.

### Step 4: The Extractor (Generate Test Data)
**Script:** `scripts/generate_test_data.py`

This script connects to the now-migrated local database and "extracts" the data into Python code files located in `tests/database/data/auto_*.py`.

*   **Function:** Reads rows from tables (Users, Tuitions, Logs, etc.).
*   **Anonymization:**
    *   By default, PII (Names, Emails) is replaced with `Faker` data.
    *   **Toggle:** You can disable this using the `--no-anonymize` flag if you need real production data for debugging.
*   **Passwords:** All extracted users will have their password set to the hash of `'testtest'`.

### Step 5: The Loader (Seed Test DB)
**Script:** `tests/database/seed_test_db.py`

This is the final step that prepares the database for `pytest`.

1.  **Truncate:** Clears all data from the tables to ensure a clean slate.
2.  **Merge:** It imports data from two sources:
    *   **Manual Data (`tests/database/data/*.py`):** The hand-crafted records matching `tests/constants.py`.
    *   **Auto Data (`tests/database/data/auto_*.py`):** The massive dataset generated in Step 4.
3.  **Deduplication:** It intelligently merges these lists. If a record in "Auto" has the same ID (or unique constraint) as a record in "Manual", the "Manual" version takes precedence to ensure test stability.
4.  **Topological Insert:** It inserts records in strict dependency order (Admins -> Teachers -> Students -> Tuitions -> Logs) to satisfy Foreign Key constraints.

---

## 🏁 Result

After completing this pipeline, you have a local database that:
1.  **Passes Tests:** Contains all specific records required by `pytest`.
2.  **Realistic:** Contains thousands of records from production for frontend development and performance checking.
3.  **Safe:** PII is anonymized (unless opted out).
4.  **Accessible:** Passwords are set to `'testtest'`.

## 🛠️ Quick Command Reference

All scripts are directory-agnostic and can be run from the project root.

```bash
# 1. Reset & Restore
# Option A: Use existing dump
./scripts/reset_test_db.sh
# Option B: Download fresh dump from production (requires PROD env var)
./scripts/reset_test_db.sh --download-recent

# 2. Migrate to v0.3
uv run scripts/v0.3_migration/run_migrations.py

# 3. Fix Passwords (Optional but recommended for consistency)
uv run scripts/v0.3_migration/update_passwords.py

# 4. Generate Data Files (Extract)
# Note: This overwrites files in tests/database/data/auto_*.py
# Default (Anonymized):
uv run scripts/generate_test_data.py --db-url $DATABASE_URL_TEST_CLI
# Debug Mode (Real Names/Emails):
uv run scripts/generate_test_data.py --db-url $DATABASE_URL_TEST_CLI --no-anonymize

# 5. Seed (Load)
# This truncates the DB and re-inserts the merged (Manual + Auto) data
uv run tests/database/seed_test_db.py
```