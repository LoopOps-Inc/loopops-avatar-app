import type { UIComponent } from '@loopops/contracts';
import type { AdvisorService, AdvisorStreamEvent } from '../types';

type MockTurn = {
  speech: string;
  uiPayload: UIComponent[];
};

type CreateMockAdvisorServiceOptions = {
  /** Delay between streamed events. Set 0 in tests. */
  delayMs?: number;
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

const attributionTurn: MockTurn = {
  speech:
    'La atribución del mes la domina la deuda gubernamental con una contribución positiva importante. La renta variable local restó. Encuentra las barras exactas en la tarjeta.',
  uiPayload: [portfolioTurn.uiPayload[1]],
};

const quoteTurn: MockTurn = {
  speech:
    'El dólar cotiza estable hoy, sin movimientos relevantes para tus posiciones. Te comparto el nivel exacto en la tarjeta.',
  uiPayload: [
    {
      type: 'market_quote',
      payload: {
        symbol: 'USDMXN',
        value: '18.42',
        change_pct: -0.15,
        as_of: PORTFOLIO_AS_OF,
      },
      source: 'get_market_quote',
    },
  ],
};

const newsTurn: MockTurn = {
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
};

const fallbackTurn: MockTurn = {
  speech:
    'Por ahora puedo apoyarte con el desempeño de tu portafolio, su atribución por sleeve, noticias de mercado o el tipo de cambio del dólar. Prueba con alguna de esas.',
  uiPayload: [
    {
      type: 'warning_banner',
      payload: {
        severity: 'info',
        message: 'Demo con datos de ejemplo. Intenciones disponibles: portafolio, atribución, noticias y tipo de cambio.',
      },
    },
  ],
};

const greetingTurn: MockTurn = {
  speech:
    'Hola, soy Tino, tu asesor digital de Actinver. Pregúntame por el desempeño de tu portafolio o el contexto de mercado.',
  uiPayload: [],
};

const INTENTS: Array<{ pattern: RegExp; turn: MockTurn }> = [
  { pattern: /atribucion|contribucion|de donde|sleeve/, turn: attributionTurn },
  { pattern: /portafolio|portfolio|como va|rendimiento|desempeno|performance/, turn: portfolioTurn },
  { pattern: /dolar|usdmxn|tipo de cambio|exchange|cotiz/, turn: quoteTurn },
  { pattern: /noticia|news|mercado|banxico|peso|contexto/, turn: newsTurn },
];

function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '');
}

function matchIntent(message: string): MockTurn {
  const normalized = normalize(message);
  const intent = INTENTS.find(({ pattern }) => pattern.test(normalized));
  return intent ? intent.turn : fallbackTurn;
}

function chunkSpeech(speech: string): string[] {
  return speech.match(/[^ ]+(?: [^ ]+)*/g) ?? [];
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Frontend mock of the advisor backend: fixtures mirror the mock tools in
 * apps/agent/README.md and honor the split-channel invariant (exact figures
 * live in ui_payload only, never in speech). When the real API lands, an
 * SSE-backed AdvisorService replaces this implementation with the same shape.
 */
export function createMockAdvisorService(
  options: CreateMockAdvisorServiceOptions = {},
): AdvisorService {
  const delayMs = options.delayMs ?? 40;
  let turnCount = 0;

  async function* streamTurn(turn: MockTurn): AsyncIterable<AdvisorStreamEvent> {
    turnCount += 1;
    for (const chunk of chunkSpeech(turn.speech)) {
      yield { event: 'token', data: { text: `${chunk} ` } };
      if (delayMs > 0) await sleep(delayMs);
    }
    for (const ui of turn.uiPayload) {
      yield { event: 'ui', data: ui };
      if (delayMs > 0) await sleep(delayMs);
    }
    yield {
      event: 'done',
      data: {
        turn_id: `mock-turn-${turnCount}`,
        evidence_id: 'mock-evidence',
        service_type: 'no_asesorado',
      },
    };
  }

  return {
    sendTurn: (message) => streamTurn(matchIntent(message)),
    sendGreeting: () => streamTurn(greetingTurn),
  };
}
