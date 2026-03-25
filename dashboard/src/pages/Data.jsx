import { useState, useEffect } from 'react'
import { getActuals, getLatestActual, getActualsSummary } from '../utils/api'
import { Database, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react'
import './Data.css'

function Data() {
  const [latestData, setLatestData] = useState(null)
  const [summary, setSummary] = useState(null)
  const [recentData, setRecentData] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [latest, summaryData, recent] = await Promise.all([
        getLatestActual(),
        getActualsSummary(30),
        getActuals({ limit: 50 }),
      ])

      setLatestData(latest)
      setSummary(summaryData)
      setRecentData(recent)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    await loadData()
    setRefreshing(false)
  }

  if (loading) {
    return (
      <div className="data-page">
        <div style={{ textAlign: 'center', padding: '3rem' }}>
          <div className="spinner" style={{ margin: '0 auto' }}></div>
          <p className="text-muted" style={{ marginTop: '1rem' }}>
            Loading data...
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="data-page">
      <div className="page-header">
        <div>
          <h1>Data Explorer</h1>
          <p className="text-muted">
            View and analyze historical NS grid load data
          </p>
        </div>

        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="btn-secondary"
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
        >
          <RefreshCw size={18} className={refreshing ? 'spinning' : ''} />
          Refresh
        </button>
      </div>

      {/* Latest Data Point */}
      {latestData && (
        <section className="data-section card">
          <h2>Latest Reading</h2>
          <div className="latest-data">
            <div className="latest-value">
              <span className="value-large">{latestData.load_mw.toFixed(1)}</span>
              <span className="value-unit">MW</span>
            </div>
            <div className="latest-meta">
              <p className="text-sm text-muted">
                {new Date(latestData.datetime).toLocaleString()}
              </p>
              <p className="text-xs text-muted">Source: {latestData.source}</p>
            </div>
          </div>
        </section>
      )}

      {/* Summary Statistics */}
      {summary && (
        <section className="data-section card">
          <h2>30-Day Summary</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon" style={{ backgroundColor: '#e3f2fd' }}>
                <Database size={24} color="#0066cc" />
              </div>
              <div className="stat-content">
                <span className="stat-label">Data Points</span>
                <span className="stat-value">
                  {summary.count.toLocaleString()}
                </span>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon" style={{ backgroundColor: '#fff3e0' }}>
                <TrendingUp size={24} color="#ff8800" />
              </div>
              <div className="stat-content">
                <span className="stat-label">Peak Load</span>
                <span className="stat-value">
                  {summary.max?.toFixed(1)} MW
                </span>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon" style={{ backgroundColor: '#e8f5e9' }}>
                <TrendingDown size={24} color="#28a745" />
              </div>
              <div className="stat-content">
                <span className="stat-label">Min Load</span>
                <span className="stat-value">
                  {summary.min?.toFixed(1)} MW
                </span>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon" style={{ backgroundColor: '#f3e5f5' }}>
                <Database size={24} color="#9c27b0" />
              </div>
              <div className="stat-content">
                <span className="stat-label">Average Load</span>
                <span className="stat-value">
                  {summary.avg?.toFixed(1)} MW
                </span>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Recent Data Table */}
      <section className="data-section card">
        <h2>Recent Data ({recentData.length} rows)</h2>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Load (MW)</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {recentData.map((row, idx) => (
                <tr key={idx}>
                  <td className="timestamp-cell">
                    {new Date(row.datetime).toLocaleString()}
                  </td>
                  <td className="load-cell">{row.load_mw.toFixed(1)}</td>
                  <td className="source-cell text-xs text-muted">
                    {row.source}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

export default Data
