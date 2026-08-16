import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Breadcrumb from '../components/ui/Breadcrumb'
import { useToast } from '../components/ui/Toast'
import { Skeleton, SkeletonCard } from '../components/ui/Skeleton'
import StatusBadge from '../components/ui/StatusBadge'
import { formatRelativeTime, formatTimestamp, formatDuration } from '../utils/formatTime'

interface ItemDetail {
  id: number
  title: string
  description: string
  status: string
  priority: number
  created_at: string
  updated_at: string
}

export default function ItemDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [item, setItem] = useState<ItemDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { toast } = useToast()

  useEffect(() => {
    const fetchItem = async () => {
      try {
        const response = await fetch(`/api/items/${id}`)
        if (!response.ok) {
          throw new Error('Item not found')
        }
        setItem(await response.json())
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load item')
      } finally {
        setLoading(false)
      }
    }

    fetchItem()

    // Auto-refresh while item is active
    const interval = setInterval(() => {
      if (item?.status === 'active' || item?.status === 'pending') {
        fetchItem()
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [id, item?.status])

  const handleStatusChange = async (newStatus: string) => {
    try {
      const response = await fetch(`/api/items/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      })
      if (response.ok) {
        const updated = await response.json()
        setItem(updated)
        toast(`Status changed to ${newStatus}`, 'success')
      } else {
        toast('Failed to update status', 'error')
      }
    } catch (err) {
      console.error('Failed to update item:', err)
      toast('Failed to update status', 'error')
    }
  }

  const handleDelete = async () => {
    try {
      const response = await fetch(`/api/items/${id}`, { method: 'DELETE' })
      if (response.ok) {
        toast('Item deleted', 'success')
        navigate('/items')
      } else {
        toast('Failed to delete item', 'error')
      }
    } catch (err) {
      console.error('Failed to delete item:', err)
      toast('Failed to delete item', 'error')
    }
  }

  if (loading) {
    return (
      <div className="space-y-6" aria-label="Loading item details" role="status">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
        <span className="sr-only">Loading item details...</span>
      </div>
    )
  }

  if (error || !item) {
    return (
      <div className="text-center py-12">
        <div role="alert" aria-live="assertive" className="text-red-400 mb-4">
          {error || 'Item not found'}
        </div>
        <button
          onClick={() => navigate(-1)}
          className="text-blue-400 hover:text-blue-300"
        >
          Go back
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Breadcrumb
        items={[
          { label: 'Home', href: '/' },
          { label: 'Items', href: '/items' },
          { label: `Item #${item.id}` },
        ]}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="text-sm text-gray-400 hover:text-white mb-2 inline-block transition-colors"
            aria-label="Go back to previous page"
          >
            &larr; Back
          </button>
          <h1 className="text-2xl font-bold text-white">{item.title}</h1>
          <p className="text-gray-400">Item #{item.id}</p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2">
          {item.status === 'pending' && (
            <button
              onClick={() => handleStatusChange('active')}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-md text-sm transition-colors"
            >
              Start
            </button>
          )}
          {item.status === 'active' && (
            <button
              onClick={() => handleStatusChange('completed')}
              className="px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white rounded-md text-sm transition-colors"
            >
              Complete
            </button>
          )}
          {item.status === 'failed' && (
            <button
              onClick={() => handleStatusChange('pending')}
              className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-white rounded-md text-sm transition-colors"
            >
              Retry
            </button>
          )}
          <button
            onClick={handleDelete}
            className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-md text-sm transition-colors"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Info Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <InfoCard label="Status">
          <StatusBadge status={item.status} />
        </InfoCard>
        <InfoCard label="Priority" value={String(item.priority)} />
        <InfoCard
          label="Created"
          value={formatRelativeTime(item.created_at)}
          title={formatTimestamp(item.created_at)}
        />
        <InfoCard
          label="Updated"
          value={formatRelativeTime(item.updated_at)}
          title={formatTimestamp(item.updated_at)}
        />
      </div>

      {/* Description */}
      {item.description && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <h2 className="text-lg font-medium text-white mb-3">Description</h2>
          <p className="text-gray-300 whitespace-pre-wrap">{item.description}</p>
        </div>
      )}

      {/* Timeline */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <h2 className="text-lg font-medium text-white mb-4">Timeline</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-400">Created:</span>
            <span className="ml-2 text-white" title={formatTimestamp(item.created_at)}>
              {formatRelativeTime(item.created_at)}
            </span>
          </div>
          <div>
            <span className="text-gray-400">Last Updated:</span>
            <span className="ml-2 text-white" title={formatTimestamp(item.updated_at)}>
              {formatRelativeTime(item.updated_at)}
            </span>
          </div>
          <div>
            <span className="text-gray-400">Age:</span>
            <span className="ml-2 text-white">
              {formatDuration(item.created_at)}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function InfoCard({
  label,
  value,
  title,
  children,
}: {
  label: string
  value?: string
  title?: string
  children?: React.ReactNode
}) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-3">
      <div className="text-xs text-gray-400 uppercase tracking-wide">{label}</div>
      <div className="mt-1" title={title}>
        {children || <span className="text-lg font-medium text-white">{value}</span>}
      </div>
    </div>
  )
}
