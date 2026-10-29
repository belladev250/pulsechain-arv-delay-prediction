import { useCallback, useEffect, useState } from "react";
import { api, clearToken, getToken } from "./api.js";
import AuthPage from "./pages/AuthPage.jsx";
import PredictPage from "./pages/PredictPage.jsx";
import ReportPage from "./pages/ReportPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import ShipmentsPage from "./pages/ShipmentsPage.jsx";
import ModelPage from "./pages/ModelPage.jsx";
import BatchPage from "./pages/BatchPage.jsx";
import FeedbackPage from "./pages/FeedbackPage.jsx";
import UsersPage from "./pages/UsersPage.jsx";

const ALL_TABS = [
  ["predict", "Predict risk"],
  ["batch", "Batch"],
  ["shipments", "Shipments"],
  ["report", "Report shortage"],
  ["dashboard", "Dashboard"],
  ["model", "Model"],
  ["feedback", "Feedback"],
  ["users", "Users"],
];

const ROLE_LABEL = { admin: "Administrator", country: "Country manager", district: "District officer" };

function scopeText(user) {
  if (user.role === "admin") return "All countries";
  if (user.role === "country") return user.country;
  return `${user.district}, ${user.country}`;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(Boolean(getToken()));

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  useEffect(() => {
    if (!getToken()) return;
    api("/auth/me")
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => {
    window.addEventListener("pulsechain-logout", logout);
    return () => window.removeEventListener("pulsechain-logout", logout);
  }, [logout]);

  if (checking) return <p className="mt-24 text-center text-slate-500">Loading PulseChain...</p>;
  if (!user) return <AuthPage onLogin={setUser} />;
  return <Shell user={user} onLogout={logout} />;
}

function Shell({ user, onLogout }) {
  const tabs = ALL_TABS.filter(([key]) => key !== "users" || user.role !== "district");
  const [options, setOptions] = useState(null);
  const [health, setHealth] = useState(null);
  const [tab, setTab] = useState(() => {
    const fromHash = window.location.hash.replace("#", "");
    return tabs.some(([key]) => key === fromHash) ? fromHash : "predict";
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
        <div className="mx-auto max-w-6xl px-4">
          <div className="flex items-center justify-between gap-3 py-3">
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-brand-900">PulseChain</h1>
              <p className="hidden text-xs text-slate-500 sm:block">HIV/ARV supply-chain early warning</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden text-right text-xs leading-tight sm:block">
                <p className="font-semibold text-slate-800">{user.name}</p>
                <p className="text-slate-500">{ROLE_LABEL[user.role]} · {scopeText(user)}</p>
              </div>
              <button
                onClick={onLogout}
                className="shrink-0 rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
              >
                Sign out
              </button>
            </div>
          </div>
          <p className="pb-2 text-xs text-slate-500 sm:hidden">
            {user.name} · {ROLE_LABEL[user.role]} · {scopeText(user)}
          </p>
          <nav className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-3">
            {tabs.map(([key, label]) => (
              <button
                key={key}
                onClick={() => changeTab(key)}
                className={`shrink-0 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  tab === key ? "bg-brand-600 text-white shadow-sm" : "bg-slate-100 text-slate-600 hover:text-slate-900"
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
            Model file not found: predictions use a simple heuristic. Place model_pipeline.joblib in app/models.
          </div>
        )}
        {tab === "predict" && <PredictPage options={options} />}
        {tab === "batch" && <BatchPage />}
        {tab === "shipments" && <ShipmentsPage options={options} />}
        {tab === "report" && <ReportPage options={options} user={user} />}
        {tab === "dashboard" && <DashboardPage user={user} />}
        {tab === "model" && <ModelPage />}
        {tab === "feedback" && <FeedbackPage user={user} />}
        {tab === "users" && user.role !== "district" && <UsersPage user={user} />}
      </main>
    </div>
  );
}
