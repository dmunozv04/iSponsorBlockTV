import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react'
import { MonitoringStatus, DeviceState, WSMessage } from '../types'
import { useAuth } from './AuthContext'

interface WebSocketContextType {
  status: MonitoringStatus | null
  isConnected: boolean
  reconnect: () => void
}

const WebSocketContext = createContext<WebSocketContextType | null>(null)

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const [status, setStatus] = useState<MonitoringStatus | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (!isAuthenticated) return
    
    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws`
    
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    
    ws.onopen = () => {
      console.log('WebSocket connected')
      setIsConnected(true)
    }
    
    ws.onclose = () => {
      console.log('WebSocket disconnected')
      setIsConnected(false)
      
      // Reconnect after 5 seconds
      if (isAuthenticated) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, 5000)
      }
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
    
    ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data)
        
        switch (message.type) {
          case 'initial_status':
            setStatus(message.data as MonitoringStatus)
            break
          
          case 'status':
            setStatus(message.data as MonitoringStatus)
            break
          
          case 'device_status':
            setStatus((prev) => {
              if (!prev) return prev
              const deviceState = message.data as DeviceState
              return {
                ...prev,
                devices: {
                  ...prev.devices,
                  [message.screen_id!]: deviceState,
                },
              }
            })
            break
          
          case 'pong':
            // Heartbeat response
            break
          
          default:
            console.log('Unknown WebSocket message:', message)
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }
    
    // Send heartbeat every 30 seconds
    const heartbeatInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)
    
    // Clean up heartbeat on close
    ws.addEventListener('close', () => {
      clearInterval(heartbeatInterval)
    })
  }, [isAuthenticated])

  useEffect(() => {
    if (isAuthenticated) {
      connect()
    } else {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setStatus(null)
      setIsConnected(false)
    }
    
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [isAuthenticated, connect])

  const reconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    connect()
  }, [connect])

  return (
    <WebSocketContext.Provider value={{ status, isConnected, reconnect }}>
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocket() {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}
