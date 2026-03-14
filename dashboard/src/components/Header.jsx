import { useState, useEffect } from 'react'
import { Activity } from 'lucide-react'
import { healthCheck } from '../utils/api'
import './Header.css'

function Header() {
  const [status, setStatus] = useState({ database: 'unknown' })
  const [currentTime, setCurrentTime] = useState(new Date())

  useEffect(() => {
    // Check health on mount
    const checkHealth = async () => {
      try {
        const data = await healthCheck()
        setStatus(data)
      } catch (error) {
        setStatus({ database: 'error' })
      }
    }
    checkHealth()

    // Update time every second
    const timer = setInterval(() => {
      setCurrentTime(new Date())
    }, 1000)

    return () => clearInterval(timer)
  }, [])

  const getStatusColor = (dbStatus) => {
    switch (dbStatus) {
      case 'ok': return '#28a745'
      case 'error': return '#dc3545'
      default: return '#6c757d'
    }
  }

  return (
    <header className="header">
      <div className="header-content">
        <div className="header-left">
          <h1 className="header-title">Halifax Energy Demand Forecasting</h1>
        </div>

        <div className="header-right">
          <div className="status-indicator">
            <Activity size={16} />
            <span className="text-sm">Database:</span>
            <span
              className="status-badge"
              style={{ backgroundColor: getStatusColor(status.database) }}
            >
              {status.database}
            </span>
          </div>

          <div className="time-display text-sm text-muted">
            {currentTime.toLocaleTimeString('en-US', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit'
            })}
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header
