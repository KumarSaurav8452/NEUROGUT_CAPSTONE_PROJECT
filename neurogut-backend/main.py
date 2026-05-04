"""
NEUROGUT v2.0 -- FastAPI Application Entrypoint
==================================================
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
from services.benchmark_job import compute_cohort_benchmarks

# Routers
from api.auth import router as auth_router
from api.predict import router as predict_router
from api.patients import router as patients_router
from api.reports import router as reports_router
from api.admin import router as admin_router
from api.alerts import router as alerts_router
from api.audit import router as audit_router


# ---------------------------------------------------------------------------
# Lifespan: run on startup and shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("=" * 50)
    print("NEUROGUT v2.0 Backend Starting...")
    print("=" * 50)

    # Initialize database
    init_db()
    seed_demo_data()

    # Load ML model
    predictor_service.load()
    print(f"[Startup] Model loaded: {predictor_service.model_version}")

    # Compute initial cohort benchmarks
    try:
        compute_cohort_benchmarks()
    except Exception as e:
        print(f"[Benchmark] Initial computation skipped: {e}")

    print("=" * 50)
    print("NEUROGUT v2.0 Backend Ready!")
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
        "Gut-Brain Axis Diagnostic Platform v2.0. "
        "AI-powered clinical decision support for Depression & Anxiety prediction "
        "from gut microbiome composition. Now with confidence intervals, "
        "longitudinal tracking, cohort benchmarking, alerts, and audit trail."
    ),
    version="2.0.0",
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

# Register routers (v1.0 + v2.0)
app.include_router(auth_router)
app.include_router(predict_router)
app.include_router(patients_router)
app.include_router(reports_router)
app.include_router(admin_router)
app.include_router(alerts_router)   # v2.0
app.include_router(audit_router)    # v2.0


@app.get("/")
def root():
    return {
        "service": "NEUROGUT API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/model/health",
    }
