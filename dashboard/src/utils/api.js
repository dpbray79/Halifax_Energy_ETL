/**
 * api.js
 * ═══════════════════════════════════════════════════════════════════════════════
 * API client for Halifax Energy Forecasting Dashboard (Supabase)
 * ═══════════════════════════════════════════════════════════════════════════════
 *
 * UPDATED FOR SUPABASE:
 *   - Replaced axios/FastAPI with Supabase REST API
 *   - Auto-generated endpoints from database schema
 *   - Real-time subscriptions replace WebSocket
 *
 * ═══════════════════════════════════════════════════════════════════════════════
 */

import { supabase, TABLES } from '../lib/supabaseClient'

// ── Actual Load Data ──────────────────────────────────────────────────────────

/**
 * Get actual load data from stg_nsp_load table
 * @param {Object} params - Query parameters
 * @param {string} params.start - Start datetime (ISO format)
 * @param {string} params.end - End datetime (ISO format)
 * @param {number} params.limit - Max rows to return (default 1000)
 * @returns {Promise<Array>} Array of load data points
 */
export const getActuals = async ({ start, end, limit = 1000 } = {}) => {
  try {
    let query = supabase
      .from(TABLES.LOAD)
      .select('datetime, load_mw, source')
      .order('datetime', { ascending: false })
      .limit(limit)

    if (start) {
      query = query.gte('datetime', start)
    }

    if (end) {
      query = query.lte('datetime', end)
    }

    const { data, error } = await query

    if (error) throw error
    return data
  } catch (error) {
    console.error('Error fetching actuals:', error)
    throw error
  }
}

/**
 * Get latest actual load data point
 * @returns {Promise<Object>} Latest load data point
 */
export const getLatestActual = async () => {
  try {
    const { data, error } = await supabase
      .from(TABLES.LOAD)
      .select('datetime, load_mw, source')
      .order('datetime', { ascending: false })
      .limit(1)
 
    if (error) throw error
    return data && data.length > 0 ? data[0] : null
  } catch (error) {
    console.error('Error fetching latest actual:', error)
    throw error
  }
}

/**
 * Get actuals summary statistics
 * @param {number} days - Number of days to summarize
 * @returns {Promise<Object>} Summary statistics
 */
export const getActualsSummary = async (days = 30) => {
  try {
    const startDate = new Date()
    startDate.setDate(startDate.getDate() - days)

    const { data, error } = await supabase
      .from(TABLES.LOAD)
      .select('load_mw')
      .gte('datetime', startDate.toISOString())

    if (error) throw error

    // Calculate summary stats
    const loads = data.map(d => d.load_mw)
    const summary = {
      count: loads.length,
      avg: loads.reduce((a, b) => a + b, 0) / loads.length,
      min: Math.min(...loads),
      max: Math.max(...loads),
      days: days
    }

    return summary
  } catch (error) {
    console.error('Error fetching actuals summary:', error)
    throw error
  }
}

// ── Model Predictions ─────────────────────────────────────────────────────────

/**
 * Get model predictions
 * @param {Object} params - Query parameters
 * @param {string} params.horizon - Forecast horizon (H1, H2, H3)
 * @param {string} params.start - Start datetime
 * @param {string} params.end - End datetime
 * @param {number} params.limit - Max rows
 * @param {boolean} params.latest_run_only - Only latest model run
 * @returns {Promise<Array>} Array of predictions
 */
export const getPredictions = async ({
  horizon,
  start,
  end,
  limit = 1000,
  latest_run_only = false
} = {}) => {
  try {
    let query = supabase
      .from(TABLES.PREDICTIONS)
      .select('*')
      .order('datetime', { ascending: false })
      .limit(limit)

    if (horizon) {
      query = query.eq('forecast_horizon', horizon)
    }

    if (start) {
      query = query.gte('datetime', start)
    }

    if (end) {
      query = query.lte('datetime', end)
    }

    if (latest_run_only) {
      // Get latest model_run_at first
      const { data: latestRun } = await supabase
        .from(TABLES.PREDICTIONS)
        .select('model_run_at')
        .order('model_run_at', { ascending: false })
        .limit(1)
        .single()

      if (latestRun) {
        query = query.eq('model_run_at', latestRun.model_run_at)
      }
    }

    const { data, error } = await query

    if (error) throw error
    return data
  } catch (error) {
    console.error('Error fetching predictions:', error)
    throw error
  }
}

/**
 * Get latest prediction for a specific horizon
 * @param {string} horizon - Forecast horizon (H1, H2, H3)
 * @returns {Promise<Object>} Latest prediction
 */
export const getLatestPrediction = async (horizon) => {
  try {
    const { data, error} = await supabase
      .from(TABLES.PREDICTIONS)
      .select('*')
      .eq('forecast_horizon', horizon)
      .order('datetime', { ascending: false })
      .limit(1)
 
    if (error) throw error
    return data && data.length > 0 ? data[0] : null
  } catch (error) {
    console.error('Error fetching latest prediction:', error)
    throw error
  }
}

/**
 * Get model performance metrics
 * @param {string} horizon - Optional horizon filter
 * @returns {Promise<Array>} Performance metrics by horizon
 */
export const getModelPerformance = async (horizon = null) => {
  try {
    let query = supabase
      .from(TABLES.PREDICTIONS)
      .select('forecast_horizon, run_rmse, run_si_pct, model_version, model_run_at')
      .order('model_run_at', { ascending: false })

    if (horizon) {
      query = query.eq('forecast_horizon', horizon)
    }

    const { data, error } = await query

    if (error) throw error

    // Group by horizon and get latest metrics
    const metrics = {}
    data.forEach(row => {
      const h = row.forecast_horizon
      if (!metrics[h] || new Date(row.model_run_at) > new Date(metrics[h].model_run_at)) {
        metrics[h] = row
      }
    })

    return Object.values(metrics)
  } catch (error) {
    console.error('Error fetching model performance:', error)
    throw error
  }
}

// ── Zones & GeoJSON ───────────────────────────────────────────────────────────

/**
 * Get Halifax zones GeoJSON with load data
 * NOTE: This function loads GeoJSON from static file and enriches with data
 *
 * @param {Object} params - Query parameters
 * @param {string} params.horizon - Forecast horizon
 * @param {string} params.timestamp - Specific timestamp
 * @returns {Promise<Object>} GeoJSON FeatureCollection
 */
export const getZones = async ({ horizon = 'H1', timestamp } = {}) => {
  try {
    // Load static GeoJSON (in production, this could be in Supabase Storage)
    const geojsonResponse = await fetch('/data/geojson/halifax_zones.geojson')
    const geojson = await geojsonResponse.json()

    // Get latest prediction for the horizon
    const prediction = await getLatestPrediction(horizon)

    // Get latest actual
    const actual = await getLatestActual()

    // Enrich each zone with prediction/actual data
    // (In a real implementation, you'd have zone-specific predictions)
    geojson.features = geojson.features.map(feature => ({
      ...feature,
      properties: {
        ...feature.properties,
        predicted_load_mw: prediction?.predicted_load_mw || 0,
        actual_load_mw: actual?.load_mw || 0,
        horizon: horizon
      }
    }))

    return geojson
  } catch (error) {
    console.error('Error fetching zones:', error)
    throw error
  }
}

// ── Model Management ──────────────────────────────────────────────────────────

/**
 * Trigger model training
 * NOTE: This requires a Supabase Edge Function or external service
 *
 * @param {Object} data - Request body
 * @param {string} data.horizon - Horizon to train
 * @param {boolean} data.backtest - Run backtest
 * @returns {Promise<Object>} Training job info
 */
export const runModel = async (data = {}) => {
  // This would call a Supabase Edge Function or GitHub Action
  console.warn('runModel: Not implemented for Supabase yet')
  console.info('To run model: Use GitHub Actions workflow or Supabase Edge Function')

  // Placeholder response
  return {
    status: 'info',
    message: 'Model training should be triggered via GitHub Actions'
  }
}

/**
 * Get model status and artifacts info
 * NOTE: Model artifacts are tracked in database or Supabase Storage
 */
export const getModelStatus = async () => {
  try {
    // Get latest predictions per horizon
    const horizons = ['H1', 'H2', 'H3']
    const status = {}

    for (const horizon of horizons) {
      const { data, error } = await supabase
        .from(TABLES.PREDICTIONS)
        .select('model_version, model_run_at, run_rmse, run_si_pct')
        .eq('forecast_horizon', horizon)
        .order('model_run_at', { ascending: false })
        .limit(1)
        .single()

      if (data) {
        status[horizon] = data
      }
    }

    return status
  } catch (error) {
    console.error('Error fetching model status:', error)
    throw error
  }
}

// ── Health Check ──────────────────────────────────────────────────────────────

/**
 * Health check - verify Supabase connection
 */
export const healthCheck = async () => {
  try {
    const { data, error } = await supabase
      .from(TABLES.LOAD)
      .select('count')
      .limit(1)

    if (error) throw error

    return {
      status: 'ok',
      database: 'connected',
      timestamp: new Date().toISOString()
    }
  } catch (error) {
    console.error('Health check failed:', error)
    return {
      status: 'error',
      database: 'disconnected',
      error: error.message
    }
  }
}

// ── Real-Time Subscriptions ───────────────────────────────────────────────────

/**
 * Subscribe to live actuals updates (replaces WebSocket)
 * Uses Supabase Realtime for streaming data
 *
 * @param {Function} onMessage - Callback for new data
 * @param {Function} onError - Callback for errors
 * @returns {Object} Subscription object with unsubscribe method
 */
export const connectLiveActuals = (onMessage, onError = null) => {
  const channel = supabase
    .channel('load-updates')
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: TABLES.LOAD
      },
      (payload) => {
        console.log('New load data:', payload.new)
        onMessage(payload.new)
      }
    )
    .subscribe((status) => {
      if (status === 'SUBSCRIBED') {
        console.log('Subscribed to live actuals')
      } else if (status === 'CHANNEL_ERROR') {
        console.error('Subscription error')
        if (onError) onError(new Error('Subscription failed'))
      }
    })

  // Return unsubscribe function
  return {
    close: () => supabase.removeChannel(channel)
  }
}

// Export supabase client for direct access if needed
export { supabase }
