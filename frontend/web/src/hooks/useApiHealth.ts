import { useEffect, useState, useCallback } from 'react'

interface HealthStatus {
  status: string
  stats?: {
    pending: number
    active: number
    completed: number
    failed: number
    total: number
  }
}

export function useApiHealth(pollInterval = 10000) {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/health')
      if (!response.ok) throw new Error('API unavailable')
      const data = await response.json()
      setHealth(data)
      setError(null)
      setLastUpdated(new Date())
    } catch {
      setError('API offline')
      setHealth(null)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, pollInterval)
    return () => clearInterval(interval)
  }, [fetchHealth, pollInterval])

  return { health, error, lastUpdated, refetch: fetchHealth }
}
