import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { UIComponent } from '@loopops/contracts';
import { setLocale } from '@/i18n';
import { UIPayloadCards } from './ui-payload-cards';

const portfolioSummary: UIComponent = {
  type: 'portfolio_summary',
  payload: {
    as_of: '2026-08-31',
    market_value: { amount: '4187203.55', currency: 'MXN' },
    period_return_pct: 0.87,
    period: 'MTD',
  },
};

const attributionBars: UIComponent = {
  type: 'attribution_bars',
  payload: {
    contributions: [
      { sleeve: 'Deuda gubernamental', bps: 118 },
      { sleeve: 'Renta variable local', bps: -52 },
    ],
  },
};

const marketQuote: UIComponent = {
  type: 'market_quote',
  payload: { symbol: 'USDMXN', value: '18.42', change_pct: -0.15 },
};

const citations: UIComponent = {
  type: 'citations',
  payload: {
    items: [
      {
        title: 'Banxico mantiene la tasa de referencia en su reunión de agosto',
        source: 'Banxico',
        published: '2026-08-28',
      },
    ],
  },
};

const warningBanner: UIComponent = {
  type: 'warning_banner',
  payload: { severity: 'info', message: 'Demo con datos de ejemplo.' },
};

describe('UIPayloadCards', () => {
  beforeEach(() => {
    setLocale('es');
  });

  it('renders the portfolio summary with formatted money and return badge', () => {
    render(<UIPayloadCards components={[portfolioSummary]} />);
    expect(screen.getByText('Valor de mercado')).toBeInTheDocument();
    expect(screen.getByText(/4,187,203/)).toBeInTheDocument();
    expect(screen.getByText('+0.87% MTD')).toBeInTheDocument();
  });

  it('renders negative returns with the error tone', () => {
    render(
      <UIPayloadCards
        components={[
          {
            ...portfolioSummary,
            payload: { ...portfolioSummary.payload, period_return_pct: -1.2 },
          },
        ]}
      />,
    );
    expect(screen.getByText('-1.20% MTD')).toBeInTheDocument();
  });

  it('renders attribution bars with sleeves and bps', () => {
    render(<UIPayloadCards components={[attributionBars]} />);
    expect(screen.getByText('Contribuciones')).toBeInTheDocument();
    expect(screen.getByText('Deuda gubernamental')).toBeInTheDocument();
    expect(screen.getByText('+118 bp')).toBeInTheDocument();
    expect(screen.getByText('-52 bp')).toBeInTheDocument();
  });

  it('renders the market quote with symbol and value', () => {
    render(<UIPayloadCards components={[marketQuote]} />);
    expect(screen.getByText('USDMXN')).toBeInTheDocument();
    expect(screen.getByText('18.42')).toBeInTheDocument();
    expect(screen.getByText('-0.15% hoy')).toBeInTheDocument();
  });

  it('renders citations with source and date', () => {
    render(<UIPayloadCards components={[citations]} />);
    expect(screen.getByText('Fuentes')).toBeInTheDocument();
    expect(screen.getByText(/Banxico mantiene la tasa/)).toBeInTheDocument();
  });

  it('renders the warning banner as a status region', () => {
    render(<UIPayloadCards components={[warningBanner]} />);
    expect(screen.getByRole('status')).toHaveTextContent('Demo con datos de ejemplo.');
  });

  it('renders nothing when there are no components', () => {
    const { container } = render(<UIPayloadCards components={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
