import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { SkeletonDashboard } from '../components/ui/Skeleton'
import { useItemsWebSocket } from '../hooks/useWebSocket'
import { formatRelativeTime, formatTimestamp } from '../utils/formatTime'
import { getStatusTextColor } from '../utils/statusColors'
import StatCard from '../components/ui/StatCard'

interface ItemStats {
  pending: number
  active: number
  completed: number
  failed: number
  total: number
}

interface RecentItem {
  id: number
  title: string
  description: string
  status: string
  priority: number
  created_at: string
  updated_at: string
}

export default function Home() {
  const [stats, setStats] = useState<ItemStats | null>(null)
  const [recentItems, setRecentItems] = useState<RecentItem[]>([])
  const [loading, setLoading] = useState(true)

  const { isConnected } = useItemsWebSocket({
    onItemUpdate: (item) => {
      setRecentItems((current) => {
        const existingIndex = current.findIndex((i) => i.id === item.id)
        if (existingIndex !== -1) {
          const updated = [...current]
          updated[existingIndex] = item as RecentItem
          return updated
        } else {
          return [item as RecentItem, ...current].slice(0, 5)
        }
      })
    },
    onStatsUpdate: (newStats) => {
      setStats(newStats)
    },
  })

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, itemsRes] = await Promise.all([
        fetch('/api/items/stats'),
        fetch('/api/items?page=1&page_size=5'),
      ])

      if (statsRes.ok) {
        setStats(await statsRes.json())
      }
      if (itemsRes.ok) {
        const data = await itemsRes.json()
        setRecentItems(data.items || [])
      }
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()

    const pollInterval = isConnected ? 30000 : 10000
    const interval = setInterval(fetchData, pollInterval)
    return () => clearInterval(interval)
  }, [fetchData, isConnected])

  if (loading) {
    return <SkeletonDashboard />
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Pending" value={stats?.pending ?? 0} color="text-yellow-400" />
        <StatCard label="Active" value={stats?.active ?? 0} color="text-blue-400" />
        <StatCard label="Completed" value={stats?.completed ?? 0} color="text-green-400" />
        <StatCard label="Failed" value={stats?.failed ?? 0} color="text-red-400" />
      </div>

      {/* Recent Items */}
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
          <h2 className="text-lg font-medium text-white">Recent Items</h2>
          <Link
            to="/items"
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            View all
          </Link>
        </div>
        <div className="divide-y divide-gray-700">
          {recentItems.length === 0 ? (
            <div className="px-4 py-8 text-center text-gray-300">
              No items yet
            </div>
          ) : (
            recentItems.map((item) => (
              <Link
                key={item.id}
                to={`/items/${item.id}`}
                className="block px-4 py-3 hover:bg-gray-750 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-white font-medium">
                      {item.title}
                    </div>
                    <div className="text-sm text-gray-400" title={formatTimestamp(item.created_at)}>
                      {formatRelativeTime(item.created_at)}
                    </div>
                  </div>
                  <span className={`text-sm font-medium ${getStatusTextColor(item.status)}`}>
                    {item.status}
                  </span>
                </div>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
