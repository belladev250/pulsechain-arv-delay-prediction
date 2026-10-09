export default function Button({ children, small = false, ...props }) {
  const size = small ? "px-3 py-1.5 text-xs" : "px-5 py-2.5 text-sm";
  return (
    <button
      {...props}
      className={`rounded-lg bg-brand-600 font-medium text-white transition hover:bg-brand-700 disabled:opacity-60 ${size}`}
    >
      {children}
    </button>
  );
}
