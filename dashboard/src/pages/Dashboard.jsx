import { useState } from 'react'
import MapView from '../components/MapView'
import ForecastChart from '../components/ForecastChart'
import PerformanceMetrics from '../components/PerformanceMetrics'
import './Dashboard.css'

function Dashboard() {
  const [selectedHorizon, setSelectedHorizon] = useState('H1')
  const [showResiduals, setShowResiduals] = useState(false)
  const [chartDays, setChartDays] = useState(7)

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <div>
          <h1>Energy Demand Dashboard</h1>
          <p className="text-muted">
            Real-time Nova Scotia grid load predictions and analysis
          </p>
        </div>

        <div className="controls">
          <select
            value={selectedHorizon}
            onChange={(e) => setSelectedHorizon(e.target.value)}
            className="horizon-select"
          >
            <option value="H1">H1 (24h)</option>
            <option value="H2">H2 (48h)</option>
            <option value="H3">H3 (7d)</option>
          </select>

          <label className="toggle-label">
            <input
              type="checkbox"
              checked={showResiduals}
              onChange={(e) => setShowResiduals(e.target.checked)}
            />
            <span>Show Residuals</span>
          </label>
        </div>
      </div>

      {/* Map Section */}
      <section className="dashboard-section">
        <div className="section-header">
          <h2>Halifax Zones</h2>
          <p className="text-sm text-muted">
            {showResiduals
              ? 'Prediction error by zone (MW)'
              : 'Predicted load by zone (MW)'}
          </p>
        </div>
        <MapView horizon={selectedHorizon} showResiduals={showResiduals} />
      </section>

      {/* Chart Section */}
      <section className="dashboard-section">
        <div className="section-header">
          <h2>Forecast vs Actual</h2>
          <div className="flex items-center gap-md">
            <p className="text-sm text-muted">
              Last {chartDays} days
            </p>
            <select
              value={chartDays}
              onChange={(e) => setChartDays(Number(e.target.value))}
              className="days-select"
            >
              <option value="3">3 days</option>
              <option value="7">7 days</option>
              <option value="14">14 days</option>
              <option value="30">30 days</option>
            </select>
          </div>
        </div>
        <ForecastChart horizon={selectedHorizon} days={chartDays} />
      </section>

      {/* Performance Metrics */}
      <section className="dashboard-section">
        <div className="section-header">
          <h2>Model Performance</h2>
          <p className="text-sm text-muted">
            Current RMSE and SI% metrics for all horizons
          </p>
        </div>
        <PerformanceMetrics />
      </section>
    </div>
  )
}

export default Dashboard
