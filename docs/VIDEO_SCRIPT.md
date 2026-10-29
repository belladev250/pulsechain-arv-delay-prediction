# PulseChain walkthrough video: script (target 9 minutes, maximum 10)

Record your screen with your voice (QuickTime: File > New Screen Recording). Before recording:
- Fresh start: stop the backend, delete `app/pulsechain.db`, restart it (`uvicorn main:app --reload`), start the frontend (`npm run dev`).
- Have three terminals ready: backend, one for tests, and the browser at http://localhost:5173.
- Have VS Code open on the project folder.

## 0:00 Introduction (30 s)
Say: "PulseChain warns supply-chain staff which HIV/ARV shipments are likely to arrive late, and lets health workers report shortages. It predicts risk at country level and combines it with district-level reports."
Show: the README top section.

## 0:30 Scope (45 s) [Rubric: scope alignment]
Show: the feature table in `docs/PulseChain_Technical_Report.pdf`.
Say: "Everything in the proposal is implemented except the SMS gateway and national LMIS integration, which were out of scope. I added sign-in and roles, batch scoring and delay-cause logging. The dataset has no district field, so prediction is country-level."

## 1:15 Core functions: sign-in and roles (1 min) [A, B]
1. Sign in as `admin@pulsechain.local`: all tabs. Sign out.
2. Sign in as `gasabo@pulsechain.local`: fewer tabs, only Gasabo data.
3. Say: "The server enforces this on every request, not just the page. A token signed with HMAC identifies the user, and every query is filtered by role."
4. Create an account, show "pending", show the refusal on sign-in, approve it as `rwanda.manager@pulsechain.local` in Users.

## 2:15 Core functions: prediction (1 min 15 s) [A, B]
Sign in as admin. Predict risk tab: SCMS from RDC, Burundi, Truck, press Predict.
Say: "The browser sends JSON to /api/predict. The backend builds leakage-safe features, LightGBM scores it, isotonic calibration converts the score to a probability capped at 50%, and a percentile rule gives the band. SHAP explains the top reasons in plain words."
Then Batch: upload a CSV, show results and download.

## 3:30 Shipments, reporting and dashboard (1 min 30 s) [A]
- Shipments: ranked by risk; click Why?; log a delay cause.
- Report shortage: submit, mark restocked.
- Dashboard: Load demo data, then Simulate live reports; point to the district flag rule (2 or more open shortages and risk 1.15 times the overall level), delay causes, and the model check by risk band.
Say: "Demo reports are simulated and labelled as Demo data."

## 5:00 Testing with different inputs (1 min) [C]
Show errors in the UI and in the Swagger page (http://127.0.0.1:8000/docs):
- wrong password; unapproved account;
- as `gasabo@`, try Uganda in Predict: blocked (403);
- invalid report (empty facility); survey with missing answers.
Say: "Each invalid input returns a clear message, not a crash."

## 6:00 Two or more testing strategies (2 min) [D]
In the terminal:
1. `python3 -m unittest discover -s tests -v`. Say: "Unit tests: 28 tests for passwords, token tampering, role scope, calibration and risk bands. Chosen because security and scoring logic must be right in isolation. All pass in under a second."
2. `python3 scripts/smoke_test.py`. Say: "Integration tests: 35 checks against the live server, including every role limit. Chosen to catch access leaks and broken interactions. 35 of 35 pass."
3. `python3 scripts/perf_test.py`. Say: "Performance and stress test: single prediction averages about 6 ms, far below the 2-second requirement; 200 requests from 20 parallel users, 227 requests per second, no errors."
4. Open the Feedback page: "Usability: the System Usability Scale, 3 tasks, anonymous, [state your n and mean SUS]."
Say what improved: "Testing the refactored code exposed a crash in the model-missing fallback, which I fixed."

## 8:00 Performance and compatibility (45 s) [E]
- Open the app in two browsers (for example Chrome and Safari).
- Narrow the window to phone width: show the tab bar scrolling and cards stacking.
- Say: "Tested on an Apple Silicon Mac, Python 3.9.6, CPU only. The model needs no GPU. Low-end hardware was not tested."

## 8:45 Code quality (45 s) [Section 3]
Show in VS Code: `app/` folder (routers, services), then `services/risk_model.py` (the RiskModel class), `dependencies.py`.
Say: "The backend was one 1,000-line file; now routers handle HTTP, services hold the logic, and the RiskModel class encapsulates the model. Reusable React components and unit-tested pure functions."

## 9:30 Close (20 s)
Say: "Limitations: only 82 late test shipments, ML does not clearly beat the vendor rule, districts inherit country risk. Next: a real pilot, cloud deployment and retraining."

### After recording
Upload the video (Google Drive or YouTube unlisted), set the link to "Anyone with the link can view", and paste the link in `README.md` and in the report.
