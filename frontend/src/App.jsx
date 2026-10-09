import { useEffect, useState } from "react";
import { api } from "./api.js";
import PredictPage from "./pages/PredictPage.jsx";
import ReportPage from "./pages/ReportPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";

const TABS = [
  ["predict", "Predict risk"],
  ["report", "Report shortage"],
  ["dashboard", "Dashboard"],
];

export default function App() {
  const [options, setOptions] = useState(null);
  const [health, setHealth] = useState(null);
  const [tab, setTab] = useState("predict");

  useEffect(() => {
    api("/options").then(setOptions);
    api("/health").then(setHealth);
  }, []);

  if (!options) return <p className="mt-24 text-center text-slate-500">Loading PulseChain...</p>;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-brand-900">PulseChain</h1>
            <p className="text-xs text-slate-500">HIV/ARV supply-chain early warning</p>
          </div>
          <nav className="flex gap-1 rounded-lg bg-slate-100 p-1">
            {TABS.map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
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
        {tab === "report" && <ReportPage options={options} />}
        {tab === "dashboard" && <DashboardPage />}
      </main>
    </div>
  );
}
