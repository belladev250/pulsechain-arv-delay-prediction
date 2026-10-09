import { useEffect, useState } from "react";
import { api } from "../api.js";
import Card from "../components/Card.jsx";
import Field, { inputClass } from "../components/Field.jsx";
import Select from "../components/Select.jsx";
import Button from "../components/Button.jsx";

export default function ReportPage({ options }) {
  const [form, setForm] = useState({ facility: "", district: "", country: "Rwanda", product_group: "ARV", note: "" });
  const [reports, setReports] = useState([]);
  const [message, setMessage] = useState("");

  const load = () => api("/reports").then(setReports).catch((e) => setMessage(e.message));
  useEffect(() => {
    load();
  }, []);

  const set = (key) => (value) => setForm({ ...form, [key]: value });

  async function submit(e) {
    e.preventDefault();
    try {
      await api("/reports", { method: "POST", body: JSON.stringify(form) });
      setMessage("Shortage reported.");
      setForm({ ...form, facility: "", district: "", note: "" });
      load();
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function restock(id) {
    try {
      await api(`/reports/${id}/restock`, { method: "PATCH" });
      setMessage("Marked as restocked.");
      load();
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <Card title="Report a shortage">
          <form onSubmit={submit}>
            <Field label="Facility name">
              <input required className={inputClass} value={form.facility} onChange={(e) => set("facility")(e.target.value)} />
            </Field>
            <Field label="District">
              <input required className={inputClass} value={form.district} onChange={(e) => set("district")(e.target.value)} />
            </Field>
            <Field label="Country"><Select value={form.country} onChange={set("country")} items={options.countries} /></Field>
            <Field label="Product"><Select value={form.product_group} onChange={set("product_group")} items={options.product_groups} /></Field>
            <Field label="Note (optional)">
              <input className={inputClass} value={form.note} onChange={(e) => set("note")(e.target.value)} />
            </Field>
            <Button>Submit report</Button>
            {message && <p className="mt-3 text-sm text-slate-600">{message}</p>}
          </form>
        </Card>
      </div>

      <div className="lg:col-span-3">
        <Card title="Reports">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-3">Facility</th>
                  <th className="py-2 pr-3">District</th>
                  <th className="py-2 pr-3">Product</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100">
                    <td className="py-2 pr-3 font-medium text-slate-800">{r.facility}</td>
                    <td className="py-2 pr-3">{r.district}, {r.country}</td>
                    <td className="py-2 pr-3">{r.product_group}</td>
                    <td className="py-2 pr-3">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          r.status === "shortage" ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      {r.status === "shortage" && (
                        <Button small onClick={() => restock(r.id)}>Mark restocked</Button>
                      )}
                    </td>
                  </tr>
                ))}
                {reports.length === 0 && (
                  <tr>
                    <td colSpan="5" className="py-4 text-slate-500">No reports yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
