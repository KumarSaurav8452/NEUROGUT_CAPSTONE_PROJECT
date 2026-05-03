"""
NEUROGUT -- FastAPI Application Entrypoint
============================================
Run with:  uvicorn main:app --reload --port 8000
From:      neurogut-backend/
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure package imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db.init_db import init_db, seed_demo_data
from services.predictor import predictor_service
from api.auth import router as auth_router
from api.predict import router as predict_router
from api.patients import router as patients_router
from api.reports import router as reports_router
from api.admin import router as admin_router


# ---------------------------------------------------------------------------
# Lifespan: run on startup and shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("=" * 50)
    print("NEUROGUT Backend Starting...")
    print("=" * 50)

    # Initialize database
    init_db()
    seed_demo_data()

    # Load ML model
    predictor_service.load()
    print(f"[Startup] Model loaded: {predictor_service.model_version}")
    print("=" * 50)
    print("NEUROGUT Backend Ready!")
    print("  API Docs: http://localhost:8000/docs")
    print("  Health:   http://localhost:8000/api/model/health")
    print("=" * 50)

    yield

    # --- Shutdown ---
    print("[Shutdown] NEUROGUT Backend stopping.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="NEUROGUT API",
    description=(
        "Gut-Brain Axis Diagnostic Platform. "
        "AI-powered clinical decision support for Depression & Anxiety prediction "
        "from gut microbiome composition."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS -- allow frontend (Next.js on port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(predict_router)
app.include_router(patients_router)
app.include_router(reports_router)
app.include_router(admin_router)


@app.get("/")
def root():
    return {
        "service": "NEUROGUT API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/model/health",
    }
