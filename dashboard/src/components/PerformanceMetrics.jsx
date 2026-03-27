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

  // Group data by horizon for rendering
  const groupedPerformance = performance.horizons.reduce((acc, current) => {
    const h = current.forecast_horizon
    if (!acc[h]) acc[h] = []
    acc[h].push(current)
    return acc
  }, {})

  if (Object.keys(groupedPerformance).length === 0) {
    return (
      <div className="metrics-container">
        <p className="text-sm text-muted">No performance data available</p>
      </div>
    )
  }

  return (
    <div className="metrics-grid">
      {Object.entries(groupedPerformance).map(([horizon, variants]) => {
        // Sort variants so best RMSE is first
        const sortedVariants = [...variants].sort((a, b) => a.run_rmse - b.run_rmse)
        const bestVariant = sortedVariants[0]
        
        // Fallback targets
        const rmse_target = horizon === 'H1' ? 50 : horizon === 'H2' ? 80 : 150

        return (
          <div key={horizon} className="comparison-card card">
            <div className="metric-header">
              <h3>{horizon} Comparison</h3>
              <span className="text-xs text-muted">
                {horizon === 'H1' ? '24h' : horizon === 'H2' ? '48h' : '7d'} Horizon Performance
              </span>
            </div>

            <div className="comparison-list">
              <table className="mini-table">
                <thead>
                  <tr>
                    <th>Config</th>
                    <th>RMSE</th>
                    <th>SI%</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedVariants.map((variant, idx) => {
                    const configName = `${variant.model_algorithm.replace('_', ' ')} ${variant.use_weather ? '(W)' : '(B)'}${variant.use_rolling ? '+R' : ''}`
                    return (
                      <tr key={idx} className={idx === 0 ? 'best-row' : ''}>
                        <td className="text-xs font-semibold">{configName}</td>
                        <td style={{ color: getPerformanceColor(variant.run_rmse, rmse_target) }}>
                          {variant.run_rmse?.toFixed(1)}
                        </td>
                        <td className="text-xs text-muted">
                          {variant.run_si_pct?.toFixed(1)}%
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="metric-footer text-xs text-muted">
              Best Run: {new Date(bestVariant.model_run_at).toLocaleString()}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default PerformanceMetrics
