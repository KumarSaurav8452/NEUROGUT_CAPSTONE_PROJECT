# NEUROGUT — Full Platform Implementation Plan

## Overview

Build the **NEUROGUT Gut-Brain Axis Diagnostic Platform** as specified in the PRD: a hospital-facing SaaS tool that takes gut microbiome data, predicts Depression & Anxiety via a stacked ensemble ML model, and presents results through an interactive clinical dashboard.

The project lives at `c:\Major_project_Neuro_Gut`. Currently it contains:
- Raw data (`Supplementary Table S1.xlsx`, `S4.xlsx`)
- Processed data (`X_resampled.csv`, `y_resampled.csv` — 112 samples, 13 bacterial taxa)
- Pipeline notebooks (`new_pathway_pipeline.ipynb`, `pipeline_smote.ipynb`)
- A pre-trained CNN model (`best_cnn_model.keras`) — not the champion model
- **No serialized GutMicrobiomeStacker**, no backend, no frontend yet

**Python 3.14.3** and **Node.js 24.14.0** are available. All ML/backend packages need to be installed.

---

## User Review Required

> [!IMPORTANT]
> **Database Choice**: The PRD specifies PostgreSQL. For local development without a Postgres server, I'll use **SQLite** initially with SQLAlchemy (swap to Postgres is trivial). Should I set up PostgreSQL instead?

> [!IMPORTANT]
> **File Storage**: The PRD mentions AWS S3 / MinIO. For Phase 1-3, I'll store generated PDF reports **locally** in a `reports/` directory. Is that acceptable for now?

> [!IMPORTANT]
> **Authentication**: For the initial build, I'll implement JWT-based auth with hardcoded demo users (admin, clinician, researcher). Full NextAuth integration can follow. Acceptable?

> [!WARNING]
> **Python 3.14 Compatibility**: Some packages (XGBoost, SDV) may have issues with Python 3.14.3. If I encounter issues, I may need to use compatibility workarounds or downgrade the Python version. I'll keep you informed.

## Open Questions

1. **Do you have a trained GutMicrobiomeStacker model saved anywhere?** The notebooks exist but I don't see a serialized `.pkl` file. I'll need to either:
   - (A) Run the notebook pipeline to train and export the model, OR
   - (B) Build the stacker from scratch using the code in `new_pathway_pipeline.ipynb`
2. **Deployment target**: Are we deploying locally only, or to a cloud VM? This affects Phase 4.

---

## Proposed Changes — Phased Implementation

### Phase 1: ML Model Serialization & Testing Infrastructure (Sprint 1)

#### [NEW] neurogut-backend/models/export_model.py
- Script to build, train, and export the `GutMicrobiomeStacker` from `X_resampled.csv` + `y_resampled.csv`
- Exports: `stacker.pkl`, `scaler.pkl`, `model_card.json`
- Uses: `RandomForestClassifier` (MultiOutput), `XGBClassifier` (ClassifierChain), `LogisticRegression` (meta-learner)
- Boruta feature selection (or uses the pre-selected 13 taxa)

#### [NEW] neurogut-backend/tests/test_synthetic.py
- SDV `GaussianCopulaSynthesizer` generates 500 synthetic samples
- Evaluates: `hamming_loss`, `roc_auc_score`, `classification_report`
- Edge case tests (extreme dysbiosis, near-healthy, anxiety-only, missing taxa, determinism, OOD)

#### [NEW] neurogut-backend/models/model_card.json
- Version, training data stats, metrics, feature list, limitations

---

### Phase 2: FastAPI Backend (Sprints 2–4)

#### [NEW] neurogut-backend/main.py
- FastAPI app entrypoint, CORS middleware, lifespan (model loading)

#### [NEW] neurogut-backend/requirements.txt
- All Python dependencies pinned

#### [NEW] neurogut-backend/Dockerfile
- Python 3.11 base, multi-stage build

#### [NEW] neurogut-backend/api/auth.py
- JWT login/refresh endpoints, bcrypt password hashing
- Role-based middleware (admin, clinician, researcher)

#### [NEW] neurogut-backend/api/predict.py
- `POST /api/predict` — 13-feature input → probabilities + importances + risk tier
- `POST /api/predict/batch` — CSV upload → array of predictions

#### [NEW] neurogut-backend/api/patients.py
- CRUD: create patient, list patients, get patient + history

#### [NEW] neurogut-backend/api/reports.py
- `POST /api/reports/generate` — ReportLab PDF with charts
- `GET /api/reports/{id}/download` — serve PDF

#### [NEW] neurogut-backend/api/admin.py
- User management endpoints (admin role only)

#### [NEW] neurogut-backend/schemas/prediction.py
- Pydantic models: `PredictionInput` (13 floats [0,1]), `PredictionOutput`, `BatchInput`

#### [NEW] neurogut-backend/schemas/patient.py
- Pydantic models: `PatientCreate`, `PatientResponse`, `SampleCreate`

#### [NEW] neurogut-backend/services/predictor.py
- Loads `stacker.pkl` + `scaler.pkl` at startup
- `predict()` → probabilities, labels, importances, risk tier, consensus features

#### [NEW] neurogut-backend/services/pdf_generator.py
- ReportLab-based PDF with patient info, prediction summary, radar chart, heatmap, recommendations

#### [NEW] neurogut-backend/services/storage.py
- Local file storage (swappable to S3/MinIO)

#### [NEW] neurogut-backend/db/database.py
- SQLAlchemy async engine + session factory

#### [NEW] neurogut-backend/db/models.py
- ORM models: `Hospital`, `User`, `Patient`, `MicrobiomeSample`, `Prediction`, `Report`

#### [NEW] neurogut-backend/db/init_db.py
- Create tables, seed demo hospital + users

---

### Phase 3: Next.js Frontend (Sprints 5–9)

#### [NEW] neurogut-frontend/
- Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui scaffold
- Clinical design system: teal palette, Inter + JetBrains Mono fonts

#### Key Pages:
| Route | Component | Description |
|-------|-----------|-------------|
| `/` | `LandingPage` | Product overview, hospital onboarding CTA |
| `/login` | `LoginPage` | Email + password auth |
| `/dashboard` | `Dashboard` | Stats cards, recent predictions, quick actions |
| `/patients` | `PatientList` | Search, filter, pagination |
| `/patients/[id]` | `PatientProfile` | History, risk timeline |
| `/analysis/new` | `AnalysisWizard` | Patient select → Sample input → Run |
| `/analysis/[id]` | `ResultsView` | RiskCards, Radar, Heatmap, Venn |
| `/reports` | `ReportHistory` | All PDFs, filter |
| `/admin/users` | `UserManagement` | Invite clinicians, roles |
| `/admin/settings` | `HospitalSettings` | Name, logo, config |
| `/docs` | `Documentation` | API reference, CSV guide, model card |

#### Key Components:
- `<RiskCard>` — Probability gauge, risk tier badge, animated fill
- `<BiomarkerRadar>` — Plotly polar chart (RF green, XGB red)
- `<DysbiosisHeatmap>` — Taxa × condition heatmap
- `<VennDiagram>` — SVG RF/XGB feature overlap
- `<SampleInputForm>` — 13 sliders + CSV upload
- `<PredictionTimeline>` — Line chart of risk over time

---

### Phase 4: Integration, Docker & Deployment (Sprints 10–11)

#### [NEW] docker-compose.yml
- Services: `backend` (FastAPI), `frontend` (Next.js), `nginx` (reverse proxy)
- Optionally `postgres` if switching from SQLite

#### [NEW] nginx/nginx.conf
- Reverse proxy: `/api` → backend:8000, `/` → frontend:3000
- SSL termination ready

#### [NEW] neurogut-backend/tests/test_api.py
- Integration tests for all endpoints

---

## Verification Plan

### Automated Tests
- `pytest neurogut-backend/tests/` — model export, synthetic data, API endpoints
- `npm test` in frontend — component rendering tests
- Manual browser testing of full clinician flow

### Manual Verification
- Run `docker-compose up` and verify the full stack
- Complete a clinician journey: login → register patient → submit sample → view results → download PDF
- Verify model predictions match expected outputs for known edge cases
