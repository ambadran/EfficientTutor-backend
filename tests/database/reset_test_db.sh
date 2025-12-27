#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- 1. Directory Resolution ---
# Get the absolute path of the script directory
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# Get the absolute path of the project root
PROJECT_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

# --- 2. Load Environment ---
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
  # 'set -a' causes variables defined from now on to be automatically exported
  set -a
  source "$ENV_FILE"
  set +a
else
  echo "❌ Error: .env file not found at $ENV_FILE"
  exit 1
fi

# --- 3. Configuration ---
# Set the default database user
DB_USER="mr_a_717"

# On macOS, the user is different.
if [[ "$(uname)" == "Darwin" ]]; then
  DB_USER="ambadran717"
fi

# Define the dump file path (always in the scripts directory)
DUMP_FILE="$SCRIPT_DIR/prod_backup.dump"

# --- 4. Download Logic ---
# Check if the first argument is --download-recent
if [[ "$1" == "--download-recent" ]]; then
  if [ -z "$DATABASE_URL_PROD_CLI" ]; then
    echo "❌ Error: DATABASE_URL_PROD_CLI is not defined in .env"
    exit 1
  fi

  echo "⬇️  Downloading fresh production database..."
  
  # Capture exit status of pg_dump pipeline
  if pg_dump "$DATABASE_URL_PROD_CLI" --format=c --no-owner --no-privileges > "$DUMP_FILE"; then
    echo "✅ Download complete: $DUMP_FILE"
  else
    echo "❌ Error: pg_dump failed. Please check your connection URL."
    # Remove potentially partial/corrupt file
    rm -f "$DUMP_FILE"
    exit 1
  fi
fi

# --- 5. Pre-Restore Check ---
if [ ! -f "$DUMP_FILE" ]; then
  echo "❌ Error: Dump file not found at: $DUMP_FILE"
  echo "   Run with '--download-recent' to fetch it, or place 'prod_backup.dump' in the scripts folder."
  exit 1
fi

# --- 6. Restore Database ---
echo "🔄 Restoring database 'efficient_tutor_test_db' for user '$DB_USER'..."

# 1. Cascade destroy (drop DB)
dropdb --if-exists --force -h localhost -U "$DB_USER" efficient_tutor_test_db

# 2. Re-create empty DB
createdb -h localhost -U "$DB_USER" -O "$DB_USER" efficient_tutor_test_db

# 3. Restore schema and data
pg_restore -h localhost -U "$DB_USER" -d efficient_tutor_test_db --no-owner "$DUMP_FILE"

echo "✅ Database reset complete!"