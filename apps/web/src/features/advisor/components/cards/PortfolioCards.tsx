import type { AttributionBarsPayload, PortfolioSummaryPayload } from '@loopops/contracts';
import { useTranslation } from '@/i18n';

type PortfolioSummaryCardProps = {
  payload: PortfolioSummaryPayload;
  asOf?: string;
};

export function PortfolioSummaryCard({ payload, asOf }: PortfolioSummaryCardProps) {
  const { t } = useTranslation();
  const sign = payload.period_return_pct >= 0 ? '+' : '';
  const tone = payload.period_return_pct >= 0 ? 'text-success' : 'text-error';

  return (
    <div className="border-outline bg-surface rounded-xs border p-4">
      <p className="text-content-muted text-xs font-medium tracking-wide uppercase">
        {t('advisor.portfolio_title')}
      </p>
      <p className="font-heading mt-1 text-2xl font-semibold tabular-nums">
        ${payload.market_value.amount}{' '}
        <span className="text-content-sub text-base font-normal">MXN</span>
      </p>
      <p className={`mt-1 text-sm font-medium tabular-nums ${tone}`}>
        {sign}
        {payload.period_return_pct.toFixed(2)}% · {payload.period}
      </p>
      {(asOf ?? payload.as_of) && (
        <p className="text-content-muted mt-2 text-xs">
          {t('advisor.as_of', { date: asOf ?? payload.as_of })}
        </p>
      )}
    </div>
  );
}

type AttributionChartProps = {
  payload: AttributionBarsPayload;
};

export function AttributionChart({ payload }: AttributionChartProps) {
  const { t } = useTranslation();
  const maxAbs = Math.max(...payload.contributions.map((c) => Math.abs(c.bps)), 1);

  return (
    <div className="border-outline bg-surface rounded-xs border p-4">
      <p className="text-content-muted text-xs font-medium tracking-wide uppercase">
        {t('advisor.attribution_title')}
      </p>
      <ul className="mt-3 flex flex-col gap-2">
        {payload.contributions.map((row) => {
          const width = `${(Math.abs(row.bps) / maxAbs) * 100}%`;
          const positive = row.bps >= 0;
          return (
            <li key={row.sleeve} className="grid grid-cols-[1fr_auto] items-center gap-3">
              <div>
                <p className="text-sm">{row.sleeve}</p>
                <div className="bg-surface-sub mt-1 h-2 overflow-hidden rounded-full">
                  <div
                    className={`h-full rounded-full ${positive ? 'bg-success' : 'bg-error'}`}
                    style={{ width }}
                  />
                </div>
              </div>
              <span
                className={`text-sm font-medium tabular-nums ${positive ? 'text-success' : 'text-error'}`}
              >
                {positive ? '+' : ''}
                {row.bps} bp
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
