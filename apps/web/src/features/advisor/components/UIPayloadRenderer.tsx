import type { UIComponent } from '@loopops/contracts';
import { AttributionChart, PortfolioSummaryCard } from './cards/PortfolioCards';
import { CitationList, WarningBanner } from './cards/SupportCards';

type UIPayloadRendererProps = {
  components: UIComponent[];
};

export function UIPayloadRenderer({ components }: UIPayloadRendererProps) {
  return (
    <div className="flex flex-col gap-3">
      {components.map((component, index) => {
        switch (component.type) {
          case 'portfolio_summary':
            return (
              <PortfolioSummaryCard
                key={`portfolio-${index}`}
                payload={component.payload}
                asOf={component.as_of}
              />
            );
          case 'attribution_bars':
            return <AttributionChart key={`attribution-${index}`} payload={component.payload} />;
          case 'warning_banner':
            return <WarningBanner key={`warning-${index}`} payload={component.payload} />;
          case 'citations':
            return <CitationList key={`citations-${index}`} payload={component.payload} />;
          default:
            return null;
        }
      })}
    </div>
  );
}
