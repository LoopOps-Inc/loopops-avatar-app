import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { setLocale } from '@/i18n';
import { UIPayloadRenderer } from './UIPayloadRenderer';

describe('UIPayloadRenderer', () => {
  it('renders portfolio summary and attribution cards', () => {
    setLocale('es');
    render(
      <UIPayloadRenderer
        components={[
          {
            type: 'portfolio_summary',
            payload: {
              as_of: '2026-08-31',
              market_value: { amount: '4,187,203.55', currency: 'MXN' },
              period_return_pct: 0.87,
              period: 'MTD',
            },
          },
          {
            type: 'attribution_bars',
            payload: {
              contributions: [{ sleeve: 'Deuda gubernamental', bps: 118 }],
            },
          },
        ]}
      />,
    );

    expect(screen.getByText('Resumen de portafolio')).toBeInTheDocument();
    expect(screen.getByText(/\$4,187,203\.55/)).toBeInTheDocument();
    expect(screen.getByText('Deuda gubernamental')).toBeInTheDocument();
  });
});
