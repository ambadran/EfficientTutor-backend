'''

'''
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .database.engine import create_db_engine_and_session_factory, dispose_db_engine
from .common.logger import log
from .common.config import settings
from .api import auth, users, tuitions, timetable, tuition_logs, payment_logs, financial_summaries, notes # Added notes

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    # --- On App Startup ---
    log.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    create_db_engine_and_session_factory()
    
    yield # --- Application is now running ---

    # --- On App Shutdown ---
    if not settings.TEST_MODE:
        log.info("Application lifespan shutdown...")
        await dispose_db_engine()
    else:
        log.info("Skipping database engine disposal in TEST_MODE.")

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan

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

@app.get("/")
async def health_check():
    return {"status": "ok", "message": f"{settings.APP_NAME} is running"}

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tuitions.router)
app.include_router(timetable.router)
app.include_router(tuition_logs.router)
app.include_router(payment_logs.router)
app.include_router(financial_summaries.router)
app.include_router(notes.router) # Included notes router


