"""PulseChain API entry point: builds the app, creates the database and mounts the routers and the web interface."""
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import DIST
from database import init_db
from routers import admin, auth_routes, dashboard, feedback, predictions, reports, shipments
from services.users import bootstrap_users

app = FastAPI(title="PulseChain API", version="0.1.0",
              description="Shipment delay-risk prediction and shortage reporting for HIV/ARV supply chains.")

init_db()
bootstrap_users()

for module in (auth_routes, predictions, shipments, reports, dashboard, feedback, admin):
    app.include_router(module.router)

app.mount("/assets", StaticFiles(directory=DIST / "assets", check_dir=False), name="assets")

NOT_BUILT = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>PulseChain</title></head>
<body style="font-family:system-ui,sans-serif;max-width:640px;margin:60px auto;padding:0 20px;color:#1e293b">
<h2>PulseChain backend is running</h2>
<p>The web interface has not been built yet. Do one of these:</p>
<ul>
<li><b>Development:</b> in a second terminal run <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run dev</code> and open
<a href="http://localhost:5173">http://localhost:5173</a>.</li>
<li><b>Single server:</b> run <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>, then refresh this page.</li>
</ul>
<p>API documentation: <a href="/docs">/docs</a></p></body></html>"""


@app.get("/")
def index():
    index_file = DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(NOT_BUILT)
