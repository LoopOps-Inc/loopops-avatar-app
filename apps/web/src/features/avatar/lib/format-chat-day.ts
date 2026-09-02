const DAY_MS = 86_400_000;

function startOfDay(timestamp: number): number {
  const date = new Date(timestamp);
  date.setHours(0, 0, 0, 0);
  return date.getTime();
}

/** Relative day label for in-transcript separators (Hoy, Ayer, or a full date). */
export function formatChatDayLabel(
  timestamp: number,
  locale: string,
  today: string,
  yesterday: string,
): string {
  const todayStart = startOfDay(Date.now());
  const diffDays = Math.round((todayStart - startOfDay(timestamp)) / DAY_MS);
  if (diffDays === 0) return today;
  if (diffDays === 1) return yesterday;
  const date = new Date(timestamp);
  return new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'es-MX', {
    day: 'numeric',
    month: 'long',
    year: date.getFullYear() === new Date().getFullYear() ? undefined : 'numeric',
  }).format(date);
}

const CHAT_TIME_ZONE = 'America/Mexico_City';

/** Absolute start label for the sheet header, e.g. "01/08/2026 10:00pm". */
export function formatChatStartedAt(timestamp: number, locale: string): string {
  const parts = new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'es-MX', {
    timeZone: CHAT_TIME_ZONE,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).formatToParts(new Date(timestamp));

  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? '';

  const dayPeriod = get('dayPeriod').toLowerCase().replace(/\./g, '').replace(/\s/g, '');

  return `${get('day')}/${get('month')}/${get('year')} ${get('hour')}:${get('minute')}${dayPeriod}`;
}
