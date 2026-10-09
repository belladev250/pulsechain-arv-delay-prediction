import { useState } from "react";
import { api } from "../api.js";
import Card from "../components/Card.jsx";
import Field, { inputClass } from "../components/Field.jsx";
import Select from "../components/Select.jsx";
import Button from "../components/Button.jsx";

const bandStyles = {
  high: { badge: "bg-red-600", fill: "bg-red-500" },
  medium: { badge: "bg-amber-500", fill: "bg-amber-400" },
  low: { badge: "bg-emerald-600", fill: "bg-emerald-500" },
};

export default function PredictPage({ options }) {
  const [form, setForm] = useState({
    vendor: options.vendors[0],
    country: "Rwanda",
    shipment_mode: "Air",
    inco_term: "N/A - From RDC",
    fulfill_via: "From RDC",
    product_group: "ARV",
    quantity: 5000,
    value: 50000,
    planned_lead_time_days: "",
    weight_kg: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (key) => (value) => setForm({ ...form, [key]: value });
  const toNumber = (v) => (v === "" ? null : Number(v));

  async function submit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const body = {
        ...form,
        quantity: Number(form.quantity),
        value: Number(form.value),
        planned_lead_time_days: toNumber(form.planned_lead_time_days),
        weight_kg: toNumber(form.weight_kg),
      };
      setResult(await api("/predict", { method: "POST", body: JSON.stringify(body) }));
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }

  const style = result ? bandStyles[result.risk_band] : null;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card title="Shipment details">
        <form onSubmit={submit}>
          <div className="grid gap-x-4 sm:grid-cols-2">
            <Field label="Vendor"><Select value={form.vendor} onChange={set("vendor")} items={options.vendors} /></Field>
            <Field label="Destination country"><Select value={form.country} onChange={set("country")} items={options.countries} /></Field>
            <Field label="Shipment mode"><Select value={form.shipment_mode} onChange={set("shipment_mode")} items={options.shipment_modes} /></Field>
            <Field label="Vendor INCO term"><Select value={form.inco_term} onChange={set("inco_term")} items={options.inco_terms} /></Field>
            <Field label="Fulfilled via"><Select value={form.fulfill_via} onChange={set("fulfill_via")} items={options.fulfill_via} /></Field>
            <Field label="Product group"><Select value={form.product_group} onChange={set("product_group")} items={options.product_groups} /></Field>
            <Field label="Quantity">
              <input type="number" className={inputClass} value={form.quantity} onChange={(e) => set("quantity")(e.target.value)} />
            </Field>
            <Field label="Line item value (USD)">
              <input type="number" className={inputClass} value={form.value} onChange={(e) => set("value")(e.target.value)} />
            </Field>
            <Field label="Planned lead time, days (optional)">
              <input type="number" className={inputClass} value={form.planned_lead_time_days} onChange={(e) => set("planned_lead_time_days")(e.target.value)} />
            </Field>
            <Field label="Weight in kg (optional)">
              <input type="number" className={inputClass} value={form.weight_kg} onChange={(e) => set("weight_kg")(e.target.value)} />
            </Field>
          </div>
          <Button disabled={loading}>{loading ? "Predicting..." : "Predict delay risk"}</Button>
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        </form>
      </Card>

      <Card title="Risk assessment">
        {!result && <p className="text-sm text-slate-500">Fill in the shipment details and press Predict.</p>}
        {result && (
          <div>
            <span className={`inline-block rounded-full px-3 py-1 text-xs font-bold text-white ${style.badge}`}>
              {result.risk_band.toUpperCase()} RISK
            </span>
            <p className="mt-3 text-2xl font-semibold text-slate-900">
              {(result.probability_late * 100).toFixed(1)}% chance of late delivery
            </p>
            <div className="mt-3 h-3 w-full overflow-hidden rounded-full bg-slate-200">
              <div className={`h-full ${style.fill}`} style={{ width: `${result.probability_late * 100}%` }} />
            </div>
            <p className="mt-2 text-xs text-slate-500">Source: {result.source}</p>

            <h3 className="mb-2 mt-6 text-sm font-semibold text-slate-900">Why this score</h3>
            <ul className="space-y-2">
              {result.reasons.map((r, i) => (
                <li key={i} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                  <span className="font-medium text-slate-800">{r.feature}</span>
                  <span className={r.direction === "raises risk" ? "text-red-600" : "text-emerald-600"}>
                    {r.direction}
                  </span>
                </li>
              ))}
              {result.reasons.length === 0 && <li className="text-sm text-slate-500">No explanation available.</li>}
            </ul>

            {result.vendor_history && (
              <p className="mt-4 text-xs text-slate-500">
                Vendor history: {(result.vendor_history.late_rate * 100).toFixed(1)}% late across{" "}
                {result.vendor_history.count} shipments.
              </p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
