# Project: EfficientTutor Backend (v0.3 Refactor)

## Core Principles & Golden Rules
1.  **NEVER ASSUME:** If you are missing information, data structures, or clear requirements, YOU MUST ASK before generating code. Ambiguity leads to technical debt.
2.  **STRICT LAYERING:** Respect the architecture. Do not bypass layers (e.g., API layer should never query the DB directly).
3.  **MODULARITY & MAINTAINABILITY:** Code must be clean, well-documented, and separated by concern.
4.  **MODERN STANDARDS:** Use the latest stable paradigms for our stack (FastAPI, Pydantic v2, SQLAlchemy 2.0+ Async).
5.  **NO DEPRECATED CODE:** Never use deprecated functions or patterns (e.g., prefer `lifespan` over `@app.on_event`, `ConfigDict` over `class Config`).

## Tech Stack
* **Language:** Python 3.13
* **Framework:** FastAPI
* **Database:** PostgreSQL (Async via `asyncpg`)
* **ORM:** SQLAlchemy 2.0+ (Async)
* **Validation:** Pydantic v2
* **Auth:** JWT (OAuth2 Password Bearer)
* **Config:** `pydantic-settings`

## Architecture Overview
The application follows a strict 3-layer architecture:
1.  **API Layer (`src/efficient_tutor_backend/api/`):** Thin Controllers. Handles HTTP requests/responses, dependency injection, and status codes. Delegates all logic to Services.
2.  **Service Layer (`src/efficient_tutor_backend/services/`):** Business Logic. Contains the core rules of the application. Interacts with the Database Layer.
3.  **Database Layer (`src/efficient_tutor_backend/database/`):** Data Access. Manages connections, defines SQL table structures (ORM), and executes queries.

## Shared Layers
* **Models (`src/efficient_tutor_backend/models/`):** Pydantic schemas used for data exchange (API input/output) and internal type safety. NOT tied to the database directly.
* **Common (`src/efficient_tutor_backend/common/`):** Utilities, configuration, logging, and custom exceptions.
