# NEUROGUT -- Gut-Brain Axis Diagnostic Platform

AI-powered clinical decision support for Depression & Anxiety prediction from gut microbiome composition.

## Architecture

- **ML Model**: GutMicrobiomeStacker (RF + XGB ClassifierChain + LR Meta-Learner)
- **Backend**: FastAPI + SQLAlchemy + SQLite
- **Frontend**: Next.js 16 + TypeScript + Tailwind CSS + Plotly.js
- **Deployment**: Docker + Nginx reverse proxy

## Quick Start (Local)

### Backend
```bash
cd neurogut-backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

### Frontend
```bash
cd neurogut-frontend
npm install
npm run dev -- --port 3000
```

### Docker (All-in-one)
```bash
docker-compose up --build
```

Then visit:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- Via Nginx: http://localhost

## Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@neurogut.demo | admin123 |
| Clinician | clinician@neurogut.demo | clinician123 |
| Researcher | researcher@neurogut.demo | researcher123 |

## Model Metrics (5-Fold CV)

| Metric | Score |
|--------|-------|
| Depression AUC | 0.945 |
| Anxiety AUC | 0.893 |
| Depression F1 | 0.933 |
| Anxiety F1 | 0.862 |
| Hamming Loss | 0.086 |

## Website versions (toggle)
The sidebar has a **Classic | NeuroGut v2** switch:
- **Classic:** the Depression & Anxiety platform above (`/dashboard`).
- **NeuroGut v2:** Parkinson's disease and schizophrenia (`/v2`).
  - **Predictions:** New Prediction (typed values, a CSV, or a MetaPhlAn profile) and Prediction History.
  - **Research findings:** Overview, Schizophrenia, Parkinson's and Methods.
  - **Models:** `neurogut-backend/models/v2/`. Rebuild them with `python -m sczml.deploy` in `research/Neurogut schizophrenia/scz-ml`, with `PYTHONPATH=src`.
  - **Demo uploads:** `data/v2_examples/`.

v2 reads static JSON in `neurogut-frontend/src/data/v2/`. To refresh it after retraining:
```bash
python scripts/export_v2_data.py
```
- Spec: `PRD_Website_v2.md`.
- Research code: `research/Neurogut schizophrenia/` holds the SCZ data pipeline, `scz-ml` (`run_all.bat`) and the PD repo clone. Large data in that folder is git-ignored.
- Local start: run `start_backend.bat` and `start_frontend.bat`.

## Tests
- **v2 prediction API** (22 tests, throwaway SQLite database, `db/neurogut.db` is never touched):
  ```bash
  cd neurogut-backend && .venv\Scripts\python -m pip install -r requirements-dev.txt && .venv\Scripts\python -m pytest tests/test_v2_api.py -q
  ```
- **Research feature code:** `cd "research/Neurogut schizophrenia/scz-ml"`, then `python -m pytest -q tests` with `PYTHONPATH=src`.
- **SVM baseline + SHAP explanations:** `python -m sczml.extras` in `scz-ml` (with `PYTHONPATH=src`) writes `results/extras/`; then re-run `scripts/export_v2_data.py` to show them on the Schizophrenia and Parkinson's pages.
