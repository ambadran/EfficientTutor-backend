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
1.  Downloads the latest production backup (or uses a local dump).
2.  Wipes the local `efficient_tutor_test` database.
3.  Uses `pg_restore` to import the **v0.2** schema and data exactly as it exists in production.

### Step 2: Migrate to v0.3
**Script:** `scripts/v0.3_migration/run_migration.py`

Since the local DB is now in v0.2 format, we must upgrade it. This script:
1.  Executes SQL scripts located in `src/efficient_tutor_backend/database/sql/v0.3_migration/`.
2.  **Schema Updates:** Adds new tables, columns, and constraints.
3.  **Data Migration:** Transforms existing data to fit the new structure (filling blanks, mapping enums, etc.).

### Step 3: Normalize Passwords
**Script:** `scripts/v0.3_migration/update_passwords.py`

The v0.2 database used an incompatible hashing method.
1.  This script takes known plain-text passwords (collected securely).
2.  Re-hashes them using the v0.3 compliant method (e.g., `bcrypt`).
3.  Updates the user records in the local database.
4.  *Note:* At the end of this, all user passwords are currently standardized to the hash of `'testtest'` because the get data script (discussed next) changes passwords.

---

## 🧬 Data Generation & Seeding

At this stage, the local DB has v0.3 schema and production data, but **pytest will still fail** because the specific UUIDs in `tests/constants.py` (which the tests rely on) do not exist or be in the expected state.

We use a **"Extract -> Merge -> Load"** strategy to solve this.

### Step 4: The Extractor (Generate Test Data)
**Script:** `scripts/generate_test_data.py`

This script connects to the now-migrated local database and "extracts" the data into Python code.

*   **Function:** Reads rows from tables (Users, Tuitions, Logs, etc.).
*   **Anonymization:**
    *   By default, PII (Names, Emails) is replaced with `Faker` data.
    *   **Toggle:** You can disable this using the `--no-anonymize` flag if you need real production data for debugging.
*   **Output:** Generates the file `tests/database/data/auto_*.py` (e.g., `auto_users.py`). These files contain lists of dictionaries representing the production data.

### Step 5: The Loader (Seed Test DB)
**Script:** `tests/database/seed_test_db.py`

This is the final step that prepares the database for `pytest`.

1.  **Truncate:** Clears all data from the tables to ensure a clean slate.
2.  **Merge:** It imports data from two sources:
    *   **Manual Data (`tests/database/data/*.py`):** The hand-crafted records matching `tests/constants.py`.
    *   **Auto Data (`tests/database/data/auto_*.py`):** The massive dataset generated in Step 4.
3.  **Deduplication:** It intelligently merges these lists. If a record in "Auto" has the same ID as a record in "Manual", the "Manual" version takes precedence (or duplicates are skipped) to ensure test stability.
4.  **Topological Insert:** It inserts records in strict dependency order (Admins -> Teachers -> Students -> Tuitions -> Logs) to satisfy Foreign Key constraints.

---

## 🏁 Result

After completing this pipeline, you have a local database that:
1.  **Passes Tests:** Contains all specific records required by `pytest`.
2.  **Realistic:** Contains thousands of records from production for frontend development and performance checking.
3.  **Safe:** PII is anonymized (unless opted out).
4.  **Accessible:** Passwords are set to `'testtest'`.

## 🛠️ Quick Command Reference

```bash
# 1. Reset & Restore
./scripts/reset_test_db.sh

# 2. Migrate to v0.3
python scripts/v0.3_migration/run_migration.py

# 3. Fix Passwords
python scripts/v0.3_migration/update_passwords.py

# 4. Generate Data Files (Extract)
# Ensure DATABASE_URL_TEST_CLI is set to your local postgres instance
uv run scripts/generate_test_data.py --db-url $DATABASE_URL_TEST_CLI

# 5. Seed (Load)
python -m tests.database.seed_test_db
```
