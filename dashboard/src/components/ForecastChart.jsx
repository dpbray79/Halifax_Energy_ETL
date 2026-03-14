import { useState, useEffect } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { getActuals, getPredictions } from '../utils/api'
import { format, subDays } from 'date-fns'
import './ForecastChart.css'

function ForecastChart({ horizon = 'H1', days = 7 }) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadChartData()
  }, [horizon, days])

  const loadChartData = async () => {
    setLoading(true)
    setError(null)

    try {
      const endDate = new Date()
      const startDate = subDays(endDate, days)

      // Fetch actuals and predictions in parallel
      const [actualsResponse, predictionsResponse] = await Promise.all([
        getActuals({
          start: startDate.toISOString(),
          end: endDate.toISOString(),
          limit: days * 24,
        }),
        getPredictions({
          horizon,
          start: startDate.toISOString(),
          end: endDate.toISOString(),
          latest_run_only: true,
          limit: days * 24,
        }),
      ])

      // Merge actuals and predictions by datetime
      const actualsMap = new Map(
        actualsResponse.data.map((d) => [d.datetime, d.load_mw])
      )

      const predictionsMap = new Map(
        predictionsResponse.data.map((d) => [d.datetime, d.predicted_load_mw])
      )

      // Get all unique timestamps
      const allTimestamps = new Set([
        ...actualsMap.keys(),
        ...predictionsMap.keys(),
      ])

      // Combine data
      const combined = Array.from(allTimestamps)
        .map((timestamp) => ({
          timestamp,
          datetime: new Date(timestamp),
          actual: actualsMap.get(timestamp),
          predicted: predictionsMap.get(timestamp),
        }))
        .sort((a, b) => a.datetime - b.datetime)

      setData(combined)
    } catch (err) {
      setError(err.message)
      console.error('Failed to load chart data:', err)
    } finally {
      setLoading(false)
    }
  }

  const formatXAxis = (timestamp) => {
    return format(new Date(timestamp), 'MMM dd HH:mm')
  }

  const formatTooltip = (value, name) => {
    if (value == null) return ['N/A', name]
    return [`${value.toFixed(1)} MW`, name]
  }

  const formatTooltipLabel = (timestamp) => {
    return format(new Date(timestamp), 'PPpp')
  }

  if (loading) {
    return (
      <div className="chart-container">
        <div className="chart-loading">
          <div className="spinner"></div>
          <p>Loading forecast data...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="chart-container">
        <div className="chart-error">
          <p>Error loading chart: {error}</p>
          <button onClick={loadChartData} className="btn-primary">
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="chart-container">
        <div className="chart-empty">
          <p>No data available for the selected period</p>
        </div>
      </div>
    )
  }

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatXAxis}
            stroke="#666"
            style={{ fontSize: '0.75rem' }}
          />
          <YAxis
            label={{ value: 'Load (MW)', angle: -90, position: 'insideLeft' }}
            stroke="#666"
            style={{ fontSize: '0.75rem' }}
          />
          <Tooltip
            formatter={formatTooltip}
            labelFormatter={formatTooltipLabel}
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #ddd',
              borderRadius: '8px',
              padding: '10px',
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: '0.875rem' }}
            iconType="line"
          />

          {/* Actual Load - Solid Blue Line */}
          <Line
            type="monotone"
            dataKey="actual"
            stroke="#0066cc"
            strokeWidth={2}
            dot={false}
            name="Actual Load"
            connectNulls
          />

          {/* Predicted Load - Dashed Orange Line */}
          <Line
            type="monotone"
            dataKey="predicted"
            stroke="#ff8800"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            name={`Predicted Load (${horizon})`}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default ForecastChart
