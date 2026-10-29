import { useEffect, useState } from "react";
import { api } from "../api.js";
import Card from "../components/Card.jsx";
import Button from "../components/Button.jsx";
import { inputClass } from "../components/Field.jsx";

const ROLE_LABEL = { admin: "Administrator", country: "Country manager", district: "District officer" };

export default function UsersPage({ user }) {
  const [users, setUsers] = useState([]);
  const [message, setMessage] = useState("");
  const isAdmin = user.role === "admin";

  const load = () => api("/users").then(setUsers).catch((e) => setMessage(e.message));
  useEffect(() => {
    load();
  }, []);

  async function update(id, body, note) {
    try {
      await api(`/users/${id}`, { method: "PATCH", body: JSON.stringify(body) });
      setMessage(note);
      load();
    } catch (err) {
      setMessage(err.message);
    }
  }

  const pending = users.filter((u) => !u.approved);

  return (
    <div className="space-y-6">
      <Card title="Who can see what">
        <ul className="space-y-1 text-sm text-slate-600">
          <li><strong>District officer:</strong> reports, dashboard and shipments for their own district and country only.</li>
          <li><strong>Country manager:</strong> everything in their own country, and approves district officers there.</li>
          <li><strong>Administrator:</strong> all countries, user roles and demo tools.</li>
        </ul>
      </Card>

      {pending.length > 0 && (
        <Card title={`Waiting for approval (${pending.length})`}>
          <ul className="divide-y divide-slate-100 text-sm">
            {pending.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>
                  <strong className="text-slate-800">{u.name}</strong> ({u.email}), {u.district}, {u.country}
                </span>
                <Button small onClick={() => update(u.id, { approved: true }, `Approved ${u.name}.`)}>Approve</Button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title={`Users (${users.length})`}>
        {message && <p className="mb-3 text-sm text-slate-600">{message}</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <th className="py-2 pr-3">Name</th>
                <th className="py-2 pr-3">Email</th>
                <th className="py-2 pr-3">Role</th>
                <th className="py-2 pr-3">Scope</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-slate-100">
                  <td className="py-2 pr-3 font-medium text-slate-800">{u.name}</td>
                  <td className="py-2 pr-3">{u.email}</td>
                  <td className="py-2 pr-3">
                    {isAdmin && u.id !== user.id ? (
                      <select
                        className={inputClass + " max-w-[11rem]"}
                        value={u.role}
                        onChange={(e) => update(u.id, { role: e.target.value }, `Role changed for ${u.name}.`)}
                      >
                        {Object.entries(ROLE_LABEL).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                      </select>
                    ) : ROLE_LABEL[u.role]}
                  </td>
                  <td className="py-2 pr-3">{u.role === "admin" ? "All countries" : u.role === "country" ? u.country : `${u.district}, ${u.country}`}</td>
                  <td className="py-2 pr-3">
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${u.approved ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-800"}`}>
                      {u.approved ? "active" : "pending"}
                    </span>
                  </td>
                  <td className="whitespace-nowrap py-2 text-right">
                    {u.id !== user.id && u.approved === 1 && (
                      <button
                        onClick={() => update(u.id, { approved: false }, `${u.name} deactivated.`)}
                        className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {isAdmin && (
          <p className="mt-3 text-xs text-slate-400">
            A new account starts as a district officer in the country and district chosen at registration. Change the role here to promote someone to country manager (they keep their country).
          </p>
        )}
      </Card>
    </div>
  );
}
