/**
 * Status color utilities for consistent item status styling across components.
 *
 * Two variants are provided:
 * - getStatusTextColor: Simple text color for compact displays
 * - getStatusBadgeColor: Full badge styling with background, text, and border
 */

export type ItemStatus =
  | 'pending'
  | 'active'
  | 'completed'
  | 'failed'
  | 'paused'
  | 'cancelled'

/**
 * Get simple text color class for a item status.
 * Use this for compact status displays where only text color is needed.
 *
 * @example
 * <span className={getStatusTextColor(item.status)}>{item.status}</span>
 */
export function getStatusTextColor(status: string): string {
  switch (status) {
    case 'pending':
      return 'text-yellow-400'
    case 'active':
      return 'text-blue-400'
    case 'completed':
      return 'text-green-400'
    case 'failed':
      return 'text-red-400'
    case 'paused':
      return 'text-orange-400'
    case 'cancelled':
      return 'text-gray-400'
    default:
      return 'text-gray-400'
  }
}

/**
 * Get full badge styling classes for a item status.
 * Includes background, text color, and border for badge/pill displays.
 *
 * @example
 * <span className={`px-2 py-0.5 rounded-md text-xs border ${getStatusBadgeColor(item.status)}`}>
 *   {item.status}
 * </span>
 */
export function getStatusBadgeColor(status: string): string {
  switch (status) {
    case 'pending':
      return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
    case 'active':
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
    case 'completed':
      return 'bg-green-500/20 text-green-400 border-green-500/30'
    case 'failed':
      return 'bg-red-500/20 text-red-400 border-red-500/30'
    case 'paused':
      return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
    case 'cancelled':
      return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    default:
      return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
  }
}
