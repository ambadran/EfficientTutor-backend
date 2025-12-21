'''

'''
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .database.engine import create_db_engine_and_session_factory, dispose_db_engine
from .common.logger import log
from .common.config import settings
from .api import auth, users, tuitions, timetable, tuition_logs, payment_logs, financial_summaries, notes 

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


# ---- CREATING THE APP ----
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan

)

# --- Add CORS Middleware ---
origins = [
    # URL of testing frontend
    "http://0.0.0.0:8080",
    "http://localhost",
    "http://localhost:3000",

    # URL for IOS Macbook and iPhone testing
    "capacitor://localhost",

    # URL of deployed frontend 
    "https://efficienttutor.tech",
    "efficienttutor.tech"
]

# Extend with environment-specific origins
origins.extend(settings.BACKEND_CORS_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    # List of origins allowed (or "*" for all)
    allow_origins=origins,
    # Allow cookies to be included
    allow_credentials=True,
    # Allow all methods (GET, POST, etc.)
    allow_methods=["*"],
    # Allow all headers
    allow_headers=["*"],)
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
app.include_router(notes.router) 


