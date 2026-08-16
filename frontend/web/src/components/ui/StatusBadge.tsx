import { getStatusBadgeColor } from '../../utils/statusColors'

interface StatusBadgeProps {
  status: string
  size?: 'sm' | 'md'
}

export default function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm'

  return (
    <span
      className={`inline-flex items-center rounded-md font-medium border ${sizeClasses} ${getStatusBadgeColor(
        status
      )}`}
    >
      {status}
    </span>
  )
}
