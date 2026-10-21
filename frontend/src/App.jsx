import { useEffect, useState } from "react";
import { api } from "./api.js";
import PredictPage from "./pages/PredictPage.jsx";
import ReportPage from "./pages/ReportPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import ShipmentsPage from "./pages/ShipmentsPage.jsx";
import ModelPage from "./pages/ModelPage.jsx";
import BatchPage from "./pages/BatchPage.jsx";
import FeedbackPage from "./pages/FeedbackPage.jsx";

const TABS = [
  ["predict", "Predict risk"],
  ["batch", "Batch"],
  ["shipments", "Shipments"],
  ["report", "Report shortage"],
  ["dashboard", "Dashboard"],
  ["model", "Model"],
  ["feedback", "Feedback"],
];

export default function App() {
  const [options, setOptions] = useState(null);
  const [health, setHealth] = useState(null);
  const [tab, setTab] = useState(() => {
    const fromHash = window.location.hash.replace("#", "");
    return TABS.some(([key]) => key === fromHash) ? fromHash : "predict";
  });
  const [loadError, setLoadError] = useState("");

  const changeTab = (key) => {
    setTab(key);
    window.location.hash = key;
  };

  const connect = () => {
    setLoadError("");
    Promise.all([api("/options"), api("/health")])
      .then(([opts, h]) => {
        setOptions(opts);
        setHealth(h);
      })
      .catch(() => setLoadError("Cannot reach the PulseChain API. Make sure the backend is running (uvicorn main:app --reload in the app folder)."));
  };

  useEffect(connect, []);

  if (loadError) {
    return (
      <div className="mx-auto mt-24 max-w-md rounded-xl border border-red-200 bg-white p-6 text-center shadow-sm">
        <p className="text-sm text-red-700">{loadError}</p>
        <button onClick={connect} className="mt-4 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          Retry
        </button>
      </div>
    );
  }
  if (!options) return <p className="mt-24 text-center text-slate-500">Loading PulseChain...</p>;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-brand-900">PulseChain</h1>
            <p className="text-xs text-slate-500">HIV/ARV supply-chain early warning</p>
          </div>
          <nav className="flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1">
            {TABS.map(([key, label]) => (
              <button
                key={key}
                onClick={() => changeTab(key)}
                className={`rounded-md px-4 py-1.5 text-sm font-medium transition ${
                  tab === key ? "bg-white text-brand-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        {health && !health.model_loaded && (
          <div className="mb-6 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Model file not found: predictions use a simple heuristic. Place lgbm_pipeline.joblib in app/models.
          </div>
        )}
        {tab === "predict" && <PredictPage options={options} />}
        {tab === "batch" && <BatchPage />}
        {tab === "shipments" && <ShipmentsPage options={options} />}
        {tab === "report" && <ReportPage options={options} />}
        {tab === "dashboard" && <DashboardPage />}
        {tab === "model" && <ModelPage />}
        {tab === "feedback" && <FeedbackPage />}
      </main>
    </div>
  );
}
