import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.routes import router

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("dubbing_app")

import asyncio
from contextlib import asynccontextmanager

def silence_event_loop_closed_exceptions(loop, context):
    exception = context.get("exception")
    # Suppress harmless Windows Proactor socket reset on client disconnect/seek (HTTP 206)
    if isinstance(exception, ConnectionResetError) or (
        isinstance(exception, OSError) and getattr(exception, "winerror", None) == 10054
    ):
        return
    loop.default_exception_handler(context)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register Windows asyncio exception handler to silence WinError 10054
    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(silence_event_loop_closed_exceptions)
    except Exception:
        pass

    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Storage directories initialized: {settings.DATA_DIR}")
    logger.info(f"Configured ASR Provider: {settings.ASR_PROVIDER}")
    logger.info(f"Configured Translation Provider: {settings.TRANSLATION_PROVIDER}")
    logger.info(f"Configured TTS Provider: {settings.TTS_PROVIDER}")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-grade Hindi to Telugu AI Video Dubbing Backend",
    lifespan=lifespan
)

# Enable CORS for Flutter Web, Desktop, and Mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

@app.get("/")
def root():
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "api_prefix": settings.API_PREFIX
    }
