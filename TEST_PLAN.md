# PulseChain: final test plan (about 20 minutes)

Run these in order. Stop at the first failure and send me the exact error text or a screenshot.

## 1. Fresh start (so the demo accounts are created)
```bash
cd pulsechain_ml_auth
rm -f app/pulsechain.db app/.secret
python3 -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r app/requirements.txt
cd frontend && npm install && npm run build && cd ..
cd app && uvicorn main:app --reload
```
Expect: "First start: created administrator admin@pulsechain.local" in the terminal, and http://127.0.0.1:8000 shows the sign-in page.
If it shows "PulseChain backend is running ... not built yet", the `npm run build` step did not finish; run it again and refresh.

## 2. Automatic API check (second terminal, backend still running)
```bash
cd pulsechain_ml_auth
python3 scripts/smoke_test.py
```
Expect: `N of N checks passed` with no FAIL lines.

## 3. Click-through by role
| Sign in as | Check |
|---|---|
| admin@pulsechain.local / Admin#2026 | All tabs visible, including Users. Dashboard > Load demo data fills charts. Simulate live reports adds events. Feedback results visible. |
| rwanda.manager@pulsechain.local / Demo#2026 | Only Rwanda in dropdowns, shipments and dashboard. Users tab lists only Rwanda district officers. Cannot see Uganda data. |
| gasabo@pulsechain.local / Demo#2026 | Only Gasabo reports. Predict with another country is blocked. No Users tab, no demo tools. |
| kampala@pulsechain.local / Demo#2026 | Only Kampala/Uganda data. |

## 4. Registration and approval
1. Sign out, click Register, create a district officer (e.g. Rwanda, Kicukiro). It says the account is pending.
2. Try to sign in: it is refused (waiting for approval).
3. Sign in as rwanda.manager, open Users, approve it.
4. Sign in as the new user: only Kicukiro data is visible.

## 5. The seven screens (as the usability participants will see them)
Predict, Shipments (click Why?, log a delay cause), Batch (upload a CSV and download results), Report shortage (report, restock, search, delete), Dashboard (charts load, no errors), Model (metrics and limitations), Feedback (submit the 10 answers).

## 6. Before the usability sessions
- Delete test survey answers: `sqlite3 app/pulsechain.db "DELETE FROM feedback;"`
- Dashboard: Stop simulation, then Load demo data to reset to the starting state.
- Decide which account participants use (gasabo@pulsechain.local is the pre-created demo account).
