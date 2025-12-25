# Backend Deployment Plan (v0.3 Migration)

This document outlines the steps to deploy the v0.3 architecture refactor to Render.com.

## 1. Git Operations
Merge the completed `v0.3` feature branch into `main` using a fast-forward approach to keep the history linear.

```bash
# 1. Switch to the feature branch and ensure it's up to date with main
git checkout v0.3
git pull origin v0.3
git fetch origin main
git rebase main

# 2. Switch to main and fast-forward merge
git checkout main
git pull origin main
git merge --ff-only v0.3

# 3. Push to production
git push origin main
```

## 2. Environment Variables & Secrets
Configure these in the Render.com Dashboard > Environment.

### Generate Secret Key
Run this command locally to generate a secure random key:
```bash
python scripts/generate_secrete_key.py
```
*Copy the output string.*

### Required Environment Variables
| Variable Name | Value / Description |
| :--- | :--- |
| `PYTHON_VERSION` | `3.13.0` |
| `SECRET_KEY` | *(Paste the generated key from above)* |
| `TEST_MODE` | `False` |
| `DATABASE_URL_PROD` | `postgresql+asyncpg://user:pass@host/dbname` (Your Render PostgreSQL Internal URL) |
| `DATABASE_URL_PROD_CLI` | Same as `DATABASE_URL_PROD`. (The migration script handles the async/sync driver conversion automatically). |
| `BACKEND_CORS_ORIGINS` | `["https://efficienttutor.tech"]` (JSON formatted list of allowed domains) |

## 3. Render Service Configuration

Update the **Build & Deploy** settings in your Web Service:

### Build Command
We use `uv` for dependency management. Since Render's default Python environment doesn't have `uv`, we install it first.
```bash
pip install uv && uv sync --frozen
```

### Start Command
We use `uv run` to ensure the command runs within the environment created by `uv sync`.
```bash
uv run fastapi run src/efficient_tutor_backend/main.py --host 0.0.0.0 --port $PORT
```


