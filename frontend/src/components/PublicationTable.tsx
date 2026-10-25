import React, { useState } from 'react'
import { SettlementRecord } from '../types'
import { formatDateTimeUK, formatMW, formatTimeUK } from '../api'

interface PublicationTableProps {
  records: SettlementRecord[]
}

export const PublicationTable: React.FC<PublicationTableProps> = ({ records }) => {
  const [filter, setFilter] = useState<'all' | 'large_error' | 'missing'>('all')

  const filteredRecords = records.filter((r) => {
    if (filter === 'large_error') {
      return r.error_mw !== null && Math.abs(r.error_mw) >= 500
    }
    if (filter === 'missing') {
      return r.actual_mw === null || r.forecast_mw === null
    }
    return true
  })

  return (
    <div className="table-card">
      <div className="table-card-header">
        <div>
          <h2 className="table-title">Settlement Period Publication Audit</h2>
          <p className="table-desc">
            Audit of each 30-minute settlement period: target delivery time, selected D-1 forecast run, and observed generation
          </p>
        </div>

        <div className="table-filters">
          <button
            type="button"
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All Periods ({records.length})
          </button>
          <button
            type="button"
            className={`filter-btn ${filter === 'large_error' ? 'active' : ''}`}
            onClick={() => setFilter('large_error')}
          >
            |Error| ≥ 500 MW
          </button>
          <button
            type="button"
            className={`filter-btn ${filter === 'missing' ? 'active' : ''}`}
            onClick={() => setFilter('missing')}
          >
            Missing Data
          </button>
        </div>
      </div>

      <div className="table-wrapper">
        <table className="audit-table">
          <thead>
            <tr>
              <th className="text-center" style={{ width: '60px' }}>SP</th>
              <th>Target Time (GMT)</th>
              <th>Selected Forecast Published (D-1)</th>
              <th className="text-right">Day-Ahead Forecast</th>
              <th className="text-right">Actual Delivered</th>
              <th className="text-right">Forecast Error</th>
              <th className="text-center">Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredRecords.length === 0 ? (
              <tr>
                <td colSpan={7} className="table-empty-row">
                  No settlement periods match the selected filter.
                </td>
              </tr>
            ) : (
              filteredRecords.map((r, index) => {
                const spIndex = records.indexOf(r) + 1
                const hasError = r.error_mw !== null
                const errorClass =
                  hasError && r.error_mw! > 0
                    ? 'pill-overforecast'
                    : hasError && r.error_mw! < 0
                    ? 'pill-underforecast'
                    : 'pill-neutral'

                const isMissing = r.actual_mw === null || r.forecast_mw === null

                return (
                  <tr key={r.start_time} className={isMissing ? 'row-missing' : ''}>
                    <td className="text-center font-tabular font-bold">{spIndex}</td>
                    <td className="font-tabular">
                      <strong>{formatTimeUK(r.start_time)}</strong>
                    </td>
                    <td className="text-muted font-tabular">
                      {formatDateTimeUK(r.forecast_publish_time)}
                    </td>
                    <td className="text-right font-tabular font-semibold">
                      {formatMW(r.forecast_mw)}
                    </td>
                    <td className="text-right font-tabular font-semibold text-actual">
                      {formatMW(r.actual_mw)}
                    </td>
                    <td className="text-right font-tabular">
                      {hasError ? (
                        <span className={`error-pill ${errorClass}`}>
                          {r.error_mw! > 0 ? '+' : ''}
                          {r.error_mw!.toLocaleString('en-GB')} MW
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="text-center">
                      {r.actual_mw !== null && r.forecast_mw !== null ? (
                        <span className="status-badge-table badge-matched">Matched</span>
                      ) : (
                        <span className="status-badge-table badge-missing">Missing Data</span>
                      )}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
