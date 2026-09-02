import type { UIComponent } from '@loopops/contracts';
import {
  AttributionBarsPayloadSchema,
  CitationsPayloadSchema,
  MarketQuotePayloadSchema,
  PortfolioSummaryPayloadSchema,
  WarningBannerPayloadSchema,
} from '@loopops/contracts';
import type { ZodType } from 'zod';
import { AttributionChart, PortfolioSummaryCard } from './cards/PortfolioCards';
import { CitationList, WarningBanner } from './cards/SupportCards';
import { MarketQuoteCard } from './ui-payload-cards';

const MARKET_QUOTE_BODY_STYLES =
  'border-outline bg-surface rounded-xs flex w-full flex-col gap-2 border px-3 py-2.5 text-left';

type UIPayloadRendererProps = {
  components: UIComponent[];
};

function matchPayload<T>(schema: ZodType<T>, component: UIComponent): T | null {
  const result = schema.safeParse(component.payload);
  return result.success ? result.data : null;
}

export function UIPayloadRenderer({ components }: UIPayloadRendererProps) {
  return (
    <div className="flex flex-col gap-3">
      {components.map((component, index) => {
        switch (component.type) {
          case 'portfolio_summary': {
            const payload = matchPayload(PortfolioSummaryPayloadSchema, component);
            return payload ? (
              <PortfolioSummaryCard
                key={`portfolio-${index}`}
                payload={payload}
                asOf={component.as_of ?? undefined}
              />
            ) : null;
          }
          case 'attribution_bars': {
            const payload = matchPayload(AttributionBarsPayloadSchema, component);
            return payload ? (
              <AttributionChart key={`attribution-${index}`} payload={payload} />
            ) : null;
          }
          case 'warning_banner': {
            const payload = matchPayload(WarningBannerPayloadSchema, component);
            return payload ? <WarningBanner key={`warning-${index}`} payload={payload} /> : null;
          }
          case 'citations': {
            const payload = matchPayload(CitationsPayloadSchema, component);
            return payload ? <CitationList key={`citations-${index}`} payload={payload} /> : null;
          }
          case 'market_quote': {
            const payload = matchPayload(MarketQuotePayloadSchema, component);
            return payload ? (
              <div key={`market-${index}`} className={MARKET_QUOTE_BODY_STYLES}>
                <MarketQuoteCard payload={payload} />
              </div>
            ) : null;
          }
          default:
            return null;
        }
      })}
    </div>
  );
}
