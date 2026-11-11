export function parseApiDate(value) {
  if (!value) {
    return null
  }

  if (value instanceof Date) {
    return value
  }

  if (typeof value === 'string') {
    const trimmed = value.trim()
    const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed)
    return new Date(hasTimezone ? trimmed : `${trimmed}Z`)
  }

  return new Date(value)
}

export function formatApiDate(value, options) {
  const date = parseApiDate(value)
  if (!date || Number.isNaN(date.getTime())) {
    return ''
  }

  return new Intl.DateTimeFormat('zh-CN', options).format(date)
}
