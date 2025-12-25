#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- 1. Directory Resolution ---
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

# --- 2. Load Environment ---
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
else
  echo "❌ Error: .env file not found at $ENV_FILE"
  exit 1
fi

# --- 3. Configuration ---
if [ -z "$DATABASE_URL_PROD_CLI" ]; then
    echo "❌ Error: DATABASE_URL_PROD_CLI is not defined in .env"
    exit 1
fi

# Determine Backup File
# Priority 1: prod_backup_dont_delete.dump (The safe snapshot)
# Priority 2: prod_backup.dump (The latest snapshot)
BACKUP_FILE="$SCRIPT_DIR/prod_backup_dont_delete.dump"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "⚠️  'prod_backup_dont_delete.dump' not found. Checking for 'prod_backup.dump'..."
    BACKUP_FILE="$SCRIPT_DIR/prod_backup.dump"
    if [ ! -f "$BACKUP_FILE" ]; then
        echo "❌ Error: No backup file found. Cannot rollback."
        exit 1
    fi
fi

# Extract Database Name from URL for Confirmation
# Assumes format: postgresql://user:pass@host:port/dbname or similar
# We use regex to grab the last path component
DB_NAME=$(echo "$DATABASE_URL_PROD_CLI" | sed -E 's/.*\/([^?]+).*/\1/')

# --- 4. Safety Prompt ---
echo "===================================================================="
echo "🚨 DANGER: PRODUCTION ROLLBACK INITIATED 🚨"
echo "===================================================================="
echo "This script will:"
echo "  1. CONNECT to the PRODUCTION database: $DB_NAME"
echo "  2. DROP all existing data and schema."
echo "  3. RESTORE from backup file: $(basename "$BACKUP_FILE")"
echo ""
echo "This action is IRREVERSIBLE."
echo "===================================================================="
echo -n "Type the database name ('$DB_NAME') to confirm: "
read -r CONFIRMATION

if [ "$CONFIRMATION" != "$DB_NAME" ]; then
    echo "❌ Confirmation failed. Aborting."
    exit 1
fi

echo ""
echo "🚀 Starting Rollback..."

# --- 5. Execute Restore ---
# We use pg_restore with the production URL directly.
# --clean: Drop database objects before creating them.
# --if-exists: Used with --clean to avoid errors if objects don't exist.
# --no-owner / --no-privileges: Standard for restoring to cloud DBs where roles might differ.

pg_restore --dbname="$DATABASE_URL_PROD_CLI" --clean --if-exists --no-owner --no-privileges "$BACKUP_FILE"

echo ""
echo "✅ Rollback complete. Production database has been restored."
