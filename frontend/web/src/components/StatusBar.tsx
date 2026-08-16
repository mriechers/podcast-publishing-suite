import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApiHealth } from '../hooks/useApiHealth'
import { formatRelativeTime } from '../utils/formatTime'

export default function StatusBar() {
  const [showDetails, setShowDetails] = useState(false)
  const { health, error, lastUpdated } = useApiHealth()

  const isHealthy = !error && health?.status === 'ok'
  const stats = health?.stats

  return (
    <div className="bg-gray-900 border-t border-gray-800 text-xs text-gray-400">
      <div className="max-w-[1600px] mx-auto px-6 py-2 flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Health Status */}
          <Link
            to="/system"
            className="flex items-center gap-2 hover:text-gray-200 transition-colors"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isHealthy ? 'bg-green-500' : 'bg-red-500'
              }`}
              aria-label={isHealthy ? 'API healthy' : 'API offline'}
            />
            <span>{isHealthy ? 'Connected' : error || 'Disconnected'}</span>
          </Link>

          {/* Item Count Summary */}
          {stats && (
            <Link
              to="/items"
              className="flex items-center gap-2 hover:text-gray-200 transition-colors"
            >
              <span>
                {stats.total} items ({stats.pending} pending, {stats.active} active,{' '}
                {stats.completed} completed, {stats.failed} failed)
              </span>
            </Link>
          )}

          {/* Toggle Details */}
          {stats && (
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="text-gray-500 hover:text-gray-300 transition-colors"
              aria-expanded={showDetails}
              aria-controls="status-details"
            >
              {showDetails ? '▼' : '▶'} Details
            </button>
          )}
        </div>

        {/* Last Updated */}
        {lastUpdated && (
          <div className="text-gray-500">
            Updated {formatRelativeTime(lastUpdated.toISOString())}
          </div>
        )}
      </div>

      {/* Expandable Details Panel */}
      {showDetails && stats && (
        <div
          id="status-details"
          className="max-w-[1600px] mx-auto px-6 py-3 border-t border-gray-800"
        >
          <div className="grid grid-cols-4 gap-4">
            <div>
              <div className="text-gray-500 mb-1">Pending</div>
              <div className="text-lg font-semibold text-yellow-400">
                {stats.pending}
              </div>
            </div>
            <div>
              <div className="text-gray-500 mb-1">Active</div>
              <div className="text-lg font-semibold text-blue-400">
                {stats.active}
              </div>
            </div>
            <div>
              <div className="text-gray-500 mb-1">Completed</div>
              <div className="text-lg font-semibold text-green-400">
                {stats.completed}
              </div>
            </div>
            <div>
              <div className="text-gray-500 mb-1">Failed</div>
              <div className="text-lg font-semibold text-red-400">
                {stats.failed}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
