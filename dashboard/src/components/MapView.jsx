import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON, Popup } from 'react-leaflet'
import { getZones } from '../utils/api'
import 'leaflet/dist/leaflet.css'
import './MapView.css'

// Fix Leaflet default icon issue with Vite
import L from 'leaflet'
import iconUrl from 'leaflet/dist/images/marker-icon.png'
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png'
import shadowUrl from 'leaflet/dist/images/marker-shadow.png'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
})

function MapView({ horizon = 'H1', showResiduals = false }) {
  const [geoData, setGeoData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadZones()
  }, [horizon])

  const loadZones = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getZones({ horizon })
      setGeoData(data)
    } catch (err) {
      setError(err.message)
      console.error('Failed to load zones:', err)
    } finally {
      setLoading(false)
    }
  }

  // Get color based on load value
  const getLoadColor = (load) => {
    if (!load) return '#cccccc'
    // Color scale: blue (low) -> yellow (medium) -> red (high)
    if (load < 100) return '#3b82f6'
    if (load < 200) return '#10b981'
    if (load < 300) return '#f59e0b'
    return '#ef4444'
  }

  // Get color based on residual (error)
  const getResidualColor = (residual) => {
    if (!residual) return '#cccccc'
    const absResidual = Math.abs(residual)
    // Green (accurate) -> Yellow -> Red (inaccurate)
    if (absResidual < 10) return '#10b981'
    if (absResidual < 25) return '#f59e0b'
    return '#ef4444'
  }

  // Style function for GeoJSON features
  const style = (feature) => {
    const props = feature.properties
    const value = showResiduals ? props.residual_mw : props.predicted_load_mw

    return {
      fillColor: showResiduals
        ? getResidualColor(props.residual_mw)
        : getLoadColor(props.predicted_load_mw),
      weight: 2,
      opacity: 1,
      color: 'white',
      fillOpacity: 0.7,
    }
  }

  // Popup content for each zone
  const onEachFeature = (feature, layer) => {
    const props = feature.properties

    const popupContent = `
      <div class="zone-popup">
        <h3>${props.zone_name}</h3>
        <div class="popup-data">
          <div class="data-row">
            <span class="label">Predicted Load:</span>
            <span class="value">${props.predicted_load_mw?.toFixed(1) || 'N/A'} MW</span>
          </div>
          ${props.actual_load_mw ? `
            <div class="data-row">
              <span class="label">Actual Load:</span>
              <span class="value">${props.actual_load_mw?.toFixed(1) || '0.0'} MW</span>
            </div>
            <div class="data-row">
              <span class="label">Residual:</span>
              <span class="value ${props.residual_mw > 0 ? 'positive' : 'negative'}">
                ${props.residual_mw > 0 ? '+' : ''}${(props.residual_mw || 0).toFixed(1)} MW
              </span>
            </div>
          ` : ''}
          <div class="data-row">
            <span class="label">Horizon:</span>
            <span class="value">${props.horizon}</span>
          </div>
          <div class="data-row text-xs text-muted">
            ${new Date(props.timestamp).toLocaleString()}
          </div>
        </div>
      </div>
    `

    layer.bindPopup(popupContent)

    // Hover effect
    layer.on({
      mouseover: (e) => {
        const layer = e.target
        layer.setStyle({
          weight: 3,
          fillOpacity: 0.9,
        })
      },
      mouseout: (e) => {
        const layer = e.target
        layer.setStyle({
          weight: 2,
          fillOpacity: 0.7,
        })
      },
    })
  }

  if (loading) {
    return (
      <div className="map-container">
        <div className="map-loading">
          <div className="spinner"></div>
          <p>Loading map data...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="map-container">
        <div className="map-error">
          <p>Error loading map: {error}</p>
          <button onClick={loadZones} className="btn-primary">
            Retry
          </button>
        </div>
      </div>
    )
  }

  // Halifax coordinates (centered on downtown)
  const center = [44.6488, -63.5752]
  const zoom = 11

  return (
    <div className="map-container">
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {geoData && (
          <GeoJSON
            data={geoData}
            style={style}
            onEachFeature={onEachFeature}
          />
        )}
      </MapContainer>

      {/* Legend */}
      <div className="map-legend">
        <h4>{showResiduals ? 'Prediction Error' : 'Predicted Load'}</h4>
        {showResiduals ? (
          <>
            <div className="legend-item">
              <span className="legend-color" style={{ background: '#10b981' }}></span>
              <span>&lt; 10 MW (Accurate)</span>
            </div>
            <div className="legend-item">
              <span className="legend-color" style={{ background: '#f59e0b' }}></span>
              <span>10-25 MW</span>
            </div>
            <div className="legend-item">
              <span className="legend-color" style={{ background: '#ef4444' }}></span>
              <span>&gt; 25 MW (Inaccurate)</span>
            </div>
          </>
        ) : (
          <>
            <div className="legend-item">
              <span className="legend-color" style={{ background: '#3b82f6' }}></span>
              <span>&lt; 100 MW</span>
            </div>
            <div className="legend-item">
              <span className="legend-color" style={{ background: '#10b981' }}></span>
              <span>100-200 MW</span>
            </div>
            <div className="legend-item">
              <span className="legend-color" style={{ background: '#f59e0b' }}></span>
              <span>200-300 MW</span>
            </div>
            <div className="legend-item">
              <span className="legend-color" style={{ background: '#ef4444' }}></span>
              <span>&gt; 300 MW</span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default MapView
