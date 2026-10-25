import { useEffect, useState, useCallback } from 'react'
import { DayAheadResponse } from './types'
import { fetchDayAheadData } from './api'
import { HeaderControls } from './components/HeaderControls'
import { KpiCards } from './components/KpiCards'
import { WindTimeSeriesChart } from './components/WindTimeSeriesChart'
import { PublicationTable } from './components/PublicationTable'
import './App.css'

export default function App() {
  const [selectedDate, setSelectedDate] = useState<string>('2026-01-01')
  const [cutoffHour, setCutoffHour] = useState<number>(12)
  const [data, setData] = useState<DayAheadResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async (date: string, cutoff: number) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchDayAheadData(date, cutoff)
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch day-ahead wind data')
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData(selectedDate, cutoffHour)
  }, [selectedDate, cutoffHour, loadData])

  return (
    <div className="dashboard-container">
      <HeaderControls
        selectedDate={selectedDate}
        onDateChange={setSelectedDate}
        cutoffHour={cutoffHour}
        onCutoffChange={setCutoffHour}
        loading={loading}
        onRefresh={() => loadData(selectedDate, cutoffHour)}
      />

      {error && (
        <div className="error-alert" role="alert">
          <div className="error-title">Data Retrieval Error</div>
          <p className="error-message">{error}</p>
          <button
            type="button"
            className="btn btn-secondary btn-retry"
            onClick={() => loadData(selectedDate, cutoffHour)}
          >
            Retry Request
          </button>
        </div>
      )}

      {loading && !data && (
        <div className="loading-state">
          <div className="spinner"></div>
          <p className="loading-text">Loading wind generation actuals and day-ahead forecasts from Elexon BMRS...</p>
        </div>
      )}

      {data && (
        <main className="dashboard-content">
          <KpiCards metrics={data.metrics} />
          <WindTimeSeriesChart records={data.records} />
          <PublicationTable records={data.records} />
        </main>
      )}

      <footer className="dashboard-footer">
        <p>
          Data source: Elexon BMRS API (FUELHH & WINDFOR streams) • National Grid Electricity System Operator (NESO)
        </p>
        <p>
          Target delivery: January 2026 • Timestamps shown in UK local time (GMT, UTC+0)
        </p>
      </footer>
    </div>
  )
}
