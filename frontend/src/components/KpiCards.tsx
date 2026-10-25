import React from 'react'
import { AccuracyMetrics } from '../types'
import { formatEnergy, formatMW } from '../api'

interface KpiCardsProps {
  metrics: AccuracyMetrics | null
}

export const KpiCards: React.FC<KpiCardsProps> = ({ metrics }) => {
  if (!metrics) return null

  const coveragePct =
    metrics.total_periods > 0
      ? Math.round((metrics.matched_periods / metrics.total_periods) * 100)
      : 0

  const biasSign =
    metrics.bias_mw !== null && metrics.bias_mw > 0 ? '+' : ''

  return (
    <section className="kpi-grid" aria-label="Key Performance Indicators">
      <div className="kpi-card forecast-card">
        <div className="kpi-header">
          <span className="kpi-title">Day-Ahead Forecast Energy</span>
          <span className="kpi-tag tag-forecast">Forecast</span>
        </div>
        <div className="kpi-value">{formatEnergy(metrics.forecast_energy_mwh)}</div>
        <div className="kpi-subtitle">
          Avg Power: {formatMW(metrics.forecast_avg_mw)}
        </div>
        <div className="kpi-footnote">Σ (MW × 0.5 h) over 48 settlement periods</div>
      </div>

      <div className="kpi-card actual-card">
        <div className="kpi-header">
          <span className="kpi-title">Actual Delivered Energy</span>
          <span className="kpi-tag tag-actual">Actual</span>
        </div>
        <div className="kpi-value">{formatEnergy(metrics.actual_energy_mwh)}</div>
        <div className="kpi-subtitle">
          Avg Power: {formatMW(metrics.actual_avg_mw)}
        </div>
        <div className="kpi-footnote">Σ (MW × 0.5 h) delivered to the GB grid</div>
      </div>

      <div className="kpi-card">
        <div className="kpi-header">
          <span className="kpi-title">Forecast Coverage</span>
          <span className="kpi-badge badge-coverage">{coveragePct}%</span>
        </div>
        <div className="kpi-value">
          {metrics.matched_periods} / {metrics.total_periods}
        </div>
        <div className="kpi-subtitle">Settlement Periods</div>
        <div className="kpi-footnote">Matched target half-hour observations</div>
      </div>

      <div className="kpi-card">
        <div className="kpi-header">
          <span className="kpi-title">Mean Absolute Error (MAE)</span>
          <span className="kpi-info" title="Mean of absolute differences: (1/n) Σ |Forecast - Actual|">
            ?
          </span>
        </div>
        <div className="kpi-value">{formatMW(metrics.mae_mw)}</div>
        <div className="kpi-subtitle">Average Magnitude of Error</div>
        <div className="kpi-footnote">Calculated on matched periods only</div>
      </div>

      <div className="kpi-card">
        <div className="kpi-header">
          <span className="kpi-title">Root Mean Square Error</span>
          <span className="kpi-info" title="Square root of mean squared error: √((1/n) Σ (Forecast - Actual)²)">
            ?
          </span>
        </div>
        <div className="kpi-value">{formatMW(metrics.rmse_mw)}</div>
        <div className="kpi-subtitle">Volatility / Large Swing Penalty</div>
        <div className="kpi-footnote">Sensitive to large forecast deviations</div>
      </div>

      <div className="kpi-card">
        <div className="kpi-header">
          <span className="kpi-title">Forecast Bias (Mean Error)</span>
          <span className="kpi-info" title="Mean signed error: (1/n) Σ (Forecast - Actual). Positive means over-forecasting.">
            ?
          </span>
        </div>
        <div
          className={`kpi-value ${
            metrics.bias_mw !== null && metrics.bias_mw > 0
              ? 'text-bias-positive'
              : metrics.bias_mw !== null && metrics.bias_mw < 0
              ? 'text-bias-negative'
              : ''
          }`}
        >
          {metrics.bias_mw !== null ? `${biasSign}${metrics.bias_mw.toFixed(1)} MW` : '—'}
        </div>
        <div className="kpi-subtitle">
          {metrics.bias_mw !== null && metrics.bias_mw > 0
            ? 'Over-forecasting (Procurement Risk)'
            : metrics.bias_mw !== null && metrics.bias_mw < 0
            ? 'Under-forecasting (Imbalance Risk)'
            : 'Neutral Bias'}
        </div>
        <div className="kpi-footnote">Forecast minus Actual generation</div>
      </div>
    </section>
  )
}
