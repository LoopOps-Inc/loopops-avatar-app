export const moneyFormatter = new Intl.NumberFormat('es-MX', {
  style: 'currency',
  currency: 'MXN',
  maximumFractionDigits: 2,
});

/** Formats an ISO date (yyyy-mm-dd) as a short es-MX date, ISO on failure. */
export function formatDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric' });
}
