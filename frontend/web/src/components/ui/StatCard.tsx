interface StatCardProps {
  label: string
  value: number | string
  color: string
}

export default function StatCard({ label, value, color }: StatCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
      <div className="text-sm text-gray-300">{label}</div>
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
    </div>
  )
}
