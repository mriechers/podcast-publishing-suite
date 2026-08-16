import { useEffect, useState } from 'react'

interface HealthStatus {
  status: string
  stats?: {
    pending: number
    active: number
    completed: number
    failed: number
  }
}

interface ConnectionLog {
  timestamp: Date
  success: boolean
  error?: string
  latency?: number
}

export default function System() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const [logs, setLogs] = useState<ConnectionLog[]>([])

  const checkConnection = async () => {
    setChecking(true)
    const start = Date.now()

    try {
      const response = await fetch('/api/health')
      const latency = Date.now() - start

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      setHealth(data)
      setError(null)
      setLogs((prev) => [
        { timestamp: new Date(), success: true, latency },
        ...prev.slice(0, 9),
      ])
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMsg)
      setHealth(null)
      setLogs((prev) => [
        { timestamp: new Date(), success: false, error: errorMsg },
        ...prev.slice(0, 9),
      ])
    } finally {
      setChecking(false)
    }
  }

  useEffect(() => {
    checkConnection()
  }, [])

  const isConnected = health !== null && error === null

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">System Status</h1>

      {/* Connection Status Card */}
      <div
        role={isConnected ? 'status' : 'alert'}
        aria-live={isConnected ? 'polite' : 'assertive'}
        className={`rounded-lg border p-6 ${
          isConnected
            ? 'bg-green-900/20 border-green-500/30'
            : 'bg-red-900/20 border-red-500/30'
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div
              className={`w-4 h-4 rounded-full ${
                isConnected ? 'bg-green-500' : 'bg-red-500 animate-pulse'
              }`}
            />
            <div>
              <h2
                className={`text-xl font-semibold ${
                  isConnected ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {isConnected ? 'API Connected' : 'API Offline'}
              </h2>
              <p className="text-sm text-gray-400">
                {isConnected
                  ? 'Backend server is responding normally'
                  : error || 'Unable to reach the API server'}
              </p>
            </div>
          </div>
          <button
            onClick={checkConnection}
            disabled={checking}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white rounded-md text-sm transition-colors"
          >
            {checking ? 'Checking...' : 'Check Now'}
          </button>
        </div>
      </div>

      {/* Troubleshooting - Show when offline */}
      {!isConnected && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Troubleshooting</h2>

          <div className="space-y-4">
            <div className="flex items-start space-x-3">
              <span className="text-yellow-400 font-mono">1.</span>
              <div>
                <p className="text-white font-medium">Check if the API server is running</p>
                <p className="text-sm text-gray-400 mt-1">
                  The API should be running on port 8000:
                </p>
                <pre className="mt-2 bg-gray-900 rounded p-3 text-sm text-green-400 font-mono overflow-x-auto">
                  lsof -i :8000
                </pre>
              </div>
            </div>

            <div className="flex items-start space-x-3">
              <span className="text-yellow-400 font-mono">2.</span>
              <div>
                <p className="text-white font-medium">Start the API server</p>
                <pre className="mt-2 bg-gray-900 rounded p-3 text-sm text-green-400 font-mono overflow-x-auto">
                  uvicorn api.main:app --reload --port 8000
                </pre>
              </div>
            </div>

            <div className="flex items-start space-x-3">
              <span className="text-yellow-400 font-mono">3.</span>
              <div>
                <p className="text-white font-medium">Install dependencies</p>
                <pre className="mt-2 bg-gray-900 rounded p-3 text-sm text-green-400 font-mono overflow-x-auto">
                  pip install -r requirements.txt
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* System Info - Show when connected */}
      {isConnected && health?.stats && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">
            Item Statistics
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <InfoRow label="Pending" value={String(health.stats.pending)} />
            <InfoRow label="Active" value={String(health.stats.active)} />
            <InfoRow label="Completed" value={String(health.stats.completed)} />
            <InfoRow label="Failed" value={String(health.stats.failed)} />
          </div>
        </div>
      )}

      {/* Connection Log */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">
          Connection Log
        </h3>
        {logs.length === 0 ? (
          <p className="text-gray-500 text-sm">No connection attempts yet</p>
        ) : (
          <div className="space-y-1">
            {logs.map((log, i) => (
              <div key={i} className="flex items-center space-x-3 text-sm font-mono">
                <span className="text-gray-600">
                  {log.timestamp.toLocaleTimeString()}
                </span>
                <span className={log.success ? 'text-green-400' : 'text-red-400'}>
                  {log.success ? 'OK' : 'FAIL'}
                </span>
                {log.latency && <span className="text-gray-500">{log.latency}ms</span>}
                {log.error && (
                  <span className="text-red-400 truncate">{log.error}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* API Endpoints Reference */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">
          API Endpoints
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm font-mono">
          <div className="text-gray-400">
            <span className="text-blue-400">GET</span> /api/health
          </div>
          <div className="text-gray-400">
            <span className="text-blue-400">GET</span> /api/items
          </div>
          <div className="text-gray-400">
            <span className="text-blue-400">GET</span> /api/items/stats
          </div>
          <div className="text-gray-400">
            <span className="text-blue-400">GET</span> /api/items/:id
          </div>
          <div className="text-gray-400">
            <span className="text-green-400">POST</span> /api/items
          </div>
          <div className="text-gray-400">
            <span className="text-yellow-400">PATCH</span> /api/items/:id
          </div>
          <div className="text-gray-400">
            <span className="text-red-400">DELETE</span> /api/items/:id
          </div>
          <div className="text-gray-400">
            <span className="text-purple-400">WS</span> /api/ws/updates
          </div>
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-400">{label}</span>
      <span className="text-white font-mono">{value}</span>
    </div>
  )
}
