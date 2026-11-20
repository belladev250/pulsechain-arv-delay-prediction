import { useState } from "react";
import { api } from "../api.js";
import Card from "../components/Card.jsx";
import Button from "../components/Button.jsx";
import { inputClass } from "../components/Field.jsx";

// Plain-language privacy policy. Every statement here matches what the code does.
export const POLICY_UPDATED = "November 2026";

export function PolicyText() {
  return (
    <div className="space-y-4 text-sm leading-relaxed text-slate-700">
      <p>
        PulseChain is a capstone research prototype (African Leadership University). It is not yet a live health service.
        This page explains, in plain language, what data it keeps and why. Last updated: {POLICY_UPDATED}.
      </p>

      <section>
        <h3 className="font-semibold text-slate-900">1. What we collect</h3>
        <ul className="list-disc pl-5">
          <li><b>Account data:</b> your name, email, country, district, and the date and time you accepted this policy.</li>
          <li><b>Your password</b> is never stored. We keep only a salted PBKDF2-SHA256 hash, which cannot be turned back into the password.</li>
          <li><b>Shortage reports:</b> facility, district, country, product group and an optional note. A report is not linked to your account.</li>
          <li><b>Usability feedback:</b> ten rating answers and an optional comment. It is anonymous and not linked to your account.</li>
          <li>We do <b>not</b> collect patient names, patient records or any health information about a person. Please never type patient details into a note.</li>
        </ul>
      </section>

      <section>
        <h3 className="font-semibold text-slate-900">2. Why we collect it</h3>
        <p>To sign you in, to show you only your own country or district (your role decides what you see), and to test whether the tool is useful for the capstone study. We collect only what is needed for these purposes.</p>
      </section>

      <section>
        <h3 className="font-semibold text-slate-900">3. Who can see it</h3>
        <p>
          A district officer sees only their own district. A country manager sees their country and the district officers in it.
          The administrator sees all accounts. The server checks this on every request. We do not sell your data or share it with advertisers.
        </p>
      </section>

      <section>
        <h3 className="font-semibold text-slate-900">4. How it is protected</h3>
        <p>
          Passwords are hashed with a random salt. Sign-in tokens are signed and expire after 12 hours. Five wrong passwords lock an email for one minute.
          This prototype runs on a laptop-grade server with a SQLite database; it has not had an independent security audit.
        </p>
      </section>

      <section>
        <h3 className="font-semibold text-slate-900">5. How long we keep it</h3>
        <p>Account data is kept while your account exists. Shortage reports and anonymous feedback are kept for the length of the study.</p>
      </section>

      <section>
        <h3 className="font-semibold text-slate-900">6. Your rights</h3>
        <ul className="list-disc pl-5">
          <li><b>Consent is voluntary.</b> You must accept this policy to create an account.</li>
          <li><b>Delete your data:</b> sign in, open the Privacy tab and use "Delete my account". Your name, email, password hash and location are removed at once.</li>
          <li><b>Withdraw consent:</b> deleting your account withdraws it.</li>
          <li><b>Correct or see your data:</b> your name, email and location are shown in the top bar. Ask the administrator to correct them.</li>
        </ul>
      </section>

      <section>
        <h3 className="font-semibold text-slate-900">7. Limits you should know about</h3>
        <p>
          Deleting your account does not delete shortage reports or anonymous feedback you submitted, because they are not linked to you and cannot be traced back.
          The dashboard in this prototype also shows clearly labelled simulated demo reports.
        </p>
      </section>
    </div>
  );
}

export default function PrivacyPage({ user, onDeleted }) {
  const [password, setPassword] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isAdmin = user.role === "admin";

  async function deleteAccount(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api("/auth/me", { method: "DELETE", body: JSON.stringify({ password }) });
      onDeleted();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card title="Privacy Policy">
        <PolicyText />
      </Card>
      <Card title="Your data">
        <p className="mb-3 text-sm text-slate-600">
          Signed in as <b>{user.name}</b> ({user.email}). Deleting your account removes your name, email, password hash and location.
        </p>
        {isAdmin ? (
          <p className="text-sm text-slate-500">The administrator account cannot be deleted from the app.</p>
        ) : !confirming ? (
          <button
            onClick={() => setConfirming(true)}
            className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
          >
            Delete my account
          </button>
        ) : (
          <form onSubmit={deleteAccount} className="max-w-sm space-y-3">
            <p className="text-sm text-red-700">This cannot be undone. Enter your password to confirm.</p>
            <input
              required
              type="password"
              autoComplete="current-password"
              className={inputClass}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button disabled={busy}>{busy ? "Deleting..." : "Permanently delete my account"}</Button>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </form>
        )}
      </Card>
    </div>
  );
}
