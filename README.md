# PulseChain: HIV/ARV Shipment Delay Early-Warning System

## Description
PulseChain predicts the probability that an HIV/ARV shipment will arrive late (LightGBM, with a Logistic Regression baseline), explains each prediction with SHAP, and lets health workers report shortages and restocks. A dashboard combines reported shortages with each country's historical late-delivery rate.

Data: PEPFAR/USAID SCMS Delivery History, 2,317 shipments from 7 East African countries (2006-2015).

## GitHub repo
<add link>

## Project structure
```
notebooks/PulseChain_Model_Colab.ipynb   data analysis, model training, metrics, SHAP
app/main.py                              FastAPI backend (API + SQLite)
frontend/                                React + Vite + Tailwind CSS frontend
app/static/                              fallback single-file frontend (used only if frontend/dist is missing)
app/data/                                dropdown options and vendor/country history
app/models/lgbm_pipeline.joblib          trained model (exported from the notebook)
data/                                    SCMS dataset
figures/                                 notebook charts
```

## Setup
Requirements: Python 3.10+ and Node.js 18+.

1. Train and export the model: run the notebook in Google Colab, then download `models/lgbm_pipeline.joblib` and place it in `app/models/`.
2. Backend:
```bash
python3 -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r app/requirements.txt
cd app
uvicorn main:app --reload
```
3. Frontend (development, second terminal):
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. API docs (Swagger UI): http://127.0.0.1:8000/docs

4. Frontend (production build, served by FastAPI):
```bash
cd frontend
npm run build
```
Then open http://127.0.0.1:8000 with only the backend running.

Without the model file the app still runs and shows a clearly labelled heuristic prediction.

## API endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | /api/health | status and whether the model is loaded |
| GET | /api/options | dropdown values |
| POST | /api/predict | delay probability, risk band, SHAP reasons |
| POST | /api/reports | submit a shortage report |
| GET | /api/reports | list reports |
| PATCH | /api/reports/{id}/restock | mark restocked and log restock time |
| GET | /api/dashboard | district-level summary |
| POST | /api/seed | add demo reports |

## Database schema (SQLite)
`reports(id, facility, district, country, product_group, note, status, reported_at, restocked_at, restock_days)`

## Designs
<add screenshots of Predict, Report and Dashboard pages in /designs>

## Deployment plan
Local: laptop, `uvicorn main:app` (no GPU). Cloud option: a single container (FastAPI serves the API and the React page) on Render or Railway, with the model file and SQLite volume mounted; SQLite can later be replaced by PostgreSQL.

## Video demo
<add link>
