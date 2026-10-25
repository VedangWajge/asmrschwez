import React, { useState, useRef } from 'react'
import { SettlementRecord } from '../types'
import { formatDateTimeUK, formatMW, formatTimeUK } from '../api'

interface WindTimeSeriesChartProps {
  records: SettlementRecord[]
}

export const WindTimeSeriesChart: React.FC<WindTimeSeriesChartProps> = ({ records }) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)
  const svgRef = useRef<SVGSVGElement | null>(null)

  if (!records || records.length === 0) {
    return (
      <div className="chart-empty-state">
        <p>No settlement periods available for the selected delivery date.</p>
      </div>
    )
  }

  // Dimensions
  const svgWidth = 1000
  const svgHeight = 360
  const padLeft = 70
  const padRight = 30
  const padTop = 30
  const padBottom = 45

  const plotWidth = svgWidth - padLeft - padRight
  const plotHeight = svgHeight - padTop - padBottom

  // Find max value for Y scaling (minimum at least 2000 MW to avoid divide-by-zero)
  const validActuals = records.map((r) => r.actual_mw).filter((v): v is number => v !== null)
  const validForecasts = records.map((r) => r.forecast_mw).filter((v): v is number => v !== null)
  const rawMax = Math.max(1000, ...validActuals, ...validForecasts)
  const maxY = Math.ceil((rawMax * 1.1) / 1000) * 1000

  // Y-axis gridlines (5 steps)
  const yTicks = [0, 0.25, 0.5, 0.75, 1.0].map((ratio) => Math.round(ratio * maxY))

  const getX = (index: number) => {
    if (records.length <= 1) return padLeft + plotWidth / 2
    return padLeft + (index / (records.length - 1)) * plotWidth
  }

  const getY = (val: number) => {
    return padTop + plotHeight - (val / maxY) * plotHeight
  }

  // Generate SVG path for a metric series handling nulls with discontinuous M commands
  const makePath = (getValue: (r: SettlementRecord) => number | null): string => {
    let path = ''
    let drawing = false

    records.forEach((r, i) => {
      const val = getValue(r)
      if (val === null) {
        drawing = false
        return
      }
      const x = getX(i)
      const y = getY(val)
      if (!drawing) {
        path += `M ${x.toFixed(1)} ${y.toFixed(1)}`
        drawing = true
      } else {
        path += ` L ${x.toFixed(1)} ${y.toFixed(1)}`
      }
    })

    return path
  }

  const actualPath = makePath((r) => r.actual_mw)
  const forecastPath = makePath((r) => r.forecast_mw)

  // Track hover index via mouse coordinates relative to SVG
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current || records.length === 0) return
    const rect = svgRef.current.getBoundingClientRect()
    const clientX = e.clientX - rect.left
    const svgX = (clientX / rect.width) * svgWidth
    const relativeX = svgX - padLeft
    const ratio = Math.max(0, Math.min(1, relativeX / plotWidth))
    const index = Math.round(ratio * (records.length - 1))
    setHoverIndex(index)
  }

  const handleMouseLeave = () => {
    setHoverIndex(null)
  }

  const activeRecord = hoverIndex !== null ? records[hoverIndex] : null

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <h2 className="chart-title">Generation Profile: Day-Ahead Forecast vs Actual</h2>
          <p className="chart-desc">
            Half-hourly power profile across all 48 settlement periods (00:00 to 23:30 GMT)
          </p>
        </div>
        <div className="chart-legend">
          <div className="legend-item">
            <span className="legend-swatch legend-actual"></span>
            <span className="legend-text">Actual Wind Generation</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch legend-forecast"></span>
            <span className="legend-text">Day-Ahead Forecast</span>
          </div>
        </div>
      </div>

      <div className="svg-container">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="chart-svg"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* Background grid */}
          {yTicks.map((tickVal) => {
            const y = getY(tickVal)
            return (
              <g key={tickVal} className="grid-row">
                <line
                  x1={padLeft}
                  y1={y}
                  x2={svgWidth - padRight}
                  y2={y}
                  stroke="#e2e8f0"
                  strokeDasharray="4 4"
                  strokeWidth="1"
                />
                <text
                  x={padLeft - 10}
                  y={y + 4}
                  textAnchor="end"
                  className="axis-label"
                >
                  {tickVal.toLocaleString('en-GB')} MW
                </text>
              </g>
            )
          })}

          {/* X Axis & Ticks (Every 4 hours = every 8 settlement periods) */}
          <line
            x1={padLeft}
            y1={padTop + plotHeight}
            x2={svgWidth - padRight}
            y2={padTop + plotHeight}
            stroke="#cbd5e1"
            strokeWidth="1.5"
          />

          {records.map((r, i) => {
            const isLabeled = i % 8 === 0 || i === records.length - 1
            if (!isLabeled) return null
            const x = getX(i)
            return (
              <g key={r.start_time} className="x-tick">
                <line
                  x1={x}
                  y1={padTop + plotHeight}
                  x2={x}
                  y2={padTop + plotHeight + 6}
                  stroke="#94a3b8"
                  strokeWidth="1"
                />
                <text
                  x={x}
                  y={padTop + plotHeight + 20}
                  textAnchor="middle"
                  className="axis-label"
                >
                  {formatTimeUK(r.start_time)}
                </text>
              </g>
            )
          })}

          {/* Forecast Line */}
          {forecastPath && (
            <path
              d={forecastPath}
              fill="none"
              stroke="#2563eb"
              strokeWidth="2.5"
              strokeDasharray="6 3"
              className="chart-line-forecast"
            />
          )}

          {/* Actual Line */}
          {actualPath && (
            <path
              d={actualPath}
              fill="none"
              stroke="#059669"
              strokeWidth="2.5"
              className="chart-line-actual"
            />
          )}

          {/* Hover Reference Line & Data Dots */}
          {hoverIndex !== null && activeRecord && (
            <g className="hover-guide">
              <line
                x1={getX(hoverIndex)}
                y1={padTop}
                x2={getX(hoverIndex)}
                y2={padTop + plotHeight}
                stroke="#64748b"
                strokeWidth="1.5"
                strokeDasharray="3 3"
              />
              {activeRecord.actual_mw !== null && (
                <circle
                  cx={getX(hoverIndex)}
                  cy={getY(activeRecord.actual_mw)}
                  r="5"
                  fill="#059669"
                  stroke="#ffffff"
                  strokeWidth="2"
                />
              )}
              {activeRecord.forecast_mw !== null && (
                <circle
                  cx={getX(hoverIndex)}
                  cy={getY(activeRecord.forecast_mw)}
                  r="5"
                  fill="#2563eb"
                  stroke="#ffffff"
                  strokeWidth="2"
                />
              )}
            </g>
          )}
        </svg>

        {/* Hover Tooltip Overlay */}
        {activeRecord && hoverIndex !== null && (
          <div
            className="chart-tooltip"
            style={{
              left: `${Math.min(
                Math.max(getX(hoverIndex) / svgWidth * 100, 15),
                85
              )}%`,
            }}
          >
            <div className="tooltip-header">
              <span className="tooltip-sp">SP {hoverIndex + 1}</span>
              <span className="tooltip-time">{formatTimeUK(activeRecord.start_time)} GMT</span>
            </div>
            <div className="tooltip-row">
              <span className="tooltip-dot dot-actual"></span>
              <span className="tooltip-label">Actual:</span>
              <span className="tooltip-value">{formatMW(activeRecord.actual_mw)}</span>
            </div>
            <div className="tooltip-row">
              <span className="tooltip-dot dot-forecast"></span>
              <span className="tooltip-label">Day-Ahead:</span>
              <span className="tooltip-value">{formatMW(activeRecord.forecast_mw)}</span>
            </div>
            <div className="tooltip-row tooltip-error-row">
              <span className="tooltip-label">Forecast Error:</span>
              <span
                className={`tooltip-value ${
                  activeRecord.error_mw !== null && activeRecord.error_mw > 0
                    ? 'text-bias-positive'
                    : activeRecord.error_mw !== null && activeRecord.error_mw < 0
                    ? 'text-bias-negative'
                    : ''
                }`}
              >
                {activeRecord.error_mw !== null
                  ? `${activeRecord.error_mw > 0 ? '+' : ''}${activeRecord.error_mw.toLocaleString('en-GB')} MW`
                  : '—'}
              </span>
            </div>
            <div className="tooltip-footer">
              Published: {formatDateTimeUK(activeRecord.forecast_publish_time)}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
