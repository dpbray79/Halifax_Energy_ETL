import { useState, useEffect } from 'react'
import { runModel, getModelStatus } from '../utils/api'
import PerformanceMetrics from '../components/PerformanceMetrics'
import { Play, CheckCircle, XCircle, Clock, FileCode } from 'lucide-react'
import './Models.css'

function Models() {
  const [modelStatus, setModelStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [training, setTraining] = useState(false)
  const [trainResult, setTrainResult] = useState(null)
  const [selectedAlgorithm, setSelectedAlgorithm] = useState('xgboost')
  const [selectedHorizon, setSelectedHorizon] = useState(null)
  const [tune, setTune] = useState(false)

  useEffect(() => {
    loadModelStatus()
  }, [])

  const loadModelStatus = async () => {
    setLoading(true)
    try {
      const status = await getModelStatus()
      setModelStatus(status)
    } catch (error) {
      console.error('Failed to load model status:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRunModel = async () => {
    setTraining(true)
    setTrainResult(null)

    try {
      const result = await runModel({
        horizon: selectedHorizon,
        algorithm: selectedAlgorithm,
        tune: tune,
      })

      setTrainResult({
        success: true,
        message: result.message,
        details: result.details,
      })

      // Reload model status after training
      setTimeout(loadModelStatus, 2000)
    } catch (error) {
      setTrainResult({
        success: false,
        message: error.response?.data?.detail || error.message,
      })
    } finally {
      setTraining(false)
    }
  }

  return (
    <div className="models-page">
      <div className="page-header">
        <div>
          <h1>Model Management</h1>
          <p className="text-muted">
            Train and monitor multi-regression forecasting models
          </p>
        </div>
      </div>

      {/* Training Control */}
      <section className="models-section card">
        <h2>Train Models</h2>
        <p className="text-sm text-muted">
          Trigger predictive regression training for specific horizons
        </p>

        <div className="training-controls">
          <div className="control-group">
            <label htmlFor="algorithm-select">Model Algorithm</label>
            <select
              id="algorithm-select"
              value={selectedAlgorithm}
              onChange={(e) => setSelectedAlgorithm(e.target.value)}
              disabled={training}
            >
              <option value="xgboost">XGBoost (High Perf)</option>
              <option value="random_forest">Random Forest</option>
              <option value="linear">Linear Regression</option>
            </select>
          </div>

          <div className="control-group">
            <label htmlFor="horizon-select">Forecast Horizon</label>
            <select
              id="horizon-select"
              value={selectedHorizon || ''}
              onChange={(e) => setSelectedHorizon(e.target.value || null)}
              disabled={training}
            >
              <option value="">All Horizons</option>
              <option value="H1">H1 (24h)</option>
              <option value="H2">H2 (48h)</option>
              <option value="H3">H3 (7d)</option>
            </select>
          </div>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={tune}
              onChange={(e) => setTune(e.target.checked)}
              disabled={training}
            />
            <span>Enable Hyperparameter Tuning</span>
          </label>

          <button
            onClick={handleRunModel}
            disabled={training}
            className="btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            {training ? (
              <>
                <Clock size={18} className="spinning" />
                Training...
              </>
            ) : (
              <>
                <Play size={18} />
                Run Training
              </>
            )}
          </button>
        </div>

        {trainResult && (
          <div
            className={`training-result ${
              trainResult.success ? 'success' : 'error'
            }`}
          >
            {trainResult.success ? (
              <CheckCircle size={20} />
            ) : (
              <XCircle size={20} />
            )}
            <div>
              <p className="font-semibold">{trainResult.message}</p>
              {trainResult.details && (
                <p className="text-sm">
                  Estimated duration: {trainResult.details.estimated_duration}
                </p>
              )}
            </div>
          </div>
        )}
      </section>

      {/* Model Artifacts */}
      <section className="models-section card">
        <h2>Model Artifacts</h2>
        <p className="text-sm text-muted">
          Saved model files and R script status
        </p>

        {loading ? (
          <div className="flex items-center justify-between" style={{ padding: '1rem 0' }}>
            <div className="spinner"></div>
          </div>
        ) : modelStatus ? (
          <>
            <div className="artifact-info">
              <FileCode size={20} />
              <div>
                <p className="font-semibold">R Script</p>
                <p className="text-sm text-muted">{modelStatus.r_script.path}</p>
                <p className="text-xs">
                  Status:{' '}
                  {modelStatus.r_script.exists ? (
                    <span style={{ color: 'var(--success)' }}>✓ Exists</span>
                  ) : (
                    <span style={{ color: 'var(--danger)' }}>✗ Not Found</span>
                  )}
                </p>
              </div>
            </div>

            <div className="artifacts-list">
              <h3>Trained Models ({modelStatus.artifacts.count})</h3>
              {modelStatus.artifacts.models.length > 0 ? (
                <div className="artifact-grid">
                  {modelStatus.artifacts.models.map((artifact) => (
                    <div key={artifact.horizon} className="artifact-item">
                      <div className="artifact-header">
                        <span className="artifact-horizon">{artifact.horizon}</span>
                        <span className="artifact-size text-xs text-muted">
                          {(artifact.size_bytes / 1024)?.toFixed(1) || '0.0'} KB
                        </span>
                      </div>
                      <p className="artifact-file text-sm">{artifact.file}</p>
                      <p className="text-xs text-muted">
                        Modified: {new Date(artifact.modified_at).toLocaleString()}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted">No trained models found</p>
              )}
            </div>
          </>
        ) : (
          <p className="text-sm" style={{ color: 'var(--danger)' }}>
            Failed to load model status
          </p>
        )}
      </section>

      {/* Performance Metrics */}
      <section className="models-section">
        <h2>Current Performance</h2>
        <p className="text-sm text-muted">
          Latest model performance metrics across all horizons
        </p>
        <PerformanceMetrics />
      </section>
    </div>
  )
}

export default Models
