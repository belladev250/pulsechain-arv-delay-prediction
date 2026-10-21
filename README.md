# PulseChain: HIV/ARV Shipment Delay Early-Warning System

Capstone project by Ineza Bella Melissa (African Leadership University). Supervisor: Elvira Immaculate Khwatenge.

## Description
PulseChain estimates how likely an HIV/ARV shipment is to arrive late, explains each estimate in plain language, and lets health workers report shortages and restocks. A live dashboard combines reported shortages with the model's predicted delay risk to flag districts that need attention.

**Problem.** A late shipment can leave a clinic without ARVs and interrupt patients' treatment. Planners usually learn about a delay only after a clinic runs out.

**Data.** PEPFAR/USAID SCMS Delivery History: 2,317 shipments to 7 East African countries (2006-2015). Target: `target_late` = actual delivery date later than scheduled date (about 12% of shipments; 17.7% in the test period).

## Links
- GitHub repo: `<add link>`
- Video demo (5-10 min): `<add link>`

## Results (held-out test set: newest 20%, 464 shipments, 82 late)
| Model | ROC-AUC | PR-AUC | Top 20% reviewed catches | Lift |
|---|---|---|---|---|
| Rule: vendor recent late rate (baseline) | 0.731 | 0.356 | 40% of late shipments | 2.0x |
| Logistic Regression | 0.734 | 0.402 | 46% | 2.3x |
| LightGBM (default) | 0.781 | 0.416 | 46% | 2.3x |
| **LightGBM (tuned), used in the app** | 0.768 | 0.344 | 39% | 1.9x |

The final model was chosen by time-series cross-validation on the development data only; the test set was not used to select it. ROC-AUC 95% interval for the final model: about 0.72 to 0.81.

**Honest reading.** The machine-learning models perform about the same as the simple vendor-recency rule (the intervals overlap). The added value is calibrated probabilities, per-shipment explanations, and a pipeline ready to learn from real clinic data. Recent vendor performance is the strongest signal.

## Method summary
- Chronological split: oldest 80% for development, newest 20% for testing.
- Leakage-safe history features: only shipments delivered at least 60 days before the scheduled date are used.
- Final feature set (4 features): vendor recent late rate, vendor past late rate, country recent late rate, global recent late rate.
- Features that acted as a clock (shipment counts) were removed after diagnosing a 0.96 correlation with the score.
- Time-series cross-validation (5 folds), randomized hyperparameter search, isotonic calibration, bootstrap confidence intervals, equal-review-capacity comparison (top 20%).
- Risk bands by percentile: High is the top 15% of scores, Medium the next 25%. Displayed probabilities are capped at 50% because few late shipments make higher values unreliable.
- Explanations: SHAP for tree models, coefficient contributions for Logistic Regression.

## Limitations
- Data covers 2006-2015 and only 82 late shipments are in the test set, so results are uncertain and this is a proof of concept.
- The ML models do not clearly beat the simple vendor rule.
- Shortage reports and logged delay causes in the demo are simulated and labelled as demo data.
- The shipment data records the destination country only, so districts inherit their country's risk.
- No login or role control yet.
- Usability evidence is limited to the System Usability Scale responses collected so far.

## Project structure
```
notebooks/PulseChain_Model_Improved.ipynb   data analysis, model training, evaluation, export
app/main.py                                 FastAPI backend (API + SQLite)
app/models/                                 model_pipeline.joblib, calibration.json, thresholds.json,
                                            feature_config.json, history_snapshot.json, initial_metrics.csv
app/data/                                   dropdown options, history stats, held-out shipments
frontend/                                   React + Vite + Tailwind CSS frontend
scripts/smoke_test.py                       end-to-end API check
data/                                       SCMS dataset
figures/                                    notebook charts
designs/                                    screenshots of the app
Dockerfile                                  single-container build
```

## Setup
Requirements: Python 3.10+ and Node.js 18+. On macOS, LightGBM needs `brew install libomp`.

1. Train and export the model: run `notebooks/PulseChain_Model_Improved.ipynb` in Google Colab (upload the dataset CSV, Run all), download the export zip, and copy its files into `app/models/` and `app/data/`.
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

## Features
- **Predict risk:** single-shipment risk band, calibrated probability and plain-language reasons.
- **Batch:** upload a CSV, score every shipment, download the results.
- **Shipments:** held-out shipments ranked by model risk, with the actual outcome, a "Why?" explanation and delay-cause logging.
- **Report shortage:** log shortages, mark restocked, search, filter and delete.
- **Dashboard:** live charts (refresh every few seconds), a demo-data label, a "Simulate live reports" toggle, district bottlenecks, delay causes and a model check of actual late rate by risk band.
- **Model:** held-out metrics, how to read them, and limitations.
- **Feedback:** 10-question System Usability Scale survey with a live average.

## API endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | /api/health | status and whether the model is loaded |
| GET | /api/options | dropdown values |
| POST | /api/predict | risk band, calibrated probability, reasons |
| POST | /api/predict/batch | score many shipments |
| GET | /api/shipments | held-out shipments ranked by risk |
| GET/POST | /api/shipments/{id}/delay-reasons | read or log the actual cause of a delay |
| POST/GET | /api/reports | submit or list shortage reports |
| PATCH | /api/reports/{id}/restock | mark restocked and log restock time |
| DELETE | /api/reports/{id} | delete a report |
| GET | /api/dashboard, /api/analytics | dashboard summaries and chart data |
| POST | /api/seed, /api/simulate/tick | demo data and live simulation |
| GET | /api/model-info | metrics, thresholds, final model |
| POST/GET | /api/feedback, /api/feedback/summary | usability survey |

## Database schema (SQLite)
- `reports(id, facility, district, country, product_group, note, status, reported_at, restocked_at, restock_days)`
- `delay_reasons(id, shipment_id, reason, note, logged_at, is_demo)`
- `feedback(id, answers, sus_score, comment, created_at)`

## Designs
Screenshots of the main pages are in `designs/`: Predict risk, Shipments, Dashboard, Report shortage, Batch, Model and Feedback.

## Testing
With the backend running: `python3 scripts/smoke_test.py` runs an end-to-end API check.

## Deployment plan
**Now (local):** laptop, `uvicorn main:app`; CPU only, no GPU needed.

**Cloud (next step):**
1. Build one container from the `Dockerfile` (it builds the React app and serves it from FastAPI).
2. Deploy to Render or Railway as a single web service; set the start command to `uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Mount a persistent volume for `pulsechain.db`, or move to managed PostgreSQL.
4. Keep the model files in `app/models/` inside the image; retrain by re-running the notebook and rebuilding.
5. Before real use: add authentication and roles, HTTPS, request limits and backups.
6. Pilot with a few health facilities, collect real shortage reports, and retrain on recent shipment data.

```bash
docker build -t pulsechain .
docker run -p 8000:8000 pulsechain
```

## Ethics and data
No patient data is used. Shipment data is public historical supply-chain data. Shortage reports in the demo are simulated.
