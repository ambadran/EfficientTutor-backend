# Database Cycle & Testing Workflow

This document defines the generalized, version-agnostic workflow for maintaining the database schema, generating test data, and ensuring test suite reliability.

## 1. Resetting the Environment
**Script:** `tests/database/reset_test_db.sh`

This script is the "Big Red Button". It completely destroys and recreates the local test database from a backup.
*   **Version Agnostic:** It restores whatever data is in `tests/database/prod_backup.dump`. It does not know about schema versions; it just restores the snapshot.
*   **Usage:**
    *   `./tests/database/reset_test_db.sh`: Restore from local file.
    *   `./tests/database/reset_test_db.sh --download-recent`: Download fresh dump from production before restoring.

## 2. Running Migrations (The Upgrade Path)
**Script:** `scripts/v[Major.Minor]_migration/run_migrations.py`

When moving to a new backend version (e.g., v0.3, v0.4), the local database (restored from the v0.2 dump) must be upgraded.
*   **Structure:** We create a dedicated migration folder/script for each major update.
*   **Responsibilities:**
    1.  **SQL Execution:** Applies schema changes in order.
    2.  **Data Logic:** Runs Python scripts for complex transformations (e.g., password hashing, data synthesis).
*   **Flags:**
    *   `--sql-only`: Useful for debugging. Skips the Python post-processing and only applies schema changes.
    *   `--prod`: Targets the production database (requires confirmation).

## 3. Generating Test Data (The Extractor)
**Script:** `tests/database/generate_test_data.py`

This script bridges the gap between "Real Production Data" and "Test Suite Expectations". It reads the current state of your local database and serializes it into Python code (`tests/database/data/auto_*.py`).

**CRITICAL MAINTENANCE:**
*   **New Tables:** If you add a new table to the database, you **MUST** update the `TABLE_CONFIG` list in this script.
*   **Why?** If you don't, the new table's data won't be extracted, and the seed script (Step 4) won't know about it, potentially causing Foreign Key errors or missing test data.

## 4. Seeding the Test DB (The Loader)
**Script:** `tests/database/seed_test_db.py`

This script prepares the database for `pytest`. It wipes the database clean and inserts a merged dataset (Manual "Golden Records" + Extracted "Auto Data").

**CRITICAL MAINTENANCE:**
*   **New Tables:** If you add a new table, you must update `clear_database()` to `TRUNCATE` it (respecting FK order) and `seed_data()` to insert its data.
*   **New Models:** You must ensure `tests/database/factories.py` has a factory corresponding to the new model. The `factory` name in the extracted data relies on this file.

## Summary Checklist for New Features

When adding a new database feature (e.g., a "Homework" table):

1.  **Migration:** Add SQL to `src/.../sql/` and add filename to `run_migrations.py`.
2.  **Extraction:** Add "Homework" to `TABLE_CONFIG` in `tests/database/generate_test_data.py`.
3.  **Factories:** Add `HomeworkFactory` to `tests/database/factories.py`.
4.  **Seeding:** Add "Homework" to `SEEDING_ORDER` and `clear_database` in `tests/database/seed_test_db.py`.

---

## 🛠️ Quick Command Reference

All scripts are directory-agnostic and can be run from the project root.

```bash
# 1. Reset & Restore
# Option A: Use existing dump
./tests/database/reset_test_db.sh
# Option B: Download fresh dump from production (requires PROD env var)
./tests/database/reset_test_db.sh --download-recent

# 2. Migrate to New Version (Runs SQL + Python Scripts)
# Replace vX.X with the actual version directory (e.g., v0.3)
uv run scripts/vX.X_migration/run_migrations.py

# --- Optional Granular Migration Commands ---
# 2a. Run ONLY SQL migrations (skips python post-processing)
uv run scripts/vX.X_migration/run_migrations.py --sql-only

# 2b. Run specific Python post-processing scripts individually
# (Example: If the version requires fixing IDs or generating data)
python scripts/vX.X_migration/fix_ids_script.py
python scripts/vX.X_migration/synthesize_data_script.py
# --------------------------------------------

# 3. Generate Data Files (Extract)
# Note: This overwrites files in tests/database/data/auto_*.py
# Default (Anonymized):
uv run tests/database/generate_test_data.py --db-url $DATABASE_URL_TEST_CLI
# Debug Mode (Real Names/Emails):
uv run tests/database/generate_test_data.py --db-url $DATABASE_URL_TEST_CLI --no-anonymize

# 4. Seed (Load)
# This truncates the DB and re-inserts the merged (Manual + Auto) data
uv run tests/database/seed_test_db.py
```
