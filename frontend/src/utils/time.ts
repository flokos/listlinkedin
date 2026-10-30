export type ExpiryTone = 'normal' | 'warning' | 'expired'

const DAY = 86_400_000
const HOUR = 3_600_000

/** Human expiry label and urgency for a list. "Soon" means under 3 days. */
export function expiryInfo(
  expiresAt: string,
  now = Date.now(),
): { label: string; tone: ExpiryTone } {
  const remaining = new Date(expiresAt).getTime() - now
  if (Number.isNaN(remaining)) return { label: 'Expiry unknown', tone: 'normal' }
  if (remaining <= 0) return { label: 'Expired', tone: 'expired' }
  const tone: ExpiryTone = remaining < 3 * DAY ? 'warning' : 'normal'
  if (remaining < HOUR) return { label: 'Expires in less than an hour', tone }
  // Hours below two days ("in 30 hours" beats a vague "in 1 day"), rounded days above.
  if (remaining < 2 * DAY) {
    const hours = Math.max(1, Math.floor(remaining / HOUR))
    return { label: `Expires in ${hours} hour${hours === 1 ? '' : 's'}`, tone }
  }
  const days = Math.round(remaining / DAY)
  return { label: `Expires in ${days} day${days === 1 ? '' : 's'}`, tone }
}

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
const dateOnly = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })

export const formatDateTime = (iso: string) => dateTime.format(new Date(iso))
export const formatDate = (iso: string) => dateOnly.format(new Date(iso))

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

/** "3 minutes ago", "yesterday"… */
export function timeAgo(iso: string, now = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000)
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ]
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit)
  }
  return 'just now'
}

/** The local calendar date of an instant, as a date input's value ("2026-11-03"). */
export function localDate(iso: string): string {
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** The last second of a local calendar date ("2026-11-03"), as an ISO instant. */
export function endOfDay(date: string): string {
  const [year, month, day] = date.split('-').map(Number)
  return new Date(year!, month! - 1, day!, 23, 59, 59).toISOString()
}
