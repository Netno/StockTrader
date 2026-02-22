interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean | null;
}

export default function StatCard({ label, value, sub, positive }: StatCardProps) {
  const color =
    positive === true ? "text-green-400" : positive === false ? "text-red-400" : "text-white";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}
