'''

'''
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .common.logger import log
from .common.config import settings
from .api import auth, users
from .models.enums import load_dynamic_enums # Import the loader
from .database.engine import get_db_session # Import the session dependency

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION
)

# --- NEW: Add CORS Middleware ---
origins = [
    # "http://localhost",
    # "http://localhost:8000",
    # "http://127.0.0.1",
    # "http://127.0.0.1:8000",
    # "http://0.0.0.0",
    # "http://0.0.0.0:8000",
    "http://0.0.0.0:8080",
    # Add the URL of your deployed frontend if applicable
    "efficienttutor.tech"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,              # List of origins allowed (or "*" for all)
    allow_credentials=True,             # Allow cookies to be included
    allow_methods=["*"],                # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],                # Allow all headers
)
# --- End of CORS Middleware ---

@app.on_event("startup")
async def startup_event():
    """
    On startup, connect to the DB and load dynamic configurations like Enums.
    """
    log.info("FastAPI application startup...")
    # We need a database session to load the enums
    async for db in get_db_session():
        await load_dynamic_enums(db)
        break # We only need to do this once

app.include_router(auth.router)
app.include_router(users.router)

@app.get("/")
async def health_check():
    return {"status": "ok", "message": f"{settings.APP_NAME} is running"}
