/**
 * ChartRenderer — renders Apache ECharts option objects from the backend.
 * Applies ₹ formatting directly on axis labels, data labels, and tooltips.
 */
import React, { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { autoFormatValue, indianiseCurrencyText } from '../../lib/formatters'

interface ChartRendererProps {
  vizConfig: Record<string, unknown>
  vizType: string | null
  columns?: string[]
  rows?: Record<string, unknown>[]
  height?: string
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
  const moneyChart = seriesLooksLikeMoney(seriesArr)

  // ── Y-axis: show ₹ on all tick labels ─────────────────────────────────────
  if (out.yAxis && moneyChart) {
    const yAxis = (Array.isArray(out.yAxis) ? out.yAxis : [out.yAxis]) as Record<string, unknown>[]
    out.yAxis = yAxis.map(ax => ({
      ...ax,
      axisLabel: {
        ...(typeof ax.axisLabel === 'object' && ax.axisLabel ? ax.axisLabel : {}),
        formatter: (val: number) => fmtINR(val),
      },
    }))
    // Unwrap single-element array back to object if original was object
    if (!Array.isArray(cfg.yAxis)) out.yAxis = (out.yAxis as unknown[])[0]
  }

  // ── Series: add data labels directly on bars/lines/pie slices ─────────────
  out.series = seriesArr.map(s => {
    const type = String(s.type || '')
    const seriesMoney = moneyChart || isMoney(String(s.name || ''))

    if ((type === 'bar' || type === 'line') && seriesMoney) {
      return {
        ...s,
        label: {
          show: true,
          position: type === 'bar' ? 'top' : 'top',
          fontSize: 10,
          color: '#475569',
          formatter: (params: { value: unknown }) => fmtINR(params.value),
          ...(typeof s.label === 'object' && s.label ? s.label : {}),
          // Always override formatter for money
        },
      }
    }

    if (type === 'pie' && seriesMoney) {
      return {
        ...s,
        label: {
          ...(typeof s.label === 'object' && s.label ? s.label : {}),
          show: true,
          fontSize: 11,
          formatter: (params: { name: string; value: unknown; percent: number }) =>
            `{name|${params.name}}\n{val|${fmtINR(params.value)}}`,
          rich: {
            name: { fontSize: 11, color: '#334155', lineHeight: 18 },
            val:  { fontSize: 12, color: '#1e40af', fontWeight: 'bold', lineHeight: 18 },
          },
        },
        // Pie tooltip
        tooltip: {
          formatter: (params: { name: string; value: unknown; percent: number }) =>
            `${params.name}<br/><b>${fmtINR(params.value)}</b> (${params.percent?.toFixed(1)}%)`,
        },
      }
    }

    return s
  })

  // ── Tooltip: show ₹ on axis-trigger tooltips (bar/line) ───────────────────
  if (moneyChart && !['pie'].includes(String(seriesArr[0]?.type || ''))) {
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
          const fmt    = moneyChart ? fmtINR(val) : String(val)
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
  out.backgroundColor = 'transparent'
  out.animation = true
  out.animationDuration = 800
  return out
}

// ─── Components ───────────────────────────────────────────────────────────────

export const ChartRenderer: React.FC<ChartRendererProps> = ({
  vizConfig, vizType, columns = [], rows = [], height = '400px'
}) => {
  if (!vizConfig || vizType === null) return null

  if (vizType === 'table' || vizConfig.type === 'table') {
    return <DataTable columns={columns} rows={rows} />
  }

  const option = useMemo(() => patchConfig(vizConfig), [vizConfig])

  const onChartClick = (params: any) => {
    console.log('Chart clicked:', params.name, params.value)
    // Placeholder for Phase 4.3 drill-down logic
  }

  return (
    <div className="w-full rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:shadow-md">
      <ReactECharts
        option={option}
        style={{ height, width: '100%' }}
        opts={{ renderer: 'canvas' }}
        onEvents={{
          'click': onChartClick
        }}
        notMerge
      />
    </div>
  )
}

// ─── Data table ───────────────────────────────────────────────────────────────

const DataTable: React.FC<{ columns: string[]; rows: Record<string, unknown>[] }> = ({ columns, rows }) => {
  if (!columns.length) return null
  return (
    <div className="w-full overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-sm text-left">
        <thead className="bg-slate-50 border-b border-slate-200">
          <tr>
            {columns.map(col => (
              <th key={col} className="px-4 py-3 font-semibold text-slate-700 whitespace-nowrap capitalize">
                {col.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 200).map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
              {columns.map(col => {
                const raw = row[col]
                const formatted = autoFormatValue(col, raw)
                const isRupee = String(formatted).startsWith('₹')
                return (
                  <td
                    key={col}
                    className={`px-4 py-2 whitespace-nowrap max-w-xs truncate ${
                      isRupee ? 'text-emerald-700 font-semibold text-right tabular-nums' : 'text-slate-600'
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
      {rows.length > 200 && (
        <div className="px-4 py-2 text-xs text-slate-500 bg-slate-50 border-t">
          Showing 200 of {rows.length.toLocaleString('en-IN')} rows
        </div>
      )}
    </div>
  )
}
