import { useEffect, useState } from "react";
import { api } from "../api.js";
import Card from "../components/Card.jsx";
import Select from "../components/Select.jsx";
import Button from "../components/Button.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import { inputClass } from "../components/Field.jsx";

export default function ShipmentsPage({ options }) {
  const [country, setCountry] = useState("All countries");
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [logged, setLogged] = useState([]);
  const [reasonOptions, setReasonOptions] = useState([]);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api("/delay-reasons/options").then((list) => {
      setReasonOptions(list);
      setReason(list[0]);
    });
  }, []);

  useEffect(() => {
    const query = country === "All countries" ? "" : `?country=${encodeURIComponent(country)}`;
    api("/shipments" + query).then(setData).catch((e) => setError(e.message));
    setSelected(null);
    setDetail(null);
  }, [country]);

  async function explain(id) {
    setSelected(id);
    setDetail(null);
    setMessage("");
    try {
      const [d, r] = await Promise.all([api(`/shipments/${id}/explain`), api(`/shipments/${id}/delay-reasons`)]);
      setDetail(d);
      setLogged(r);
    } catch (err) {
      setError(err.message);
    }
  }

  async function logReason(e) {
    e.preventDefault();
    try {
      await api(`/shipments/${selected}/delay-reasons`, { method: "POST", body: JSON.stringify({ reason, note }) });
      setNote("");
      setMessage("Delay reason logged.");
      setLogged(await api(`/shipments/${selected}/delay-reasons`));
    } catch (err) {
      setMessage(err.message);
    }
  }

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-slate-500">Scoring shipments...</p>;

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="lg:col-span-3">
        <Card
          title="Recent shipments ranked by risk (held-out test set)"
          action={
            <div className="w-44">
              <Select value={country} onChange={setCountry} items={["All countries", ...options.countries]} />
            </div>
          }
        >
          <p className="mb-4 text-sm text-slate-500">
            These are the {data.total} most recent historical shipments in the dataset (2014 to 2015). The model never saw
            them during training, so this page replays how it would have scored them. Showing the {data.shown} highest-risk.
            "Actual" is what really happened.
          </p>
          <div className="max-h-[620px] overflow-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-3">Vendor</th>
                  <th className="py-2 pr-3">Country</th>
                  <th className="py-2 pr-3">Mode</th>
                  <th className="py-2 pr-3">Risk score</th>
                  <th className="py-2 pr-3">Actual</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {data.shipments.map((s) => (
                  <tr key={s.id} className={`border-b border-slate-100 ${selected === s.id ? "bg-brand-50" : ""}`}>
                    <td className="max-w-[160px] truncate py-2 pr-3 font-medium text-slate-800">{s.vendor}</td>
                    <td className="py-2 pr-3">{s.country}</td>
                    <td className="py-2 pr-3">{s.shipment_mode || "-"}</td>
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-16 overflow-hidden rounded-full bg-slate-200">
                          <div
                            className={s.risk_band === "high" ? "h-full bg-red-500" : s.risk_band === "medium" ? "h-full bg-amber-400" : "h-full bg-emerald-500"}
                            style={{ width: `${Math.min(100, s.probability_late * 100)}%` }}
                          />
                        </div>
                        <span>{(s.probability_late * 100).toFixed(0)}%{s.probability_late >= 0.5 ? "+" : ""}</span>
                      </div>
                    </td>
                    <td className="py-2 pr-3">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          s.actual_late ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {s.actual_late ? "late" : "on time"}
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      <Button small onClick={() => explain(s.id)}>Why?</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <div className="space-y-6 lg:col-span-2">
        <Card title="Why this shipment is flagged">
          {!selected && <p className="text-sm text-slate-500">Press "Why?" on a shipment to see the model's reasons.</p>}
          {selected && !detail && <p className="text-sm text-slate-500">Loading...</p>}
          {detail && (
            <div>
              <RiskBadge band={detail.risk_band} />
              <p className="mt-3 text-xl font-semibold text-slate-900">
                Estimated late chance: {(detail.probability_late * 100).toFixed(0)}%{detail.probability_late >= 0.5 ? "+" : ""}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                {detail.vendor} to {detail.country}. It was actually {detail.actual_late ? "late" : "on time"}.
              </p>
              <p className="mt-3 text-xs font-semibold uppercase text-slate-500">Model risk factors</p>
              <ul className="mt-2 space-y-2">
                {detail.reasons.map((r, i) => (
                  <li key={i} className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                    <span className={r.direction === "raises risk" ? "text-red-600" : "text-emerald-600"}>
                      {r.direction === "raises risk" ? "▲" : "▼"}
                    </span>{" "}
                    {r.plain || r.feature}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate-400">These are patterns the model found, not proven causes of delay.</p>
            </div>
          )}
        </Card>

        {detail && (
          <Card title="Actual cause of delay (logged by staff)">
            {logged.length === 0 && <p className="mb-3 text-sm text-slate-500">No cause logged for this shipment yet.</p>}
            <ul className="mb-4 space-y-2">
              {logged.map((l) => (
                <li key={l.id} className="rounded-lg bg-indigo-50 px-3 py-2 text-sm text-slate-700">
                  <strong>{l.reason}</strong>
                  {l.note && l.note !== "Demo data" && <span className="text-slate-500"> · {l.note}</span>}
                  {l.is_demo ? <span className="ml-2 rounded bg-amber-100 px-1.5 text-xs text-amber-800">demo</span> : null}
                </li>
              ))}
            </ul>
            <form onSubmit={logReason} className="space-y-3">
              <Select value={reason} onChange={setReason} items={reasonOptions} />
              <input className={inputClass} placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
              <Button small>Log delay reason</Button>
              {message && <p className="text-xs text-slate-500">{message}</p>}
            </form>
          </Card>
        )}
      </div>
    </div>
  );
}
