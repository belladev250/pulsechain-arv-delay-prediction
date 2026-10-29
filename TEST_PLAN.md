# PulseChain: test plan and results

This document describes how PulseChain was tested and what was found. A summary with the performance figures is in `docs/PulseChain_Technical_Report.pdf`.

## 1. Test environment

| Item | Value |
|---|---|
| Hardware | Apple Silicon Mac (arm64), CPU only, no GPU |
| Operating system | macOS 26.1 |
| Python | 3.9.6 |
| Browsers | Google Chrome 156.0.8078.73; Safari 26.1 |
| Not tested | Windows, Linux, low-end hardware, mobile devices (phone-width window only) |

## 2. Preparing a clean run

```bash
rm -f app/pulsechain.db app/.secret
python3 -m venv venv && source venv/bin/activate
pip install -r app/requirements.txt
cd frontend && npm install && npm run build && cd ..
cd app && uvicorn main:app --reload
```

On the first start the terminal prints "First start: created administrator admin@pulsechain.local". Demo account passwords are listed in `README.md`. If the page says "web interface has not been built yet", `npm run build` did not finish; run it again.

## 3. Testing strategies

| Strategy | Why chosen | Command | Result |
|---|---|---|---|
| Unit tests | Security and scoring logic must be correct in isolation | `python3 -m unittest discover -s tests -v` | 28 of 28 pass, under 1 second |
| Integration (API) tests | Check layers work together, including errors and role limits | `python3 scripts/smoke_test.py` (backend running) | 35 of 35 pass |
| Performance and stress | Requirement: a prediction in under 2 seconds on a laptop | `python3 scripts/perf_test.py` (backend running) | Mean 5.8 ms per prediction; 200 requests from 20 parallel users, 227 requests per second, 0 errors |
| Manual click-through by role | Confirm what each role sees in the interface | Section 4 below | Pass |
| Browser compatibility | Same behaviour in more than one browser and at phone width | Section 5 below | Pass |
| Usability (SUS) | Judge ease of use with real users | Feedback tab, 3 tasks and 10 questions | **No participants yet (n = 0); no score is reported.** Planned as the next testing step |

## 4. Manual test cases by role

| Sign in as | Expected behaviour |
|---|---|
| Administrator | All tabs visible, including Users. Dashboard: Load demo data fills the charts; Simulate live reports adds events. Feedback results visible. |
| Country manager (Rwanda) | Only Rwanda in dropdowns, shipments and dashboard. Users tab lists only Rwanda district officers. Uganda data is not visible. |
| District officer (Gasabo) | Only Gasabo reports. Predicting for another country is blocked (403). No Users tab and no demo tools. |
| District officer (Kampala) | Only Kampala and Uganda data. |

**Registration and approval:** create a district officer account. It is created as pending, sign-in is refused until a manager approves it in the Users tab, and afterwards only that district's data is visible.

**Seven screens:** Predict, Shipments (Why? explanation, log a delay cause), Batch (upload CSV, download results), Report shortage (report, restock, search, delete), Dashboard, Model, Feedback.

## 5. Browser and layout checks

| Check | Chrome 156 | Safari 26.1 |
|---|---|---|
| Sign in, Predict and Dashboard load without errors | Pass | Pass |
| Narrow (phone-width) window: tab bar scrolls sideways, nothing overlaps | Pass | Not checked |

## 6. Invalid and unauthorised inputs

| Input | Expected | Observed |
|---|---|---|
| Wrong password; unapproved account | 401; "waiting for approval" (403) | As expected |
| Request without sign-in | 401 on every data endpoint | As expected |
| District officer asks for another country | 403 or filtered out | As expected |
| Non-admin calls demo tools or the user list | 403 | As expected |
| Unknown country, product or delay reason; survey with 3 answers | 422 with a message | As expected |
| Restock a report twice; delete a missing report | 400; 404 | As expected |
| Model file missing | Labelled heuristic estimate, no crash | Works (unit-tested fallback) |

## 7. Defects found and fixed during testing

- With the model file missing, the fallback path crashed because it looked up a field that does not exist. Fixed by reading history through `RiskModel.history_for` and `country_recent_late_rate`, and covered by a unit test.
- When the frontend had not been built, the server showed an outdated page. It now shows a clear "not built yet" message.
- The Model page still listed "no sign-in" as a limitation after authentication was added. The text was corrected.

## 8. Known gaps

- SUS has no participants yet, so there is no usability score.
- The Dockerfile is written but the image build was not verified.
- Windows, Linux and low-end hardware were not tested.
