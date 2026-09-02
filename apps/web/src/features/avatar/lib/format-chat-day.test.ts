import { describe, expect, it, vi } from 'vitest';
import { formatChatDayLabel, formatChatStartedAt } from './format-chat-day';

describe('formatChatDayLabel', () => {
  it('returns today and yesterday labels relative to the current day', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-09-01T12:00:00'));

    expect(formatChatDayLabel(Date.parse('2026-09-01T08:00:00'), 'es', 'Hoy', 'Ayer')).toBe('Hoy');
    expect(formatChatDayLabel(Date.parse('2026-08-31T20:00:00'), 'es', 'Hoy', 'Ayer')).toBe('Ayer');

    vi.useRealTimers();
  });

  it('formats older dates with month and day', () => {
    expect(formatChatDayLabel(Date.parse('2026-08-28T10:00:00'), 'es', 'Hoy', 'Ayer')).toBe(
      '28 de agosto',
    );
  });

  it('formats thread start as dd/mm/yyyy h:mmam/pm', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-09-01T12:00:00'));

    expect(formatChatStartedAt(Date.parse('2026-08-02T04:00:00.000Z'), 'es')).toBe(
      '01/08/2026 10:00pm',
    );

    vi.useRealTimers();
  });
});
