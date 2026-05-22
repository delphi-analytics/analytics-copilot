/**
 * ChartRenderer — renders Apache ECharts option objects from the backend.
 * Applies ₹ formatting directly on axis labels, data labels, and tooltips.
 * Includes export functionality with proper backgrounds.
 */
import React, { useMemo, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import { autoFormatValue, indianiseCurrencyText } from '../../lib/formatters'

interface ChartRendererProps {
  vizConfig: Record<string, unknown>
  vizType: string | null
  columns?: string[]
  rows?: Record<string, unknown>[]
  height?: string
  theme?: 'light' | 'dark'
  role?: string
}

// ─── Formatters ──────────────────────────────────────────────────────────────

/** Format a number as ₹ — max Crore level, no Arab/Kharab */
function fmtINR(val: unknown): string {
  const n = typeof val === 'number' ? val : parseFloat(String(val))
  if (isNaN(n)) return String(val ?? '')
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1_00_00_000) return `${sign}₹${(abs / 1_00_00_000).toFixed(1)}Cr`
  if (abs >= 1_00_000)    return `${sign}₹${(abs / 1_00_000).toFixed(1)}L`
  if (abs >= 1_000)       return `${sign}₹${(abs / 1_000).toFixed(1)}K`
  return `${sign}₹${abs.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

/** Format a count or quantity (K/L/Cr) without any currency symbol */
function fmtCount(val: unknown): string {
  const n = typeof val === 'number' ? val : parseFloat(String(val))
  if (isNaN(n)) return String(val ?? '')
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1_00_00_000) return `${sign}${(abs / 1_00_00_000).toFixed(1)}Cr`
  if (abs >= 1_00_000)    return `${sign}${(abs / 1_00_000).toFixed(1)}L`
  if (abs >= 1_000)       return `${sign}${(abs / 1_000).toFixed(1)}K`
  return `${sign}${abs.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

/** Detect if a column/series name looks like money */
const isMoney = (name: string) => {
  const n = (name || '').toLowerCase()
  return ['revenue', 'sales', 'subtotal', 'total', 'price', 'amount', 'cost',
    'mrp', 'sp', 'value', 'gross', 'income', 'spend', 'profit', 'loss',
    'cogs', 'gmv', 'net', 'billing', 'earning'].some(k => n.includes(k))
}

/** Detect whether the series data values are large monetary figures */
function seriesLooksLikeMoney(series: unknown[]): boolean {
  for (const s of series) {
    const sr = s as Record<string, unknown>
    if (isMoney(String(sr.name || ''))) return true
    const data = Array.isArray(sr.data) ? sr.data : []
    const sample = data.slice(0, 5)
    const nums = sample.map((d: unknown) => typeof d === 'number' ? d : parseFloat(String(d))).filter((v: number) => !isNaN(v))
    if (nums.length && Math.max(...nums) > 10_000) return true
  }
  return false
}

// ─── Config patcher ───────────────────────────────────────────────────────────

function patchConfig(cfg: Record<string, unknown>): Record<string, unknown> {
  const out = structuredClone(cfg) as Record<string, unknown>
  const seriesArr = Array.isArray(out.series) ? (out.series as Record<string, unknown>[]) : []

  // ── Y-axis: format each Y-axis based on whether its bound series are currency ──
  if (out.yAxis) {
    const yAxisArr = (Array.isArray(out.yAxis) ? out.yAxis : [out.yAxis]) as Record<string, unknown>[]
    out.yAxis = yAxisArr.map((ax, idx) => {
      const boundSeries = seriesArr.filter(s => (s.yAxisIndex ?? 0) === idx)
      const isMoneyAxis = boundSeries.some(s => isMoney(String(s.name || '')))
      const formatterFn = isMoneyAxis ? fmtINR : fmtCount
      return {
        ...ax,
        axisLabel: {
          ...(typeof ax.axisLabel === 'object' && ax.axisLabel ? ax.axisLabel : {}),
          formatter: (val: number) => formatterFn(val),
        },
      }
    })
    // Unwrap single-element array back to object if original was object
    if (!Array.isArray(cfg.yAxis)) out.yAxis = (out.yAxis as unknown[])[0]
  }

  // ── Series: add data labels formatted dynamically based on series type ────
  out.series = seriesArr.map(s => {
    const type = String(s.type || '')
    const seriesMoney = isMoney(String(s.name || ''))
    const formatterFn = seriesMoney ? fmtINR : fmtCount

    if (type === 'bar' || type === 'line') {
      return {
        ...s,
        label: {
          show: true,
          position: 'top',
          fontSize: 10,
          color: '#475569',
          formatter: (params: { value: unknown }) => formatterFn(params.value),
          ...(typeof s.label === 'object' && s.label ? s.label : {}),
        },
      }
    }

    if (type === 'pie') {
      return {
        ...s,
        label: {
          ...(typeof s.label === 'object' && s.label ? s.label : {}),
          show: true,
          fontSize: 11,
          formatter: (params: { name: string; value: unknown; percent: number }) =>
            `{name|${params.name}}\n{val|${formatterFn(params.value)}}`,
          rich: {
            name: { fontSize: 11, color: '#334155', lineHeight: 18 },
            val:  { fontSize: 12, color: '#1e40af', fontWeight: 'bold', lineHeight: 18 },
          },
        },
        tooltip: {
          formatter: (params: { name: string; value: unknown; percent: number }) =>
            `${params.name}<br/><b>${formatterFn(params.value)}</b> (${params.percent?.toFixed(1)}%)`,
        },
      }
    }

    return s
  })

  // ── Tooltip: format series values axis-by-axis based on whether they look like money ──
  if (!['pie'].includes(String(seriesArr[0]?.type || ''))) {
    out.tooltip = {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      ...(typeof out.tooltip === 'object' && out.tooltip ? out.tooltip : {}),
      formatter: (params: unknown) => {
        const items = Array.isArray(params) ? params : [params as Record<string, unknown>]
        const title = (items[0] as Record<string, unknown>)?.axisValueLabel
          || (items[0] as Record<string, unknown>)?.name || ''
        const rows = items.map((p: Record<string, unknown>) => {
          const marker = String(p.marker || '')
          const name   = String(p.seriesName || p.name || '')
          const val    = p.value
          const seriesMoney = isMoney(name)
          const fmt    = seriesMoney ? fmtINR(val) : fmtCount(val)
          return `${marker} ${name}: <b>${fmt}</b>`
        })
        return `<div style="font-size:12px">${title ? `<b>${title}</b><br/>` : ''}${rows.join('<br/>')}</div>`
      },
    }
  }

  // ── Toolbox: Add interactive tools (export, zoom, restore) ───────────────
  out.toolbox = {
    show: true,
    right: '5%',
    top: '2%',
    feature: {
      saveAsImage: { show: true, title: 'Save' },
      dataZoom: { show: ['bar', 'line', 'scatter'].includes(String(seriesArr[0]?.type || '')) },
      restore: { show: true, title: 'Reset' },
    }
  }

  // ── Global style ───────────────────────────────────────────────────────────
  // Use proper background color for export (not transparent)
  out.backgroundColor = '#ffffff'
  out.animation = true
  out.animationDuration = 800
  return out
}

// ─── Export functions ───────────────────────────────────────────────────────────

function downloadChartAsImage(chartInstance: any, filename: string, theme: 'light' | 'dark') {
  const url = chartInstance.getDataURL({
    type: 'png',
    pixelRatio: 2, // Higher quality
    backgroundColor: theme === 'dark' ? '#1e293b' : '#ffffff'
  })

  const link = document.createElement('a')
  link.download = `${filename}.png`
  link.href = url
  link.click()
}

function exportTableToCSV(columns: string[], rows: Record<string, unknown>[], filename: string) {
  // Create CSV content
  const csvRows: string[] = []

  // Header row
  csvRows.push(columns.map(c => c.replace(/_/g, ' ')).join(','))

  // Data rows
  for (const row of rows) {
    const values = columns.map(col => {
      const val = row[col]
      // Escape quotes and wrap in quotes if contains comma
      const strVal = String(val ?? '')
      if (strVal.includes(',') || strVal.includes('"') || strVal.includes('\n')) {
        return `"${strVal.replace(/"/g, '""')}"`
      }
      return strVal
    })
    csvRows.push(values.join(','))
  }

  const csvContent = csvRows.join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `${filename}.csv`
  link.click()
}

// ─── Components ───────────────────────────────────────────────────────────────

export const ChartRenderer: React.FC<ChartRendererProps> = ({
  vizConfig, vizType, columns = [], rows = [], height = '400px', theme = 'light', role
}) => {
  const chartRef = useRef<any>(null)

  if (!vizConfig || vizType === null) return null

  if (vizType === 'table' || vizConfig.type === 'table') {
    if (role === 'non_tech_user') {
      return (
        <div className={`p-6 rounded-xl border text-center ${
          theme === 'dark' ? 'bg-zinc-900 border-zinc-800 text-zinc-400' : 'bg-zinc-50 border-zinc-200 text-zinc-600'
        }`}>
          <p className="text-sm font-semibold mb-1">📊 Detail Table Hidden</p>
          <p className="text-xs">Underlying technical data tables are hidden for Non-tech Users. Please switch your role to Team Member or Business Analyst to view details.</p>
        </div>
      )
    }
    return <DataTable columns={columns} rows={rows} theme={theme} />
  }

  const option = useMemo(() => {
    const patched = patchConfig(vizConfig)
    // Update background based on theme
    patched.backgroundColor = theme === 'dark' ? '#1e293b' : '#ffffff'
    return patched
  }, [vizConfig, theme])

  const onChartClick = (params: any) => {
    console.log('Chart clicked:', params.name, params.value)
  }

  const handleExportChart = () => {
    if (chartRef.current) {
      const chartInstance = chartRef.current.getEchartsInstance()
      const title = String(vizConfig.title || vizConfig.text || 'chart')
      downloadChartAsImage(chartInstance, title.replace(/[^a-z0-9]/gi, '_'), theme)
    }
  }

  return (
    <div className={`w-full rounded-xl border shadow-sm transition-all hover:shadow-md ${
      theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'
    }`}>
      {/* Export button */}
      <div className="flex justify-end p-2">
        <button
          onClick={handleExportChart}
          className="px-3 py-1.5 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors ${
            theme === 'dark'
              ? 'bg-slate-700 text-slate-200 hover:bg-slate-600'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Export PNG
        </button>
      </div>

      <ReactECharts
        ref={chartRef}
        option={option}
        style={{ height, width: '100%' }}
        opts={{ renderer: 'canvas' }}
        onEvents={{ 'click': onChartClick }}
        notMerge
      />
    </div>
  )
}

// ─── Data table ───────────────────────────────────────────────────────────────

const DataTable: React.FC<{
  columns: string[]
  rows: Record<string, unknown>[]
  theme?: 'light' | 'dark'
}> = ({ columns, rows, theme = 'light' }) => {
  if (!columns.length) return null

  const handleExportCSV = () => {
    const title = `data_export_${new Date().toISOString().split('T')[0]}`
    exportTableToCSV(columns, rows, title)
  }

  return (
    <div className={`w-full rounded-xl border shadow-sm ${
      theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'
    }`}>
      {/* Export button */}
      <div className="flex justify-end p-2">
        <button
          onClick={handleExportCSV}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors ${
            theme === 'dark'
              ? 'bg-slate-700 text-slate-200 hover:bg-slate-600'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Export CSV
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className={`border-b ${
            theme === 'dark' ? 'bg-slate-700 border-slate-600' : 'bg-slate-50 border-slate-200'
          }`}>
            <tr>
              {columns.map(col => (
                <th key={col} className={`px-4 py-3 font-semibold whitespace-nowrap capitalize ${
                  theme === 'dark' ? 'text-slate-200' : 'text-slate-700'
                }`}>
                  {col.replace(/_/g, ' ')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 200).map((row, i) => (
              <tr key={i} className={`border-b ${
                theme === 'dark'
                  ? i % 2 === 0 ? 'bg-slate-800' : 'bg-slate-750 border-slate-700'
                  : i % 2 === 0 ? 'bg-white' : 'bg-slate-50'
              }`}>
                {columns.map(col => {
                  const raw = row[col]
                  const formatted = autoFormatValue(col, raw)
                  const isRupee = String(formatted).startsWith('₹')
                  return (
                    <td
                      key={col}
                      className={`px-4 py-2 whitespace-nowrap max-w-xs truncate ${
                        isRupee
                          ? theme === 'dark' ? 'text-emerald-400 font-semibold text-right tabular-nums' : 'text-emerald-700 font-semibold text-right tabular-nums'
                          : theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
                      }`}
                    >
                      {indianiseCurrencyText(String(formatted))}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 200 && (
        <div className={`px-4 py-2 text-xs border-t ${
          theme === 'dark' ? 'text-slate-400 bg-slate-700 border-slate-600' : 'text-slate-500 bg-slate-50 border-slate-200'
        }`}>
          Showing 200 of {rows.length.toLocaleString('en-IN')} rows
        </div>
      )}
    </div>
  )
}
