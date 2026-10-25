import React from 'react'

interface HeaderControlsProps {
  selectedDate: string
  onDateChange: (date: string) => void
  cutoffHour: number
  onCutoffChange: (hour: number) => void
  loading: boolean
  onRefresh: () => void
}

const MIN_DATE = '2026-01-01'
const MAX_DATE = '2026-01-31'

const CUTOFF_OPTIONS = [
  { value: 8, label: '08:00 UTC' },
  { value: 9, label: '09:00 UTC' },
  { value: 10, label: '10:00 UTC' },
  { value: 11, label: '11:00 UTC (Hourly Auction)' },
  { value: 12, label: '12:00 UTC (Default / 30-min Auction)' },
  { value: 14, label: '14:00 UTC' },
  { value: 16, label: '16:00 UTC' },
  { value: 17, label: '17:00 UTC' },
]

export const HeaderControls: React.FC<HeaderControlsProps> = ({
  selectedDate,
  onDateChange,
  cutoffHour,
  onCutoffChange,
  loading,
  onRefresh,
}) => {
  const handlePrevDay = () => {
    const cur = new Date(selectedDate)
    cur.setDate(cur.getDate() - 1)
    const nextStr = cur.toISOString().split('T')[0]
    if (nextStr >= MIN_DATE) {
      onDateChange(nextStr)
    }
  }

  const handleNextDay = () => {
    const cur = new Date(selectedDate)
    cur.setDate(cur.getDate() + 1)
    const nextStr = cur.toISOString().split('T')[0]
    if (nextStr <= MAX_DATE) {
      onDateChange(nextStr)
    }
  }

  return (
    <header className="dashboard-header">
      <div className="header-brand">
        <div className="brand-badge">UK Wholesale Power</div>
        <h1 className="header-title">Wind Forecast Intelligence</h1>
        <p className="header-subtitle">
          National wind generation actuals and day-ahead forecast evaluation from Elexon BMRS for January 2026
        </p>
      </div>

      <div className="controls-bar">
        <div className="control-group">
          <label className="control-label" htmlFor="delivery-date-input">
            Delivery Date
          </label>
          <div className="date-picker-row">
            <button
              type="button"
              className="btn btn-secondary btn-icon"
              onClick={handlePrevDay}
              disabled={selectedDate <= MIN_DATE || loading}
              title="Previous delivery day"
            >
              ←
            </button>
            <input
              id="delivery-date-input"
              type="date"
              className="date-input"
              value={selectedDate}
              min={MIN_DATE}
              max={MAX_DATE}
              disabled={loading}
              onChange={(e) => onDateChange(e.target.value)}
            />
            <button
              type="button"
              className="btn btn-secondary btn-icon"
              onClick={handleNextDay}
              disabled={selectedDate >= MAX_DATE || loading}
              title="Next delivery day"
            >
              →
            </button>
          </div>
        </div>

        <div className="control-group">
          <label className="control-label" htmlFor="cutoff-select">
            D-1 Decision Cutoff
          </label>
          <select
            id="cutoff-select"
            className="select-input"
            value={cutoffHour}
            disabled={loading}
            onChange={(e) => onCutoffChange(Number(e.target.value))}
          >
            {CUTOFF_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="control-group control-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={onRefresh}
            disabled={loading}
          >
            {loading ? 'Fetching...' : 'Update Data'}
          </button>
        </div>
      </div>

      <div className="assumption-banner">
        <span className="banner-icon">ℹ</span>
        <span>
          <strong>Operational Assumption:</strong> Day-ahead purchase decisions are made on D-1 before the configured cutoff (default: 12:00 UTC). Forecasts published after this time are excluded from day-ahead procurement evaluation.
        </span>
      </div>
    </header>
  )
}
