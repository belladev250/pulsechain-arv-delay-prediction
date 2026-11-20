import { useEffect, useState } from "react";
import { api, setToken } from "../api.js";
import Field, { inputClass } from "../components/Field.jsx";
import Select from "../components/Select.jsx";
import Button from "../components/Button.jsx";
import { PolicyText } from "./PrivacyPage.jsx";

export default function AuthPage({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [countries, setCountries] = useState(["Rwanda"]);
  const [form, setForm] = useState({ name: "", email: "", password: "", country: "Rwanda", district: "", consent: false });
  const [showPolicy, setShowPolicy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/auth/countries").then((d) => setCountries(d.countries)).catch(() => {});
  }, []);

  const set = (key) => (value) => setForm({ ...form, [key]: value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    setMessage("");
    setBusy(true);
    try {
      if (mode === "login") {
        const res = await api("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: form.email, password: form.password }),
        });
        setToken(res.token);
        onLogin(res.user);
      } else {
        const res = await api("/auth/register", { method: "POST", body: JSON.stringify(form) });
        setMessage(res.message);
        setMode("login");
        setForm({ ...form, password: "", consent: false });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-md px-4">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold text-brand-900">PulseChain</h1>
        <p className="text-sm text-slate-500">HIV/ARV supply-chain early warning</p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex rounded-lg bg-slate-100 p-1 text-sm font-medium">
          {[["login", "Sign in"], ["register", "Create account"]].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => { setMode(key); setError(""); setMessage(""); }}
              className={`flex-1 rounded-md py-1.5 transition ${mode === key ? "bg-white text-brand-700 shadow-sm" : "text-slate-600"}`}
            >
              {label}
            </button>
          ))}
        </div>
        <form onSubmit={submit}>
          {mode === "register" && (
            <Field label="Full name">
              <input required className={inputClass} value={form.name} onChange={(e) => set("name")(e.target.value)} />
            </Field>
          )}
          <Field label="Email">
            <input required type="email" autoComplete="username" className={inputClass} value={form.email} onChange={(e) => set("email")(e.target.value)} />
          </Field>
          <Field label="Password">
            <input
              required
              type="password"
              minLength={mode === "register" ? 8 : undefined}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className={inputClass}
              value={form.password}
              onChange={(e) => set("password")(e.target.value)}
            />
          </Field>
          {mode === "register" && (
            <>
              <Field label="Country"><Select value={form.country} onChange={set("country")} items={countries} /></Field>
              <Field label="District">
                <input required className={inputClass} value={form.district} onChange={(e) => set("district")(e.target.value)} />
              </Field>
              <p className="mb-3 text-xs text-slate-500">
                You will see only your own district's data. A manager must approve your account before you can sign in.
              </p>
              <label className="mb-3 flex items-start gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  required
                  className="mt-0.5"
                  checked={form.consent}
                  onChange={(e) => set("consent")(e.target.checked)}
                />
                <span>
                  I have read the{" "}
                  <button type="button" onClick={() => setShowPolicy(true)} className="text-brand-700 underline">
                    Privacy Policy
                  </button>{" "}
                  and I agree that PulseChain stores my name, email and location for this study.
                </span>
              </label>
            </>
          )}
          <Button disabled={busy}>{busy ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}</Button>
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          {message && <p className="mt-3 text-sm text-emerald-700">{message}</p>}
        </form>
      </div>
      <p className="mt-4 text-center text-xs text-slate-500">
        <button type="button" onClick={() => setShowPolicy(true)} className="underline">Privacy Policy</button>
      </p>
      {showPolicy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[85vh] w-full max-w-xl overflow-y-auto rounded-xl bg-white p-6 shadow-lg">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900">Privacy Policy</h2>
              <button onClick={() => setShowPolicy(false)} className="text-sm text-slate-500 hover:text-slate-800">Close</button>
            </div>
            <PolicyText />
          </div>
        </div>
      )}
    </div>
  );
}
