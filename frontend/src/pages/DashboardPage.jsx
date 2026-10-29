import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import Card from "../components/Card.jsx";
import Button from "../components/Button.jsx";
import {
  BandValidationChart, CountryChart, DelayReasonsChart, RiskDistributionChart, StatusChart, TimelineChart,
} from "../components/Charts.jsx";

const REFRESH_MS = 5000;

const attentionStyles = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  ok: "bg-emerald-100 text-emerald-700",
};

function Stat({ label, value, hint }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}

function timeAgo(iso) {
  const seconds = Math.max(0, (Date.now() - new Date(iso + "Z").getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  return `${Math.floor(seconds / 86400)} d ago`;
}

export default function DashboardPage({ user }) {
  const isAdmin = user.role === "admin";
  const [data, setData] = useState(null);
  const [charts, setCharts] = useState(null);
  const [error, setError] = useState("");
  const [live, setLive] = useState(true);
  const [updated, setUpdated] = useState(null);
  const [busy, setBusy] = useState(false);
  const [simulate, setSimulate] = useState(false);
  const [lastEvent, setLastEvent] = useState("");

  const load = useCallback(async () => {
    try {
      const [summary, analytics] = await Promise.all([api("/dashboard"), api("/analytics")]);
      setData(summary);
      setCharts(analytics);
      setUpdated(new Date());
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!live) return undefined;
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [live, load]);

  useEffect(() => {
    if (!simulate) return undefined;
    const tick = async () => {
      try {
        const res = await api("/simulate/tick", { method: "POST" });
        setLastEvent(res.events.join(" · "));
        await load();
      } catch (err) {
        setError(err.message);
      }
    };
    tick();
    const timer = setInterval(tick, 3000);
    return () => clearInterval(timer);
  }, [simulate, load]);

  async function seed() {
    setBusy(true);
    try {
      await api("/seed", { method: "POST" });
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (!data || !charts) return <p className="text-slate-500">{error || "Loading..."}</p>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Operations dashboard</h2>
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${live ? "animate-pulse bg-emerald-500" : "bg-slate-400"}`} />
            {live ? "Live" : "Paused"}
            {updated && <span>· updated {updated.toLocaleTimeString()}</span>}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setLive(!live)}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            {live ? "Pause updates" : "Resume updates"}
          </button>
          {isAdmin && (
            <>
          <button
            onClick={() => setSimulate(!simulate)}
            className={`rounded-lg border px-4 py-2 text-sm ${
              simulate ? "border-emerald-600 bg-emerald-50 text-emerald-700" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
            }`}
          >
            {simulate ? "Stop simulation" : "Simulate live reports"}
          </button>
          <Button small disabled={busy} onClick={seed}>{busy ? "Loading..." : "Load demo data"}</Button>
            </>
          )}
        </div>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {(charts.demo_reports > 0 || charts.demo_delay_reasons > 0) && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>Demo data:</strong> {charts.demo_reports} of {charts.total_reports} shortage reports and{" "}
          {charts.demo_delay_reasons} logged delay causes are simulated sample data, not real facility records. Shipment
          predictions use real SCMS history.
          {simulate && lastEvent && <span className="ml-2 text-amber-700">Latest: {lastEvent}</span>}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total reports" value={data.total_reports} />
        <Stat label="Open shortages" value={data.open_shortages} hint="Awaiting restock" />
        <Stat label="Restocked" value={data.restocked} />
        <Stat label="Avg restock time" value={data.avg_restock_days === null ? "-" : `${data.avg_restock_days} d`} hint="Report to restock" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Shortage reports over time (14 days)"><TimelineChart data={charts.timeline} /></Card>
        <Card title="Shortages by country"><CountryChart data={charts.by_country} /></Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Report status"><StatusChart data={charts.status} /></Card>
        <Card title="Predicted risk distribution"><RiskDistributionChart data={charts.risk_distribution} /></Card>
        <Card title="Model check: actual late rate by risk band">
          <BandValidationChart data={charts.band_validation} baseline={charts.baseline_late_rate} />
        </Card>
      </div>

      <Card title="Logged causes of delay (late shipments)">
        {charts.delay_reasons.length === 0 ? (
          <p className="text-sm text-slate-500">
            No causes logged yet. On the Shipments page, open a late shipment and log why it was delayed.
          </p>
        ) : (
          <DelayReasonsChart data={charts.delay_reasons} />
        )}
      </Card>

      <Card title="District bottlenecks">
        <p className="mb-4 text-sm text-slate-500">
          Open shortages combined with the model's predicted delay risk for shipments to each country (average
          predicted risk {data.overall_predicted_risk === null ? "n/a" : (data.overall_predicted_risk * 100).toFixed(1) + "%"}).
          A district is flagged high when it has at least 2 open shortages and its country's predicted risk is at least 15% above average.
          The shipment data records the destination country, not the district, so districts inherit their country's
          shipment risk. Risk is computed on the held-out shipments.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <th className="py-2 pr-3">District</th>
                <th className="py-2 pr-3">Country</th>
                <th className="py-2 pr-3">Open</th>
                <th className="py-2 pr-3">Restocked</th>
                <th className="py-2 pr-3">Predicted risk</th>
                <th className="py-2 pr-3">High-risk shipments</th>
                <th className="py-2 pr-3">Historical late rate</th>
                <th className="py-2">Attention</th>
              </tr>
            </thead>
            <tbody>
              {data.districts.map((d, i) => (
                <tr key={i} className="border-b border-slate-100">
                  <td className="py-2 pr-3 font-medium text-slate-800">{d.district}</td>
                  <td className="py-2 pr-3">{d.country}</td>
                  <td className="py-2 pr-3">{d.open}</td>
                  <td className="py-2 pr-3">{d.restocked}</td>
                  <td className="py-2 pr-3">{d.predicted_risk === null ? "-" : (d.predicted_risk * 100).toFixed(1) + "%"}</td>
                  <td className="py-2 pr-3">{d.high_risk_shipments} of {d.shipments_scored}</td>
                  <td className="py-2 pr-3">{(d.country_late_rate * 100).toFixed(1)}%</td>
                  <td className="py-2">
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${attentionStyles[d.attention]}`}>
                      {d.attention}
                    </span>
                  </td>
                </tr>
              ))}
              {data.districts.length === 0 && (
                <tr>
                  <td colSpan="8" className="py-4 text-slate-500">
                    No reports yet. Use "Load demo data" or submit a shortage.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Recent activity">
        <ul className="divide-y divide-slate-100">
          {charts.recent.map((r) => (
            <li key={r.id} className="flex items-center justify-between py-2 text-sm">
              <span>
                <span className="font-medium text-slate-800">{r.facility}</span>{" "}
                <span className="text-slate-500">({r.district}, {r.country}) · {r.product_group}</span>
              </span>
              <span className="flex items-center gap-3">
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${r.status === "shortage" ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>
                  {r.status}
                </span>
                <span className="text-xs text-slate-400">{timeAgo(r.reported_at)}</span>
              </span>
            </li>
          ))}
          {charts.recent.length === 0 && <li className="py-2 text-sm text-slate-500">No activity yet.</li>}
        </ul>
      </Card>
    </div>
  );
}
