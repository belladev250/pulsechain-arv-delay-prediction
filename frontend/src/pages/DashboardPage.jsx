import { useEffect, useState } from "react";
import { api } from "../api.js";
import Card from "../components/Card.jsx";
import Button from "../components/Button.jsx";

const attentionStyles = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  ok: "bg-emerald-100 text-emerald-700",
};

function Stat({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const load = () => api("/dashboard").then(setData).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  async function seed() {
    await api("/seed", { method: "POST" });
    load();
  }

  if (!data) return <p className="text-slate-500">{error || "Loading..."}</p>;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total reports" value={data.total_reports} />
        <Stat label="Open shortages" value={data.open_shortages} />
        <Stat label="Restocked" value={data.restocked} />
        <Stat label="Avg restock (days)" value={data.avg_restock_days === null ? "-" : data.avg_restock_days} />
      </div>

      <Card title="District bottlenecks" action={<Button small onClick={seed}>Add demo reports</Button>}>
        <p className="mb-4 text-sm text-slate-500">
          Open shortages combined with each country's historical late-delivery rate (overall{" "}
          {(data.overall_late_rate * 100).toFixed(1)}%).
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <th className="py-2 pr-3">District</th>
                <th className="py-2 pr-3">Country</th>
                <th className="py-2 pr-3">Open</th>
                <th className="py-2 pr-3">Restocked</th>
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
                  <td className="py-2 pr-3">
                    <div className="mb-1 h-1.5 w-28 overflow-hidden rounded-full bg-slate-200">
                      <div
                        className="h-full bg-amber-400"
                        style={{ width: `${Math.min(100, d.country_late_rate * 200)}%` }}
                      />
                    </div>
                    {(d.country_late_rate * 100).toFixed(1)}%
                  </td>
                  <td className="py-2">
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${attentionStyles[d.attention]}`}>
                      {d.attention}
                    </span>
                  </td>
                </tr>
              ))}
              {data.districts.length === 0 && (
                <tr>
                  <td colSpan="6" className="py-4 text-slate-500">
                    No reports yet. Use "Add demo reports" or submit a shortage.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
