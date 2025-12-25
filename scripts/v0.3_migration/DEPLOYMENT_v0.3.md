# v0.3 Database Deployment Guide

This document outlines the procedure for upgrading the **Production** database from `v0.2` to `v0.3`. This is a major structural update that involves schema changes, data migration, ID regeneration, and password hashing updates.

---

## 1. Prerequisites & Safety Checks

Before initiating the deployment, ensure the following:

1.  **Environment Variables:**
    *   Ensure `.env` contains the correct `DATABASE_URL_PROD_CLI`.
2.  **Backup File (Crucial):**
    *   Verify that `scripts/prod_backup_dont_delete.dump` exists. This is the "Safe Harbor" snapshot used by the rollback script.
    *   *If missing:* Run `cp scripts/prod_backup.dump scripts/prod_backup_dont_delete.dump` (assuming `prod_backup.dump` is a recent valid backup).
3.  **Application State:**
    *   Stop the backend API service or enable maintenance mode to prevent data writes during migration.

---

## 2. Deployment Execution

The entire migration pipeline is orchestrated by a single script.

**Command:**
```bash
uv run scripts/v0.3_migration/run_migrations.py --prod
```

**Pipeline Steps (Automated):**
1.  **Prompt:** Asks for explicit confirmation (`y`) to run on Production.
2.  **SQL Migrations:** Executes 12 SQL scripts to update schema tables, columns, and constraints.
3.  **Tuition ID Fix:** Runs `fix_tuition_ids.py`.
    *   Preserves Log & Link data.
    *   Regenerates all Tuitions with **Deterministic UUIDs**.
    *   Restores Log & Link associations.
4.  **Timetable Synthesis:** Runs `synthesize_timetable.py`.
    *   Generates a master timetable schedule based on the new Tuitions.
5.  **Password Updates:** Runs `update_passwords.py`.
    *   Updates legacy passwords to the new v0.3 hashing standard.

---

## 3. Verification

After the script completes successfully, perform the following checks:

### A. Integrity Check
Run the integrity script against the production database:
```bash
uv run scripts/check_integrity.py --prod
```
*   **Success Criteria:**
    *   Orphaned Logs: 0
    *   Orphaned Links: 0
    *   Total Meeting Links: > 0 (approx 22)

### B. Manual Application Check
1.  Restart the backend API.
2.  Login as a Teacher.
3.  Verify that Tuitions are listed.
4.  Verify that the Timetable view is populated.

---

## 4. Fail-Safe Strategy (Rollback)

**If the migration fails or data corruption is detected:**

Do **NOT** attempt to patch the database manually. Use the automated rollback script to revert to the pre-migration state immediately.

**Rollback Command:**
```bash
./scripts/rollback_production.sh
```

**Rollback Process:**
1.  **Prompt:** Asks you to type the database name to confirm destruction.
2.  **Reset:** Connects to `DATABASE_URL_PROD_CLI`.
3.  **Clean:** Drops all existing schema and data (`--clean` flag).
4.  **Restore:** Restores the database from `scripts/prod_backup_dont_delete.dump`.

**Post-Rollback:**
*   The database is now back to `v0.2`.
*   **Action Required:** You MUST revert the deployed application code to the previous `v0.2` version immediately, as the `v0.3` code will fail against the rolled-back database.