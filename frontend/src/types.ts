export interface AccuracyMetrics {
  matched_periods: number
  total_periods: number
  mae_mw: number | null
  rmse_mw: number | null
  bias_mw: number | null
  actual_energy_mwh: number | null
  forecast_energy_mwh: number | null
  actual_avg_mw: number | null
  forecast_avg_mw: number | null
}

export interface SettlementRecord {
  start_time: string
  actual_mw: number | null
  forecast_mw: number | null
  error_mw: number | null
  forecast_publish_time: string | null
  cutoff_time: string
}

export interface DayAheadResponse {
  delivery_from: string
  delivery_to: string
  cutoff_hour: number
  count: number
  metrics: AccuracyMetrics
  records: SettlementRecord[]
}
