/**
 * Indian number & currency formatters for Limese Analytics
 */

/** Format a number with Indian grouping — max Crore (no Arab/Kharab) */
export function formatIndianNumber(value: number): string {
  if (isNaN(value) || value === null) return '—'
  const abs = Math.abs(value)
  const sign = value < 0 ? '-' : ''

  // Cap at Crore — show e.g. ₹567.89 Cr for very large numbers
  if (abs >= 1_00_00_000) {
    return `${sign}${(abs / 1_00_00_000).toFixed(2)} Cr`
  }
  if (abs >= 1_00_000) {
    return `${sign}${(abs / 1_00_000).toFixed(2)} L`
  }
  if (abs >= 1_000) {
    return `${sign}${(abs / 1_000).toFixed(1)}K`
  }
  return `${sign}${abs.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

/** Format as Indian Rupee ₹ with crore/lakh suffix */
export function formatINR(value: number): string {
  return `₹${formatIndianNumber(value)}`
}

/**
 * Auto-detect if a string value looks like currency/money
 * and return formatted ₹ version. Otherwise return as-is.
 */
export function autoFormatValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return '—'

  const keyLower = key.toLowerCase()
  const isMoney = [
    'revenue', 'sales', 'subtotal', 'total', 'price', 'amount', 'cost',
    'mrp', 'sp', 'value', 'gross', 'earning', 'income', 'spend', 'profit',
    'loss', 'cogs', 'gmv', 'net', 'billing', 'invoice', 'order_price',
  ].some(k => keyLower.includes(k))

  const num = typeof value === 'number' ? value : parseFloat(String(value))

  if (isMoney && !isNaN(num) && Math.abs(num) > 100) {
    return formatINR(num)
  }

  if (!isNaN(num) && typeof value === 'number') {
    // Large round numbers in non-money columns — just format with Indian commas
    if (Math.abs(num) >= 1000) {
      return num.toLocaleString('en-IN', { maximumFractionDigits: 2 })
    }
    return String(Math.round(num * 100) / 100)
  }

  return String(value)
}

/**
 * Replace "$X" or "$ X" patterns in text with "₹X"
 * Also converts "USD" mentions to "INR"
 */
export function indianiseCurrencyText(text: string): string {
  return text
    .replace(/\$\s?([\d,]+(?:\.\d+)?)/g, (_, n) => {
      const num = parseFloat(n.replace(/,/g, ''))
      return formatINR(num)
    })
    .replace(/USD/g, 'INR')
    .replace(/\bUS\$/g, '₹')
}
