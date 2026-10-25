import { DayAheadResponse } from './types'

export async function fetchDayAheadData(
  date: string,
  cutoffHour: number = 12
): Promise<DayAheadResponse> {
  const params = new URLSearchParams({
    date_from: date,
    date_to: date,
    cutoff_hour: cutoffHour.toString(),
  })
  const res = await fetch(`/api/day-ahead?${params}`)
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(errorBody.detail || `Request failed with status ${res.status}`)
  }
  return res.json()
}

export function formatTimeUK(isoString: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Europe/London',
  }).format(new Date(isoString))
}

export function formatDateTimeUK(isoString: string | null): string {
  if (!isoString) return 'Unavailable'
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Europe/London',
  }).format(new Date(isoString))
}

export function formatMW(val: number | null): string {
  if (val === null || val === undefined) return '—'
  return new Intl.NumberFormat('en-GB').format(Math.round(val)) + ' MW'
}

export function formatEnergy(mwh: number | null): string {
  if (mwh === null || mwh === undefined) return '—'
  if (mwh >= 1000) {
    return (mwh / 1000).toLocaleString('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' GWh'
  }
  return mwh.toLocaleString('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' MWh'
}
