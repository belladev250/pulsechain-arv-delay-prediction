import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const GRID = "#e2e8f0";
const AXIS = { fontSize: 12, fill: "#64748b" };

export function TimelineChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="gReported" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.35} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gRestocked" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#10b981" stopOpacity={0.35} />
            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
        <XAxis dataKey="date" tick={AXIS} tickLine={false} />
        <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip />
        <Legend />
        <Area type="monotone" dataKey="reported" name="Shortages reported" stroke="#ef4444" strokeWidth={2} fill="url(#gReported)" />
        <Area type="monotone" dataKey="restocked" name="Restocked" stroke="#10b981" strokeWidth={2} fill="url(#gRestocked)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function CountryChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="country" tick={AXIS} tickLine={false} interval={0} />
        <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip />
        <Legend />
        <Bar dataKey="open" name="Open" stackId="a" fill="#ef4444" />
        <Bar dataKey="restocked" name="Restocked" stackId="a" fill="#10b981" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

const STATUS_COLORS = ["#ef4444", "#10b981"];

export function StatusChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3}>
          {data.map((entry, i) => (
            <Cell key={entry.name} fill={STATUS_COLORS[i % STATUS_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function RiskDistributionChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="range" tick={{ ...AXIS, fontSize: 10 }} tickLine={false} interval={0} />
        <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip />
        <Bar dataKey="shipments" name="Shipments" fill="#059669" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

const BAND_COLORS = { Low: "#10b981", Medium: "#f59e0b", High: "#ef4444" };

export function BandValidationChart({ data, baseline }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="band" tick={{ ...AXIS, fontSize: 11 }} tickLine={false} />
        <YAxis unit="%" tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip formatter={(value) => `${value}%`} />
        {baseline !== null && (
          <ReferenceLine y={baseline} stroke="#64748b" strokeDasharray="4 4" label={{ value: `Overall ${baseline}%`, fontSize: 11, fill: "#64748b", position: "insideTopLeft" }} />
        )}
        <Bar dataKey="late_rate" name="Actually late" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.band} fill={BAND_COLORS[entry.band.split(" ")[0]] || "#64748b"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function DelayReasonsChart({ data }) {
  const rows = data.map((d) => ({ ...d, label: d.reason.length > 34 ? d.reason.slice(0, 32) + "..." : d.reason }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(220, rows.length * 42)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
        <XAxis type="number" allowDecimals={false} tick={AXIS} tickLine={false} />
        <YAxis type="category" dataKey="label" width={220} tick={{ ...AXIS, fontSize: 11 }} tickLine={false} axisLine={false} />
        <Tooltip />
        <Bar dataKey="count" name="Late shipments" fill="#6366f1" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
