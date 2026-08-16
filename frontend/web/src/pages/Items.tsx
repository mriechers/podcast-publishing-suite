import { useEffect, useState, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { useToast } from '../components/ui/Toast'
import { SkeletonQueue } from '../components/ui/Skeleton'
import { useDebounce } from '../hooks/useDebounce'
import { useItemsWebSocket } from '../hooks/useWebSocket'
import { formatRelativeTime, formatTimestamp } from '../utils/formatTime'
import StatusBadge from '../components/ui/StatusBadge'
import EmptyState from '../components/ui/EmptyState'

interface Item {
  id: number
  title: string
  description: string
  status: string
  priority: number
  created_at: string
  updated_at: string
}

interface PaginatedResponse {
  items: Item[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

interface ItemStats {
  pending: number
  active: number
  completed: number
  failed: number
  total: number
}

export default function Items() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [items, setItems] = useState<Item[]>([])
  const [filter, setFilter] = useState<string>('all')
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<ItemStats | null>(null)

  // Pagination and search state
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [searchInput, setSearchInput] = useState(searchParams.get('search') || '')
  const debouncedSearch = useDebounce(searchInput, 300)
  const PAGE_SIZE = 20

  // Dialog state
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean
    title: string
    message: string
    onConfirm: () => void
    variant?: 'danger' | 'warning' | 'info'
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
  })

  const { toast } = useToast()

  // WebSocket connection for real-time updates
  const { isConnected } = useItemsWebSocket({
    onItemUpdate: (item, eventType) => {
      setItems((current) => {
        const existingIndex = current.findIndex((i) => i.id === item.id)

        if (eventType === 'item_deleted') {
          return current.filter((i) => i.id !== item.id)
        }

        if (existingIndex !== -1) {
          const updated = [...current]
          updated[existingIndex] = item as Item
          return updated
        } else if (filter === 'all' || filter === item.status) {
          return [item as Item, ...current]
        }

        return current
      })
    },
    onStatsUpdate: (newStats) => {
      setStats(newStats)
    },
  })

  const handleDelete = (itemId: number) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Item',
      message: 'Are you sure you want to delete this item? This action cannot be undone.',
      variant: 'danger',
      onConfirm: async () => {
        try {
          const response = await fetch(`/api/items/${itemId}`, { method: 'DELETE' })
          if (response.ok) {
            toast('Item deleted successfully', 'success')
            fetchItems()
          } else {
            toast('Failed to delete item', 'error')
          }
        } catch (err) {
          console.error('Failed to delete item:', err)
          toast('Failed to delete item', 'error')
        }
        setConfirmDialog((prev) => ({ ...prev, isOpen: false }))
      },
    })
  }

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch('/api/items/stats')
      if (response.ok) {
        setStats(await response.json())
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err)
    }
  }, [])

  const fetchItems = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: PAGE_SIZE.toString(),
      })

      if (filter !== 'all') {
        params.set('status', filter)
      }

      if (debouncedSearch) {
        params.set('search', debouncedSearch)
      }

      const response = await fetch(`/api/items?${params}`)
      if (response.ok) {
        const data: PaginatedResponse = await response.json()
        setItems(data.items || [])
        setTotal(data.total)
        setTotalPages(data.total_pages)
      }
    } catch (err) {
      console.error('Failed to fetch items:', err)
    } finally {
      setLoading(false)
    }
  }, [filter, page, debouncedSearch])

  useEffect(() => {
    fetchItems()
    fetchStats()

    const pollInterval = isConnected ? 30000 : 5000
    const interval = setInterval(() => {
      fetchStats()
      if (!isConnected) {
        fetchItems()
      }
    }, pollInterval)

    return () => clearInterval(interval)
  }, [fetchItems, fetchStats, isConnected])

  // Update URL when search changes
  useEffect(() => {
    const params = new URLSearchParams(searchParams)
    if (debouncedSearch) {
      params.set('search', debouncedSearch)
    } else {
      params.delete('search')
    }
    setSearchParams(params, { replace: true })
  }, [debouncedSearch, setSearchParams, searchParams])

  // Reset to first page when search changes
  useEffect(() => {
    if (debouncedSearch !== searchParams.get('search')) {
      setPage(1)
    }
  }, [debouncedSearch, searchParams])

  const clearSearch = () => {
    setSearchInput('')
    setPage(1)
  }

  const handleFilterChange = (newFilter: string) => {
    setFilter(newFilter)
    setPage(1)
  }

  return (
    <div className="space-y-6">
      {/* Header with Title, Search, and Count */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Items</h1>
          <span className="text-gray-400 text-sm">
            {total} item{total !== 1 ? 's' : ''}
            {filter !== 'all' && ` (${filter})`}
            {debouncedSearch && ` matching "${debouncedSearch}"`}
          </span>
        </div>

        {/* Search */}
        <div className="relative">
          <label htmlFor="items-search" className="sr-only">Search items</label>
          <input
            id="items-search"
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search items..."
            className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 w-64 pr-8"
            aria-describedby="items-search-desc"
          />
          {searchInput && (
            <button
              type="button"
              onClick={clearSearch}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
              aria-label="Clear search"
            >
              &#10005;
            </button>
          )}
          <span id="items-search-desc" className="sr-only">
            Search filters automatically as you type. Results appear after you stop typing for 300ms.
          </span>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center space-x-1 bg-gray-800 rounded-lg p-1 w-fit">
        {['all', 'pending', 'active', 'completed', 'failed'].map((status) => {
          const count = stats
            ? status === 'all'
              ? stats.total
              : stats[status as keyof ItemStats]
            : null

          return (
            <button
              key={status}
              onClick={() => handleFilterChange(status)}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors flex items-center space-x-1.5 ${
                filter === status
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <span className="capitalize">{status}</span>
              {count !== null && (
                <span
                  className={`px-1.5 py-0.5 text-xs rounded-full ${
                    filter === status
                      ? 'bg-gray-600 text-gray-200'
                      : 'bg-gray-700 text-gray-400'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Items Table */}
      {loading ? (
        <SkeletonQueue />
      ) : (
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          {items.length === 0 ? (
            <EmptyState
              title="No items found"
              description={debouncedSearch ? `No results for "${debouncedSearch}"` : 'Create your first item to get started.'}
            />
          ) : (
            <table className="w-full">
              <thead className="bg-gray-850 border-b border-gray-700">
                <tr className="text-left text-sm text-gray-300">
                  <th className="px-4 py-3 font-medium">ID</th>
                  <th className="px-4 py-3 font-medium">Title</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Priority</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {items.map((item) => (
                  <tr
                    key={item.id}
                    className="hover:bg-gray-750 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <Link
                        to={`/items/${item.id}`}
                        className="text-blue-400 hover:text-blue-300"
                      >
                        #{item.id}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-medium text-white">
                      {item.title}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="px-4 py-3 text-gray-300 text-sm">
                      {item.priority}
                    </td>
                    <td
                      className="px-4 py-3 text-gray-300 text-sm"
                      title={formatTimestamp(item.created_at)}
                    >
                      {formatRelativeTime(item.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center space-x-2">
                        <Link
                          to={`/items/${item.id}`}
                          className="text-xs text-gray-300 hover:text-white"
                        >
                          View
                        </Link>
                        <button
                          onClick={() => handleDelete(item.id)}
                          className="text-xs text-red-400 hover:text-red-300"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center space-x-4 py-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-700 transition-colors"
          >
            &larr; Previous
          </button>
          <span className="text-gray-400">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-700 transition-colors"
          >
            Next &rarr;
          </button>
        </div>
      )}

      {/* Confirm Dialog */}
      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        onConfirm={confirmDialog.onConfirm}
        onCancel={() => setConfirmDialog((prev) => ({ ...prev, isOpen: false }))}
        title={confirmDialog.title}
        message={confirmDialog.message}
        variant={confirmDialog.variant}
        confirmText="Confirm"
        cancelText="Cancel"
      />
    </div>
  )
}
