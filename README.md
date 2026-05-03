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
