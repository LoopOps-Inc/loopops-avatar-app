import type { UIComponent } from '@loopops/contracts';

export type MockTurn = {
  speech: string;
  uiPayload: UIComponent[];
};

const PORTFOLIO_AS_OF = '2026-08-31';

const portfolioTurn: MockTurn = {
  speech:
    'Tu portafolio cerró el mes ligeramente al alza. Casi todo el movimiento vino de deuda gubernamental, compensando la caída de la renta variable local. Te dejo el desglose en pantalla.',
  uiPayload: [
    {
      type: 'portfolio_summary',
      payload: {
        as_of: PORTFOLIO_AS_OF,
        market_value: { amount: '4187203.55', currency: 'MXN' },
        period_return_pct: 0.87,
        period: 'MTD',
      },
      as_of: PORTFOLIO_AS_OF,
      source: 'get_portfolio_performance',
    },
    {
      type: 'attribution_bars',
      payload: {
        contributions: [
          { sleeve: 'Deuda gubernamental', bps: 118 },
          { sleeve: 'Renta variable local', bps: -52 },
        ],
      },
      as_of: PORTFOLIO_AS_OF,
      source: 'get_portfolio_attribution',
    },
  ],
};

export const MOCK_TURNS = {
  portfolio: portfolioTurn,
  attribution: {
    speech:
      'La atribución del mes la domina la deuda gubernamental con una contribución positiva importante. La renta variable local restó. Encuentra las barras exactas en la tarjeta.',
    uiPayload: [portfolioTurn.uiPayload[1]],
  } satisfies MockTurn,
  quote: {
    speech:
      'El dólar cotiza estable hoy, sin movimientos relevantes para tus posiciones. Te comparto el nivel exacto en la tarjeta.',
    uiPayload: [
      {
        type: 'market_quote',
        payload: { symbol: 'USDMXN', value: '18.42', change_pct: -0.15, as_of: PORTFOLIO_AS_OF },
        source: 'get_market_quote',
      },
    ],
  } satisfies MockTurn,
  news: {
    speech:
      'Hay dos notas relevantes hoy: Banxico sostuvo su postura de tasas en su reunión y el peso cotiza con estabilidad apoyado en flujos externos. Te dejo las fuentes.',
    uiPayload: [
      {
        type: 'citations',
        payload: {
          items: [
            {
              title: 'Banxico mantiene la tasa de referencia en su reunión de agosto',
              source: 'Banxico',
              published: '2026-08-28',
            },
            {
              title: 'El peso mexicano avanza apoyado por flujos externos',
              source: 'El Economista',
              published: '2026-08-30',
            },
          ],
        },
        source: 'search_market_news',
      },
    ],
  } satisfies MockTurn,
  fallback: {
    speech:
      'Por ahora puedo apoyarte con el desempeño de tu portafolio, su atribución por sleeve, noticias de mercado o el tipo de cambio del dólar. Prueba con alguna de esas.',
    uiPayload: [
      {
        type: 'warning_banner',
        payload: {
          severity: 'info',
          message:
            'Demo con datos de ejemplo. Intenciones disponibles: portafolio, atribución, noticias y tipo de cambio.',
        },
      },
    ],
  } satisfies MockTurn,
  greeting: {
    speech:
      'Hola, soy Tino, tu asesor digital de Actinver. Pregúntame por el desempeño de tu portafolio o el contexto de mercado.',
    uiPayload: [],
  } satisfies MockTurn,
};

/** Intent patterns (matched on accent-insensitive lowercase text). */
export const INTENT_PATTERNS: Array<{ pattern: RegExp; turn: MockTurn }> = [
  { pattern: /atribucion|contribucion|de donde|sleeve/, turn: MOCK_TURNS.attribution },
  { pattern: /portafolio|portfolio|como va|rendimiento|desempeno|performance/, turn: MOCK_TURNS.portfolio },
  { pattern: /dolar|usdmxn|tipo de cambio|exchange|cotiz/, turn: MOCK_TURNS.quote },
  { pattern: /noticia|news|mercado|banxico|peso|contexto/, turn: MOCK_TURNS.news },
];
