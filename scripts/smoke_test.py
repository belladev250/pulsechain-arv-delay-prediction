import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@pulsechain.local"
ADMIN_PASSWORD = "Admin#2026"
results = []
TOKEN = None


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token or TOKEN:
        headers["Authorization"] = "Bearer " + (token or TOKEN)
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode() or "{}")


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))


status, anon = call("GET", "/api/reports")
check("reports need sign-in (401)", status == 401)
status, login = call("POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
check("admin sign-in", status == 200 and "token" in login, str(login)[:150])
TOKEN = login.get("token")
status, bad = call("POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": "wrong-password"})
check("wrong password rejected (401)", status == 401)

status, health = call("GET", "/api/health")
check("health endpoint", status == 200 and health.get("status") == "ok")
check("model loaded", health.get("model_loaded") is True, "model file not loaded, using fallback")

status, options = call("GET", "/api/options")
check("options endpoint", status == 200 and len(options.get("vendors", [])) > 0)

shipment = {"vendor": "SCMS from RDC", "country": "Burundi", "shipment_mode": "Truck", "inco_term": "N/A - From RDC",
            "fulfill_via": "From RDC", "product_group": "ARV", "quantity": 5000, "value": 50000}
status, pred = call("POST", "/api/predict", shipment)
check("single prediction", status == 200 and 0 <= pred.get("probability_late", -1) <= 1, str(pred)[:200])
check("prediction has reasons", len(pred.get("reasons", [])) > 0, "SHAP reasons empty")

status, batch = call("POST", "/api/predict/batch", {"shipments": [shipment, shipment]})
check("batch prediction", status == 200 and batch.get("count") == 2, str(batch)[:200])

status, ships = call("GET", "/api/shipments?limit=5")
check("ranked shipments", status == 200 and len(ships.get("shipments", [])) == 5, str(ships)[:200])
if status == 200 and ships["shipments"]:
    sid = ships["shipments"][0]["id"]
    status, detail = call("GET", f"/api/shipments/{sid}/explain")
    check("shipment explanation", status == 200 and len(detail.get("reasons", [])) > 0, str(detail)[:200])

status, reasons = call("GET", "/api/delay-reasons/options")
check("delay reason options", status == 200 and len(reasons) >= 5)
if ships.get("shipments"):
    status, bad_reason = call("POST", f"/api/shipments/{ships['shipments'][0]['id']}/delay-reasons", {"reason": "Not a reason"})
    check("invalid delay reason rejected", status == 422, str(bad_reason)[:120])
    status, logged = call("GET", f"/api/shipments/{ships['shipments'][0]['id']}/delay-reasons")
    check("list delay reasons", status == 200 and isinstance(logged, list))

status, bad_feedback = call("POST", "/api/feedback", {"answers": [1, 2, 3], "comment": ""})
check("invalid feedback rejected", status == 422)
status, fb = call("GET", "/api/feedback/summary")
check("feedback summary", status == 200 and "responses" in fb)

status, bad_report = call("POST", "/api/reports", {"facility": "X", "district": "Y", "country": "Mars", "product_group": "ARV"})
check("invalid report rejected", status == 422)

status, info = call("GET", "/api/model-info")
check("model info", status == 200 and len(info.get("models", [])) >= 2)

status, seeded = call("POST", "/api/seed")
check("seed demo data", status == 200 and seeded.get("seeded", 0) > 0)

status, tick = call("POST", "/api/simulate/tick")
check("simulate live report", status == 200 and len(tick.get("events", [])) >= 1, str(tick))

status, created = call("POST", "/api/reports", {"facility": "Smoke Test Clinic", "district": "Gasabo",
                                                "country": "Rwanda", "product_group": "ARV", "note": "smoke"})
check("create report", status == 201 and "id" in created, str(created))
rid = created.get("id")
if rid:
    status, done = call("PATCH", f"/api/reports/{rid}/restock")
    check("restock report", status == 200 and done.get("status") == "restocked", str(done))
    status, again = call("PATCH", f"/api/reports/{rid}/restock")
    check("double restock rejected", status == 400)
    status, gone = call("DELETE", f"/api/reports/{rid}")
    check("delete report", status == 200, str(gone))
    status, gone = call("DELETE", f"/api/reports/{rid}")
    check("delete missing report returns 404", status == 404)

status, dash = call("GET", "/api/dashboard")
check("dashboard summary", status == 200 and dash.get("total_reports", 0) > 0, str(dash)[:200])
status, an = call("GET", "/api/analytics")
check("analytics charts data", status == 200 and len(an.get("timeline", [])) == 14, str(an)[:200])
check("risk bands present", len(an.get("band_validation", [])) == 3)
check("delay reasons in analytics", len(an.get("delay_reasons", [])) > 0, "run Load demo data first")

# role scoping (uses the demo accounts created on first start)
status, gas = call("POST", "/api/auth/login", {"email": "gasabo@pulsechain.local", "password": "Demo#2026"})
if status == 200:
    gtoken = gas["token"]
    status, mine = call("GET", "/api/reports", token=gtoken)
    check("district officer sees only own district", status == 200 and len(mine) > 0 and all(
        r["district"] == "Gasabo" and r["country"] == "Rwanda" for r in mine), str(mine)[:150])
    status, ships_g = call("GET", "/api/shipments?limit=40", token=gtoken)
    check("district officer sees only own country's shipments", status == 200 and all(
        x["country"] == "Rwanda" for x in ships_g.get("shipments", [])))
    status, other = call("POST", "/api/predict", {**shipment, "country": "Uganda"}, token=gtoken)
    check("other country prediction blocked (403)", status == 403)
    status, denied = call("POST", "/api/seed", token=gtoken)
    check("demo tools are admin only (403)", status == 403)
    status, denied = call("GET", "/api/users", token=gtoken)
    check("user list blocked for district officer (403)", status == 403)
    status, an_g = call("GET", "/api/analytics", token=gtoken)
    check("analytics scoped to own country", status == 200 and [c["country"] for c in an_g["by_country"]] == ["Rwanda"])
else:
    check("demo accounts available", False, "start with a fresh database to create the demo accounts")

print(f"\n{sum(results)} of {len(results)} checks passed")
sys.exit(0 if all(results) else 1)
