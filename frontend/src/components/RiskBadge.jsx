const styles = {
  high: "bg-red-600",
  medium: "bg-amber-500",
  low: "bg-emerald-600",
};

export default function RiskBadge({ band }) {
  return (
    <span className={`inline-block rounded-full px-3 py-1 text-xs font-bold uppercase text-white ${styles[band]}`}>
      {band} risk
    </span>
  );
}
