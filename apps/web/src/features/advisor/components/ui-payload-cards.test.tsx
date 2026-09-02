import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { UIComponent } from '@loopops/contracts';
import { UI_COMPONENT_TYPES } from '@loopops/contracts';
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

describe('closed component registry', () => {
  beforeEach(() => {
    setLocale('es');
  });

  it.each(UI_COMPONENT_TYPES)('has a renderer case for %s', (type) => {
    // An empty payload fails every schema, so a type WITH a case renders
    // nothing while a type WITHOUT one falls through to the unsupported card.
    render(<UIPayloadCards components={[{ type, payload: {} } as UIComponent]} />);

    expect(screen.queryByText(/Componente no soportado/)).not.toBeInTheDocument();
  });

  it('surfaces a type the client has not shipped instead of dropping it', () => {
    render(
      <UIPayloadCards components={[{ type: 'not_shipped_yet', payload: {} } as UIComponent]} />,
    );

    expect(screen.getByText(/Componente no soportado: not_shipped_yet/)).toBeInTheDocument();
  });
});

describe('real server payloads', () => {
  beforeEach(() => {
    setLocale('es');
  });

  // Captured verbatim from a live /v1/threads/{id}/messages SSE stream.
  const portfolioPositions: UIComponent = {
    type: 'portfolio_positions',
    payload: {
      as_of: '2026-09-02T11:21:46-06:00',
      total_market_value: { amount: '12650000.00', currency: 'MXN' },
      cash: { amount: '632500.00', currency: 'MXN' },
      liquid_pct: 1.0,
      positions: [
        {
          product_id: 'ACTIVAR-RV',
          name: 'Actinver Renta Variable México',
          asset_class: 'renta_variable_local',
          quantity: 1804859.1578,
          market_value: { amount: '4427500.00', currency: 'MXN' },
          cost_basis: { amount: '4176886.79', currency: 'MXN' },
          weight_pct: 35.0,
          currency: 'MXN',
        },
      ],
    },
    as_of: '2026-09-02T11:21:46-06:00',
    source: 'tool:get_portfolio_positions',
  };

  const cashSummary: UIComponent = {
    type: 'cash_summary',
    payload: {
      as_of: '2026-09-02T11:22:37-06:00',
      available: { amount: '556600.00', currency: 'MXN' },
      pending: { amount: '75900.00', currency: 'MXN' },
      settlements: [{ date: '2026-09-03', amount: { amount: '75900.00', currency: 'MXN' } }],
    },
    as_of: '2026-09-02T11:22:37-06:00',
    source: 'tool:get_cash_balance',
  };

  it('renders the positions the server actually sent', () => {
    render(<UIPayloadCards components={[portfolioPositions]} />);

    expect(screen.getByText('Actinver Renta Variable México')).toBeInTheDocument();
    expect(screen.getByText(/4,427,500/)).toBeInTheDocument();
    expect(screen.getByText(/Peso 35.0%/)).toBeInTheDocument();
    expect(screen.queryByText(/Componente no soportado/)).not.toBeInTheDocument();
  });

  it('renders the cash balance the server actually sent', () => {
    render(<UIPayloadCards components={[cashSummary]} />);

    expect(screen.getByText('Disponible')).toBeInTheDocument();
    expect(screen.getByText(/556,600/)).toBeInTheDocument();
    // Once as the pending balance, once as the 2026-09-03 settlement.
    expect(screen.getAllByText(/75,900/)).toHaveLength(2);
    expect(screen.getByText('Liquidaciones')).toBeInTheDocument();
  });
});
