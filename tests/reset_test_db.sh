#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# Set the default database user
DB_USER="mr_a_717"


# On macOS, the user is different. 'Darwin' is the kernel name for macOS.
if [[ "$(uname)" == "Darwin" ]]; then
  DB_USER="ambadran717"
fi

# Load environment variables like DATABASE_URL
# Make sure this path is correct relative to where you run the script
if [ -f ../.env ]; then
  source ../.env
else
  echo "Error: ../.env file not found."
  exit 1
fi

# --- Logic ---
# Check if the first argument is --download-recent
if [[ "$1" == "--download-recent" ]]; then
  echo "Downloading a fresh copy of the production database..."
  pg_dump "$DATABASE_URL_PROD_CLI" --format=c --no-owner --no-privileges > prod_backup.dump
  echo "Download complete."
fi

# --- Restore Database ---
# This command will always run, either after the download or on its own.
echo "Restoring database 'efficient_tutor_test_db' for user '$DB_USER'..."
# 1. This is your "cascade destroy" — it drops the DB and all dependencies.
dropdb --if-exists --force -h localhost -U "$DB_USER" efficient_tutor_test_db

# 2. This re-creates the empty database.
createdb -h localhost -U "$DB_USER" -O "$DB_USER" efficient_tutor_test_db

# 3. This restores your backup onto the clean slate.
pg_restore -h localhost -U "$DB_USER" -d efficient_tutor_test_db --no-owner prod_backup.dump
echo "✅ Database reset complete!"
