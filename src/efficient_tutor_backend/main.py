'''

'''
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .common.logger import log
from .common.config import settings
from .api import auth, users

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    # --- Code to run ON STARTUP ---
    log.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    
    # Enum loading logic is now removed as it's handled by static imports
    
    yield # --- Application is now running ---

    # --- Code to run ON SHUTDOWN ---
    log.info("FastAPI application shutting down...")

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



app.include_router(auth.router)
app.include_router(users.router)

@app.get("/")
async def health_check():
    return {"status": "ok", "message": f"{settings.APP_NAME} is running"}
