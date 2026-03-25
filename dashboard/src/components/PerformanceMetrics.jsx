import { useState, useEffect } from 'react'
import { getModelPerformance } from '../utils/api'
import { TrendingUp, Target, Activity } from 'lucide-react'
import './PerformanceMetrics.css'

function PerformanceMetrics() {
  const [performance, setPerformance] = useState({ horizons: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadPerformance()
  }, [])

  const loadPerformance = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getModelPerformance()
      setPerformance({ horizons: data })
    } catch (err) {
      setError(err.message)
      console.error('Failed to load performance:', err)
    } finally {
      setLoading(false)
    }
  }

  const getPerformanceColor = (actual, target) => {
    if (actual <= target) return 'var(--success)'
    if (actual <= target * 1.2) return 'var(--warning)'
    return 'var(--danger)'
  }

  const getPerformanceStatus = (actual, target) => {
    if (actual <= target) return '✓ On Target'
    if (actual <= target * 1.2) return '⚠ Near Target'
    return '✗ Below Target'
  }

  if (loading) {
    return (
      <div className="metrics-container">
        <div className="spinner"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="metrics-container">
        <p className="text-sm" style={{ color: 'var(--danger)' }}>
          Error loading metrics: {error}
        </p>
      </div>
    )
  }

  if (!performance.horizons || performance.horizons.length === 0) {
    return (
      <div className="metrics-container">
        <p className="text-sm text-muted">No performance data available</p>
      </div>
    )
  }

  return (
    <div className="metrics-grid">
      {performance.horizons.map((horizon) => {
        // Fallback targets for display
        const rmse_target = horizon.forecast_horizon === 'H1' ? 50 : horizon.forecast_horizon === 'H2' ? 80 : 150
        const si_target_pct = 10.0

        return (
          <div key={horizon.forecast_horizon} className="metric-card">
            <div className="metric-header">
              <h3>{horizon.forecast_horizon}</h3>
              <span className="text-xs text-muted">
                {horizon.forecast_horizon === 'H1'
                  ? '24h Forecast'
                  : horizon.forecast_horizon === 'H2'
                  ? '48h Forecast'
                  : '7d Forecast'}
              </span>
            </div>

            <div className="metric-stats">
              {/* RMSE */}
              <div className="stat-item">
                <div className="stat-icon" style={{ backgroundColor: '#e3f2fd' }}>
                  <TrendingUp size={20} color="#0066cc" />
                </div>
                <div className="stat-content">
                  <span className="stat-label">RMSE</span>
                  <span
                    className="stat-value"
                    style={{
                      color: getPerformanceColor(
                        horizon.run_rmse,
                        rmse_target
                      ),
                    }}
                  >
                    {horizon.run_rmse?.toFixed(1) || 'N/A'} MW
                  </span>
                  <span className="stat-target text-xs text-muted">
                    Target: &lt; {rmse_target} MW
                  </span>
                </div>
              </div>

              {/* SI% */}
              <div className="stat-item">
                <div className="stat-icon" style={{ backgroundColor: '#fff3e0' }}>
                  <Target size={20} color="#ff8800" />
                </div>
                <div className="stat-content">
                  <span className="stat-label">SI%</span>
                  <span
                    className="stat-value"
                    style={{
                      color: getPerformanceColor(
                        horizon.run_si_pct,
                        si_target_pct
                      ),
                    }}
                  >
                    {horizon.run_si_pct?.toFixed(1) || 'N/A'}%
                  </span>
                  <span className="stat-target text-xs text-muted">
                    Target: &lt; {si_target_pct}%
                  </span>
                </div>
              </div>

              {/* Predictions Count */}
              <div className="stat-item">
                <div className="stat-icon" style={{ backgroundColor: '#e8f5e9' }}>
                  <Activity size={20} color="#28a745" />
                </div>
                <div className="stat-content">
                  <span className="stat-label">Model Version</span>
                  <span className="stat-value" style={{ fontSize: '0.9rem' }}>
                    {horizon.model_version || 'v1.0'}
                  </span>
                  <span className="stat-target text-xs text-muted">
                    {getPerformanceStatus(horizon.run_rmse, rmse_target)}
                  </span>
                </div>
              </div>
            </div>

            <div className="metric-footer text-xs text-muted">
              Last run: {new Date(horizon.model_run_at).toLocaleString()}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default PerformanceMetrics
