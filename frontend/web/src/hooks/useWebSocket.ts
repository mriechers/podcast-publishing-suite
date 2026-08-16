import { useEffect, useRef, useState, useCallback } from 'react'

export interface Item {
  id: number
  title: string
  description: string
  status: string
  priority: number
  created_at: string
  updated_at: string
  [key: string]: unknown
}

export interface ItemStats {
  pending: number
  active: number
  completed: number
  failed: number
  total: number
}

export interface WebSocketMessage {
  type: 'item_created' | 'item_updated' | 'item_deleted' | 'stats_updated'
  item?: Item
  stats?: ItemStats
}

export interface UseItemsWebSocketOptions {
  onItemUpdate?: (item: Item, eventType: string) => void
  onStatsUpdate?: (stats: ItemStats) => void
  autoReconnect?: boolean
  reconnectInterval?: number
}

export function useItemsWebSocket(options: UseItemsWebSocketOptions = {}) {
  const {
    onItemUpdate,
    onStatsUpdate,
    autoReconnect = true,
    reconnectInterval = 5000,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const heartbeatIntervalRef = useRef<number | null>(null)
  const missedHeartbeatsRef = useRef(0)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/api/ws/updates`

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        setError(null)
        missedHeartbeatsRef.current = 0

        // Start heartbeat
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current)
        }
        heartbeatIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            missedHeartbeatsRef.current++
            if (missedHeartbeatsRef.current >= 3) {
              ws.close()
            } else {
              ws.send(JSON.stringify({ type: 'ping' }))
            }
          }
        }, 30000)
      }

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)

          // Reset heartbeat counter on any message
          missedHeartbeatsRef.current = 0

          if (message.type === 'item_created' || message.type === 'item_updated' || message.type === 'item_deleted') {
            if (message.item && onItemUpdate) {
              onItemUpdate(message.item, message.type)
            }
          } else if (message.type === 'stats_updated') {
            if (message.stats && onStatsUpdate) {
              onStatsUpdate(message.stats)
            }
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      ws.onerror = () => {
        setError('WebSocket connection error')
      }

      ws.onclose = () => {
        setIsConnected(false)
        wsRef.current = null

        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current)
          heartbeatIntervalRef.current = null
        }

        if (autoReconnect) {
          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current)
          }
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect()
          }, reconnectInterval)
        }
      }
    } catch (err) {
      setError('Failed to establish WebSocket connection')
      console.error('WebSocket connection error:', err)
    }
  }, [autoReconnect, reconnectInterval, onItemUpdate, onStatsUpdate])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current)
      heartbeatIntervalRef.current = null
    }

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setIsConnected(false)
  }, [])

  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    isConnected,
    error,
    reconnect: connect,
    disconnect,
  }
}
