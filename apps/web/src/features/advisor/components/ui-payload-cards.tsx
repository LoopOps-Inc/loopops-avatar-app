import type {
  AttributionBarsPayload,
  CitationsPayload,
  MarketQuotePayload,
  PortfolioSummaryPayload,
  UIComponent,
  WarningBannerPayload,
} from '@loopops/contracts';
import { Info, TriangleAlert } from 'lucide-react';
import { useTranslation } from '@/i18n';
import { formatDate, moneyFormatter } from './ui-payload-format';

function ReturnBadge({ value, period }: { value: number; period: string }) {
  const positive = value >= 0;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
        positive ? 'bg-success/15 text-success' : 'bg-error/15 text-error'
      }`}
    >
      {positive ? '+' : ''}
      {value.toFixed(2)}% {period}
    </span>
  );
}

function PortfolioSummaryCard({ payload }: { payload: PortfolioSummaryPayload }) {
  const { t } = useTranslation();
  return (
    <dl className="grid grid-cols-2 gap-2">
      <div className="col-span-2 flex items-baseline justify-between gap-2">
        <dt className="text-content-sub text-[11px] font-medium tracking-wide uppercase">
          {t('advisor.market_value')}
        </dt>
        <dd className="text-content text-sm font-semibold tabular-nums">
          {moneyFormatter.format(Number(payload.market_value.amount))}
        </dd>
      </div>
      <div className="flex items-center justify-between gap-2">
        <dt className="text-content-sub text-[11px] font-medium tracking-wide uppercase">
          {t('advisor.period_return')}
        </dt>
        <dd>
          <ReturnBadge value={payload.period_return_pct} period={payload.period} />
        </dd>
      </div>
      <div className="flex items-center justify-between gap-2">
        <dt className="text-content-sub text-[11px] font-medium tracking-wide uppercase">
          {t('advisor.as_of')}
        </dt>
        <dd className="text-content-sub text-xs tabular-nums">{formatDate(payload.as_of)}</dd>
      </div>
    </dl>
  );
}

function AttributionBarsCard({ payload }: { payload: AttributionBarsPayload }) {
  const { t } = useTranslation();
  const max = Math.max(...payload.contributions.map((c) => Math.abs(c.bps)), 1);
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-content-sub text-[11px] font-medium tracking-wide uppercase">
        {t('advisor.contributions')}
      </p>
      {payload.contributions.map((contribution) => {
        const positive = contribution.bps >= 0;
        const width = Math.round((Math.abs(contribution.bps) / max) * 100);
        return (
          <div key={contribution.sleeve} className="flex flex-col gap-0.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-content text-xs">{contribution.sleeve}</span>
              <span
                className={`text-xs font-medium tabular-nums ${positive ? 'text-success' : 'text-error'}`}
              >
                {positive ? '+' : ''}
                {contribution.bps} bp
              </span>
            </div>
            <div className="bg-outline/40 h-1.5 w-full overflow-hidden rounded-full">
              <div
                className={`h-full rounded-full ${positive ? 'bg-success' : 'bg-error'}`}
                style={{ width: `${width}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function MarketQuoteCard({ payload }: { payload: MarketQuotePayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-content-sub text-xs font-medium tracking-wide uppercase">
        {payload.symbol}
      </span>
      <span className="flex items-baseline gap-2">
        <span className="text-content text-sm font-semibold tabular-nums">{payload.value}</span>
        {payload.change_pct !== undefined && (
          <ReturnBadge value={payload.change_pct} period={t('advisor.today')} />
        )}
      </span>
    </div>
  );
}

function CitationsCard({ payload }: { payload: CitationsPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-content-sub text-[11px] font-medium tracking-wide uppercase">
        {t('advisor.citations')}
      </p>
      <ul className="flex flex-col gap-1">
        {payload.items.map((item) => (
          <li key={item.title} className="text-content text-xs leading-relaxed">
            {item.title}
            {(item.source || item.published) && (
              <span className="text-content-muted">
                {' '}
                — {item.source}
                {item.published ? `, ${formatDate(item.published)}` : ''}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function WarningBannerCard({ payload }: { payload: WarningBannerPayload }) {
  const isWarning = payload.severity === 'warning';
  const Icon = isWarning ? TriangleAlert : Info;
  return (
    <p
      role="status"
      className={`flex items-start gap-2 rounded-xs border px-2.5 py-2 text-xs leading-relaxed ${
        isWarning
          ? 'border-warning/30 bg-warning/10 text-warning'
          : 'border-info/30 bg-info/10 text-info'
      }`}
    >
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {payload.message}
    </p>
  );
}

const CARD_BODY_STYLES =
  'flex w-full flex-col gap-2 rounded-xl border border-outline-soft bg-surface-sub px-3 py-2.5 text-left';

/** Renders the ui_payload cards attached to an avatar chat message. */
export function UIPayloadCards({ components }: { components: UIComponent[] }) {
  if (components.length === 0) return null;
  return (
    <div className="mt-2 flex flex-col gap-2">
      {components.map((component, index) => {
        switch (component.type) {
          case 'portfolio_summary':
            return (
              <div key={index} className={CARD_BODY_STYLES}>
                <PortfolioSummaryCard payload={component.payload} />
              </div>
            );
          case 'attribution_bars':
            return (
              <div key={index} className={CARD_BODY_STYLES}>
                <AttributionBarsCard payload={component.payload} />
              </div>
            );
          case 'market_quote':
            return (
              <div key={index} className={CARD_BODY_STYLES}>
                <MarketQuoteCard payload={component.payload} />
              </div>
            );
          case 'citations':
            return (
              <div key={index} className={CARD_BODY_STYLES}>
                <CitationsCard payload={component.payload} />
              </div>
            );
          case 'warning_banner':
            return <WarningBannerCard key={index} payload={component.payload} />;
          default:
            return null;
        }
      })}
    </div>
  );
}
