export default function Field({ label, children }) {
  return (
    <label className="mb-3 flex flex-col gap-1 text-sm text-slate-600">
      <span className="font-medium">{label}</span>
      {children}
    </label>
  );
}

export const inputClass =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100";
