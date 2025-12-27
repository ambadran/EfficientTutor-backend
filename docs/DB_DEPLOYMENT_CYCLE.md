# Database Production Deployment Guide

This document outlines the standard operating procedure for upgrading the **Production** database to a new major version (e.g., `v0.3` to `v0.4`). This workflow ensures safety, data integrity, and a robust rollback capability.

---

## 1. Prerequisites & Safety Checks

Before initiating any deployment, ensure the following:

1.  **Environment Variables:**
    *   Ensure `.env` contains the correct `DATABASE_URL_PROD_CLI`.
2.  **Backup File (Safe Harbor):**
    *   **Action:** Create a "Safe Harbor" snapshot that will *only* be used for rollback.
    *   **Command:** `cp tests/database/prod_backup.dump tests/database/prod_backup_dont_delete.dump` (Ensure the source dump is recent).
3.  **Application State:**
    *   **Action:** Stop the backend API service or enable "Maintenance Mode" to prevent data writes during the migration.

---

## 2. Deployment Execution

The entire migration pipeline for a specific version is orchestrated by its dedicated runner script.

**Command:**
```bash
uv run scripts/v[Major.Minor]_migration/run_migrations.py --prod
```

**Standard Pipeline Steps:**
1.  **Prompt:** The script MUST ask for explicit confirmation (`y`) to run on Production.
2.  **SQL Migrations:** Executes ordered `.sql` scripts to update schema tables, columns, and constraints.
3.  **Post-Processing (Python):** Executes any required Python scripts for complex data transformations (e.g., ID regeneration, data synthesis, password hashing).

---

## 3. Verification

After the script completes successfully, perform the following checks:

### A. Integrity Check
Run the integrity script against the production database:
```bash
uv run tests/database/check_integrity.py --prod
```
*   **Success Criteria:**
    *   No orphaned records.
    *   Expected data counts match (e.g., number of active users, logs).

### B. Manual Application Check
1.  Restart the backend API with the new version code.
2.  Login as a representative user (Teacher/Admin).
3.  Verify that core features (listings, details, new features) are functional.

---

## 4. Fail-Safe Strategy (Rollback)

**If the migration fails or data corruption is detected:**

Do **NOT** attempt to patch the database manually. Use the automated rollback script to revert to the pre-migration state immediately.

**Rollback Command:**
```bash
./tests/database/rollback_production.sh
```

**Rollback Process:**
1.  **Prompt:** Asks you to type the database name to confirm destruction.
2.  **Reset:** Connects to `DATABASE_URL_PROD_CLI`.
3.  **Clean:** Drops all existing schema and data (`--clean` flag).
4.  **Restore:** Restores the database from `tests/database/prod_backup_dont_delete.dump`.

**Post-Rollback:**
*   The database is now back to the previous version.
*   **CRITICAL ACTION:** You **MUST** revert the deployed application code to the previous version immediately, as the new code will likely be incompatible with the rolled-back database schema.
