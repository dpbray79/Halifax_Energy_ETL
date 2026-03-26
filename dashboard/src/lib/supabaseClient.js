/**
 * supabaseClient.js
 * ═══════════════════════════════════════════════════════════════════════════════
 * Supabase Client Configuration for Halifax Energy Dashboard
 * ═══════════════════════════════════════════════════════════════════════════════
 *
 * SETUP:
 *   1. Create .env.local in dashboard/ directory
 *   2. Add your Supabase credentials:
 *      VITE_SUPABASE_URL=https://your-project.supabase.co
 *      VITE_SUPABASE_ANON_KEY=your-anon-key
 *
 * ═══════════════════════════════════════════════════════════════════════════════
 */

import { createClient } from '@supabase/supabase-js'

// Get Supabase credentials from environment variables
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// Validate environment variables
if (!supabaseUrl || !supabaseAnonKey) {
  console.error('Missing Supabase environment variables!')
  console.error('Please create dashboard/.env.local with:')
  console.error('  VITE_SUPABASE_URL=https://your-project.supabase.co')
  console.error('  VITE_SUPABASE_ANON_KEY=your-anon-key')
}

// Create Supabase client
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true
  },
  realtime: {
    enabled: true  // Enable real-time subscriptions for live data
  }
})

/**
 * Database table names (must match schema)
 */
export const TABLES = {
  LOAD: 'stg_nsp_load',
  WEATHER: 'stg_weather',
  FACT: 'fact_energy_weather',
  PREDICTIONS: 'model_predictions',
  DIM_DATE: 'dim_date',
  WATERMARK: 'etl_watermark'
}

/**
 * Check if Supabase connection is working
 */
export const checkConnection = async () => {
  try {
    const { data, error } = await supabase
      .from(TABLES.LOAD)
      .select('count')
      .limit(1)

    if (error) throw error
    return true
  } catch (error) {
    console.error('Supabase connection failed:', error)
    return false
  }
}
