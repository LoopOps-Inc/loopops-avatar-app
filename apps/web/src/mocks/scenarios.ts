import type { UIComponent } from '@loopops/contracts';
import type { SuggestionChip } from './schemas';
import {
  defaultChips,
  fernandaAdvisor,
  portfolioAttribution,
  rodrigoProducts,
  rodrigoUser,
  explorarSummary,
  getIdleCashAccount,
} from './fixtures/rodrigo';

export type MockScenarioResult = {
  speech: string;
  uiPayload: UIComponent[];
  chips?: SuggestionChip[];
};

type ScenarioMatcher = {
  id: string;
  match: (message: string) => boolean;
  build: () => MockScenarioResult;
};

function formatMoney(amount: string): string {
  const num = Number.parseFloat(amount.replace(/,/g, ''));
  return num.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const scenarios: ScenarioMatcher[] = [
  {
    id: 'portfolio_inspect',
    match: (m) =>
      /portafolio|cómo va|como va|rendimiento|posición|posicion/i.test(m) &&
      !/baj[oó]|movi[oó]/i.test(m),
    build: () => ({
      speech:
        'Su portafolio cerró el mes con una ligera caída. La mayor parte del movimiento vino de su posición en renta variable. Le dejo el resumen y el desglose en pantalla.',
      uiPayload: [
        {
          type: 'portfolio_summary',
          as_of: explorarSummary.asOf,
          source: 'tool:get_portfolio_performance',
          payload: {
            as_of: explorarSummary.asOf,
            market_value: explorarSummary.marketValue,
            period_return_pct: explorarSummary.periodReturnPct,
            period: explorarSummary.period,
          },
        },
        {
          type: 'attribution_bars',
          source: 'tool:get_portfolio_attribution',
          payload: {
            contributions: portfolioAttribution.items.map((item) => ({
              sleeve: item.label,
              bps: item.contributionBps,
            })),
          },
        },
      ],
    }),
  },
  {
    id: 'why_down',
    match: (m) => /por qué baj|porque baj|baj[oó]|movi[oó]|ca[ií]da/i.test(m),
    build: () => ({
      speech:
        'Su portafolio bajó 2.4% este mes. Cerca del 80% del movimiento viene de NAFTRAC, en línea con la debilidad del mercado accionario local. Contra su horizonte de tres años, el movimiento sigue dentro de lo esperado para un perfil moderado.',
      uiPayload: [
        {
          type: 'attribution_bars',
          source: 'tool:get_portfolio_attribution',
          payload: {
            contributions: portfolioAttribution.items.map((item) => ({
              sleeve: item.label,
              bps: item.contributionBps,
            })),
          },
        },
        {
          type: 'citations',
          payload: {
            items: portfolioAttribution.items
              .filter((i) => i.citationTitle)
              .map((i) => ({
                title: i.citationTitle ?? i.reason,
                url: i.citationUrl,
                source: i.label,
              })),
          },
        },
      ],
    }),
  },
  {
    id: 'idle_cash',
    match: (m) => /parado|idle|tres millones|3\s*millones|efectivo|cuenta/i.test(m),
    build: () => {
      const cash = getIdleCashAccount();
      return {
        speech: `Tiene ${formatMoney(cash.available.amount)} pesos disponibles en su cuenta desde marzo. Ese monto pierde poder adquisitivo frente a la inflación. Para orientarle bien, necesito dos datos: ¿para cuándo podría necesitar el dinero y con qué fin?`,
        uiPayload: [
          {
            type: 'warning_banner',
            payload: {
              severity: 'info',
              message: `Saldo disponible al ${cash.asOf}. Cifra informativa, no es recomendación.`,
            },
          },
        ],
        chips: defaultChips,
      };
    },
  },
  {
    id: 'products',
    match: (m) => /etf|fondo|renta fija|instrumento|producto|invertir/i.test(m),
    build: () => ({
      speech:
        'Estos son instrumentos de deuda de bajo riesgo en la casa. También muestro uno no elegible para su perfil, con la razón. Puede pedirme una comparación o una simulación.',
      uiPayload: [
        {
          type: 'warning_banner',
          payload: {
            severity: 'info',
            message:
              'Listado filtrado con fines educativos. Una sugerencia personalizada requiere validación de perfil.',
          },
        },
        {
          type: 'citations',
          payload: {
            items: rodrigoProducts.map((p) => ({
              title: `${p.name}${p.eligible ? '' : ' (no elegible)'}`,
              source: p.type,
            })),
          },
        },
      ],
      chips: defaultChips,
    }),
  },
  {
    id: 'blocked_structured',
    match: (m) => /estructurad|nota|multi.activo/i.test(m),
    build: () => ({
      speech: `La nota estructurada no es congruente con su perfil moderado: complejidad alta y riesgo alto. Se lo explico con detalle y, si lo prefiere, le agendo con ${fernandaAdvisor.firstName}, su asesora.`,
      uiPayload: [
        {
          type: 'warning_banner',
          payload: {
            severity: 'warning',
            message:
              rodrigoProducts.find((p) => p.id === 'prod_nota_estructurada')?.ineligibilityReason ??
              'Producto no apto para su perfil.',
          },
        },
      ],
    }),
  },
  {
    id: 'market',
    match: (m) => /peso|dólar|dolar|mercado|banxico|tasa|tipo de cambio/i.test(m),
    build: () => ({
      speech:
        'El peso se ha fortalecido ligeramente en la sesión. Las noticias recientes giran en torno a Banxico y al sentimiento global. Revise las fuentes en pantalla.',
      uiPayload: [
        {
          type: 'warning_banner',
          payload: {
            severity: 'info',
            message: 'Cotización con retraso. No constituye asesoría de inversiones.',
          },
        },
        {
          type: 'citations',
          source: 'tool:search_market_news',
          payload: {
            items: [
              {
                title: 'Banxico mantiene la tasa de referencia en 10.00%',
                url: 'https://www.banxico.org.mx/',
                published: '2026-08-28',
                source: 'Banxico',
              },
              {
                title: 'Peso gana terreno ante menor aversión al riesgo',
                url: 'https://www.elfinanciero.com.mx/',
                published: '2026-09-01',
                source: 'El Financiero',
              },
            ],
          },
        },
      ],
    }),
  },
];

export function resolveMockScenario(message: string): MockScenarioResult {
  const hit = scenarios.find((s) => s.match(message));
  if (hit) return hit.build();

  return {
    speech: `${rodrigoUser.firstName}, por ahora puedo ayudarle con su portafolio, efectivo disponible, instrumentos de la casa o contexto de mercado. Pruebe preguntarme por qué bajó su portafolio o qué hacer con su efectivo parado.`,
    uiPayload: [
      {
        type: 'warning_banner',
        payload: {
          severity: 'info',
          message: 'Respuesta informativa. No constituye asesoría de inversiones.',
        },
      },
    ],
    chips: defaultChips,
  };
}

export { scenarios };
