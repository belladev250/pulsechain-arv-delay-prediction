import { useEffect, useState } from "react";
import { api } from "../api.js";
import Card from "../components/Card.jsx";
import Button from "../components/Button.jsx";
import { inputClass } from "../components/Field.jsx";

const QUESTIONS = [
  "I think that I would like to use this system frequently.",
  "I found the system unnecessarily complex.",
  "I thought the system was easy to use.",
  "I think that I would need the support of a technical person to be able to use this system.",
  "I found the various functions in this system were well integrated.",
  "I thought there was too much inconsistency in this system.",
  "I would imagine that most people would learn to use this system very quickly.",
  "I found the system very cumbersome to use.",
  "I felt very confident using the system.",
  "I needed to learn a lot of things before I could get going with this system.",
];

function interpret(score) {
  if (score >= 80.3) return "Excellent";
  if (score >= 68) return "Good (above the usual average of 68)";
  if (score >= 51) return "OK, below average";
  return "Poor";
}

export default function FeedbackPage({ user }) {
  const isAdmin = user.role === "admin";
  const [answers, setAnswers] = useState(Array(10).fill(0));
  const [comment, setComment] = useState("");
  const [message, setMessage] = useState("");
  const [summary, setSummary] = useState(null);

  const load = () => (isAdmin ? api("/feedback/summary").then(setSummary).catch(() => {}) : Promise.resolve());
  useEffect(() => {
    load();
  }, []);

  async function submit(e) {
    e.preventDefault();
    if (answers.some((a) => a === 0)) {
      setMessage("Please answer all 10 questions.");
      return;
    }
    try {
      const res = await api("/feedback", { method: "POST", body: JSON.stringify({ answers, comment }) });
      setMessage(`Thank you. Your SUS score is ${res.sus_score}.`);
      setAnswers(Array(10).fill(0));
      setComment("");
      load();
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="lg:col-span-3">
        <Card title="Usability survey (System Usability Scale)">
          <p className="mb-4 text-sm text-slate-500">
            After trying the app, rate each statement from 1 (strongly disagree) to 5 (strongly agree).
          </p>
          <form onSubmit={submit} className="space-y-4">
            {QUESTIONS.map((q, i) => (
              <div key={i} className="rounded-lg bg-slate-50 p-3">
                <p className="mb-2 text-sm text-slate-800">{i + 1}. {q}</p>
                <div className="flex gap-4">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <label key={n} className="flex items-center gap-1 text-sm text-slate-600">
                      <input
                        type="radio"
                        name={`q${i}`}
                        checked={answers[i] === n}
                        onChange={() => setAnswers(answers.map((a, idx) => (idx === i ? n : a)))}
                      />
                      {n}
                    </label>
                  ))}
                </div>
              </div>
            ))}
            <textarea
              className={inputClass}
              rows="3"
              placeholder="Comments or suggestions (optional)"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
            <Button>Submit feedback</Button>
            {message && <p className="text-sm text-slate-600">{message}</p>}
          </form>
        </Card>
      </div>

      {isAdmin && (
      <div className="lg:col-span-2">
        <Card title="Results so far">
          {!summary && <p className="text-sm text-slate-500">Loading...</p>}
          {summary && summary.responses === 0 && <p className="text-sm text-slate-500">No responses yet.</p>}
          {summary && summary.responses > 0 && (
            <div>
              <p className="text-4xl font-semibold text-slate-900">{summary.mean_sus}</p>
              <p className="text-sm text-slate-500">
                Average SUS score from {summary.responses} {summary.responses === 1 ? "response" : "responses"} (0 to 100)
              </p>
              <p className="mt-2 text-sm font-medium text-brand-700">{interpret(summary.mean_sus)}</p>
              <p className="mt-1 text-xs text-slate-400">Range: {summary.min} to {summary.max}</p>
              {summary.comments.length > 0 && (
                <div className="mt-4">
                  <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Comments</p>
                  <ul className="space-y-2">
                    {summary.comments.map((c, i) => (
                      <li key={i} className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
      )}
    </div>
  );
}
