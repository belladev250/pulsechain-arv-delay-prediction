import { useState } from "react";
import { api } from "../api.js";
import Card from "../components/Card.jsx";
import Button from "../components/Button.jsx";
import { download, parseCSV, toCSV } from "../csv.js";

const COLUMNS = [
  "vendor", "country", "shipment_mode", "inco_term", "fulfill_via", "product_group",
  "quantity", "value", "planned_lead_time_days", "weight_kg",
];

const SAMPLE = [
  COLUMNS,
  ["SCMS from RDC", "Burundi", "Truck", "N/A - From RDC", "From RDC", "ARV", 5000, 50000, "", ""],
  ["Orgenics, Ltd", "Uganda", "Air", "EXW", "Direct Drop", "HRDT", 1200, 18000, 90, 600],
  ["Aurobindo Pharma Limited", "Rwanda", "Air", "EXW", "Direct Drop", "ARV", 20000, 120000, 120, 2500],
];

const bandStyles = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-emerald-100 text-emerald-700",
};

function toShipment(header, cells) {
  const get = (name) => (cells[header.indexOf(name)] || "").trim();
  const optional = (name) => (get(name) === "" ? null : Number(get(name)));
  return {
    vendor: get("vendor"),
    country: get("country"),
    shipment_mode: get("shipment_mode"),
    inco_term: get("inco_term"),
    fulfill_via: get("fulfill_via"),
    product_group: get("product_group"),
    quantity: get("quantity") === "" ? 1000 : Number(get("quantity")),
    value: get("value") === "" ? 10000 : Number(get("value")),
    planned_lead_time_days: optional("planned_lead_time_days"),
    weight_kg: optional("weight_kg"),
  };
}

export default function BatchPage() {
  const [fileName, setFileName] = useState("");
  const [shipments, setShipments] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function onFile(e) {
    const file = e.target.files[0];
    if (!file) return;
    setFileName(file.name);
    setResult(null);
    setError("");
    const reader = new FileReader();
    reader.onload = () => {
      const rows = parseCSV(String(reader.result));
      if (rows.length < 2) {
        setError("The file needs a header row and at least one shipment.");
        setShipments([]);
        return;
      }
      const header = rows[0].map((h) => h.trim());
      const missing = COLUMNS.slice(0, 6).filter((c) => !header.includes(c));
      if (missing.length) {
        setError("Missing columns: " + missing.join(", "));
        setShipments([]);
        return;
      }
      setShipments(rows.slice(1).map((cells) => toShipment(header, cells)));
    };
    reader.readAsText(file);
  }

  async function run() {
    setLoading(true);
    setError("");
    try {
      setResult(await api("/predict/batch", { method: "POST", body: JSON.stringify({ shipments }) }));
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }

  function downloadResults() {
    const rows = [["row", "vendor", "country", "shipment_mode", "probability_late", "risk_band"]];
    result.results.forEach((r) => rows.push([r.row, r.vendor, r.country, r.shipment_mode, r.probability_late, r.risk_band]));
    download("pulsechain_predictions.csv", toCSV(rows));
  }

  return (
    <div className="space-y-6">
      <Card title="Batch prediction">
        <p className="mb-4 text-sm text-slate-500">
          Upload a CSV of shipments and score all of them at once. Required columns: vendor, country, shipment_mode,
          inco_term, fulfill_via, product_group. Optional: quantity, value, planned_lead_time_days, weight_kg.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input type="file" accept=".csv" onChange={onFile} className="text-sm" />
          <button
            onClick={() => download("pulsechain_template.csv", toCSV(SAMPLE))}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            Download sample CSV
          </button>
          <Button disabled={loading || shipments.length === 0} onClick={run}>
            {loading ? "Scoring..." : `Score ${shipments.length || ""} shipments`}
          </Button>
        </div>
        {fileName && <p className="mt-2 text-xs text-slate-500">{fileName}: {shipments.length} shipments read</p>}
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </Card>

      {result && (
        <Card
          title={`Results: ${result.high} of ${result.count} flagged high risk`}
          action={<Button small onClick={downloadResults}>Download results CSV</Button>}
        >
          <p className="mb-3 text-xs text-slate-500">Source: {result.source}</p>
          <div className="max-h-[480px] overflow-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-3">#</th>
                  <th className="py-2 pr-3">Vendor</th>
                  <th className="py-2 pr-3">Country</th>
                  <th className="py-2 pr-3">Mode</th>
                  <th className="py-2 pr-3">Risk score</th>
                  <th className="py-2">Risk</th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((r) => (
                  <tr key={r.row} className="border-b border-slate-100">
                    <td className="py-2 pr-3 text-slate-400">{r.row}</td>
                    <td className="py-2 pr-3 font-medium text-slate-800">{r.vendor}</td>
                    <td className="py-2 pr-3">{r.country}</td>
                    <td className="py-2 pr-3">{r.shipment_mode}</td>
                    <td className="py-2 pr-3">{(r.probability_late * 100).toFixed(1)}%{r.probability_late >= 0.5 ? "+" : ""}</td>
                    <td className="py-2">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${bandStyles[r.risk_band]}`}>{r.risk_band}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
