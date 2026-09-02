import type {
  AccountsListPayload,
  AttributionBarsPayload,
  CalendarListPayload,
  CashSummaryPayload,
  CitationsPayload,
  ComplaintCardPayload,
  DisclosurePayload,
  EscalationCardPayload,
  FeeBreakdownPayload,
  FormSpecPayload,
  MarketQuotePayload,
  NewsListPayload,
  OrderReceiptPayload,
  PortfolioPositionsPayload,
  PortfolioSummaryPayload,
  ProductDetailPayload,
  ProductListPayload,
  QuoteTablePayload,
  ServicesGuidePayload,
  SimulationChartPayload,
  StatementLinkPayload,
  SuitabilitySummaryPayload,
  TransactionListPayload,
  UIComponent,
  WarningBannerPayload,
} from '@loopops/contracts';
import {
  AccountsListPayloadSchema,
  AttributionBarsPayloadSchema,
  CalendarListPayloadSchema,
  CashSummaryPayloadSchema,
  CitationsPayloadSchema,
  ComplaintCardPayloadSchema,
  DisclosurePayloadSchema,
  EscalationCardPayloadSchema,
  EscalationOfferPayloadSchema,
  FeeBreakdownPayloadSchema,
  FormSpecPayloadSchema,
  MarketQuotePayloadSchema,
  NewsListPayloadSchema,
  OrderReceiptPayloadSchema,
  PortfolioPositionsPayloadSchema,
  PortfolioSummaryPayloadSchema,
  ProductDetailPayloadSchema,
  ProductListPayloadSchema,
  ProfileUpdateOfferPayloadSchema,
  QuoteTablePayloadSchema,
  ServicesGuidePayloadSchema,
  SimulationChartPayloadSchema,
  StatementLinkPayloadSchema,
  SuitabilitySummaryPayloadSchema,
  TransactionListPayloadSchema,
  WarningBannerPayloadSchema,
} from '@loopops/contracts';
import type { ZodType } from 'zod';
import { Info, TriangleAlert } from 'lucide-react';
import { useTranslation } from '@/i18n';
import { formatDate, moneyFormatter } from './ui-payload-format';

function matchPayload<T>(schema: ZodType<T>, component: UIComponent): T | null {
  const result = schema.safeParse(component.payload);
  return result.success ? result.data : null;
}

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
          {t('advisor.as_of_label')}
        </dt>
        <dd className="text-content-small text-xs tabular-nums">{formatDate(payload.as_of)}</dd>
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

export function MarketQuoteCard({ payload }: { payload: MarketQuotePayload }) {
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
              <span className="text-content-small">
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
  const suitability = 'warnings' in payload;
  const isWarning = suitability || payload.severity === 'warning';
  const Icon = isWarning ? TriangleAlert : Info;
  return (
    <div
      role="status"
      className={`flex items-start gap-2 rounded-xs border px-2.5 py-2 text-xs leading-relaxed ${
        isWarning
          ? 'border-warning/30 bg-warning/10 text-warning'
          : 'border-info/30 bg-info/10 text-info'
      }`}
    >
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {suitability ? (
        <span className="flex flex-col gap-0.5">
          <span className="font-medium">{payload.product_id}</span>
          {payload.warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </span>
      ) : (
        <span>{payload.message}</span>
      )}
    </div>
  );
}

// ── shared primitives ───────────────────────────────────────────────────────

const LABEL_STYLES = 'text-content-sub text-[11px] font-medium tracking-wide uppercase';

function CardTitle({ children }: { children: React.ReactNode }) {
  return <p className={LABEL_STYLES}>{children}</p>;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-content-small text-xs">{label}</span>
      <span className="text-content text-xs font-medium tabular-nums">{value}</span>
    </div>
  );
}

function money(value: { amount: string }): string {
  return moneyFormatter.format(Number(value.amount));
}

// ── portfolio ───────────────────────────────────────────────────────────────

function PortfolioPositionsCard({ payload }: { payload: PortfolioPositionsPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-2">
      <CardTitle>{t('advisor.positions')}</CardTitle>
      <Row label={t('advisor.total_value')} value={money(payload.total_market_value)} />
      <Row label={t('advisor.cash')} value={money(payload.cash)} />
      <ul className="flex flex-col gap-1.5">
        {payload.positions.map((position) => (
          <li key={position.product_id} className="flex flex-col gap-0.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-content text-xs">{position.name}</span>
              <span className="text-content text-xs font-semibold tabular-nums">
                {money(position.market_value)}
              </span>
            </div>
            <div className="text-content-small flex items-baseline justify-between gap-2 text-[11px] tabular-nums">
              <span>
                {t('advisor.weight')} {position.weight_pct.toFixed(1)}%
              </span>
              {position.cost_basis && (
                <span>
                  {t('advisor.cost_basis')} {money(position.cost_basis)}
                </span>
              )}
            </div>
            <div className="bg-outline/40 h-1 w-full overflow-hidden rounded-full">
              <div
                className="bg-info h-full rounded-full"
                style={{ width: `${Math.min(100, position.weight_pct)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CashSummaryCard({ payload }: { payload: CashSummaryPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <CardTitle>{t('advisor.cash')}</CardTitle>
      <Row label={t('advisor.cash_available')} value={money(payload.available)} />
      <Row label={t('advisor.cash_pending')} value={money(payload.pending)} />
      {payload.settlements.length > 0 && (
        <>
          <CardTitle>{t('advisor.settlements')}</CardTitle>
          {payload.settlements.map((settlement) => (
            <Row
              key={`${settlement.date}-${settlement.amount.amount}`}
              label={formatDate(settlement.date)}
              value={money(settlement.amount)}
            />
          ))}
        </>
      )}
    </div>
  );
}

function AccountsListCard({ payload }: { payload: AccountsListPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <CardTitle>{t('advisor.accounts')}</CardTitle>
      {payload.accounts.map((account) => (
        <Row
          key={account.account_id}
          label={account.label}
          value={`${account.type} · ${account.currency}`}
        />
      ))}
    </div>
  );
}

// ── products ────────────────────────────────────────────────────────────────

function ProductListCard({ payload, title }: { payload: ProductListPayload; title: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-2">
      <CardTitle>{title}</CardTitle>
      <ul className="flex flex-col gap-1.5">
        {payload.items.map((item) => (
          <li key={item.product_id} className="flex flex-col gap-0.5">
            <span className="text-content text-xs font-medium">{item.name}</span>
            <div className="text-content-small flex flex-wrap gap-x-3 text-[11px] tabular-nums">
              <span>
                {t('advisor.risk')}: {item.risk_level}
              </span>
              <span>
                {t('advisor.annual_cost')}: {item.annual_cost_pct.toFixed(2)}%
              </span>
              <span>
                {t('advisor.min_investment')}: {money(item.minimum_investment)}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProductDetailCard({ payload }: { payload: ProductDetailPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <CardTitle>{payload.name}</CardTitle>
      <p className="text-content-small text-xs leading-relaxed">{payload.objective}</p>
      <Row label={t('advisor.risk')} value={payload.risk_level} />
      <Row label={t('advisor.complexity')} value={payload.complexity} />
      <Row label={t('advisor.annual_cost')} value={`${payload.fees.annual_cost_pct.toFixed(2)}%`} />
      <Row label={t('advisor.min_investment')} value={money(payload.minimum_investment)} />
      {payload.historical_returns.map((entry) => (
        <Row
          key={entry.period}
          label={entry.period}
          value={<ReturnBadge value={entry.return_pct} period={entry.period} />}
        />
      ))}
    </div>
  );
}

// ── market ──────────────────────────────────────────────────────────────────

function QuoteTableCard({ payload }: { payload: QuoteTablePayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <CardTitle>{t('advisor.quotes')}</CardTitle>
      {payload.quotes.map((quote) => (
        <div key={quote.symbol} className="flex flex-col gap-0.5">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-content text-xs font-medium">{quote.symbol}</span>
            <span className="flex items-baseline gap-2">
              <span className="text-content text-xs font-semibold tabular-nums">
                {quote.price.toFixed(2)} {quote.currency}
              </span>
              <ReturnBadge value={quote.change_pct} period={t('advisor.today')} />
            </span>
          </div>
          {quote.delayed && (
            <span className="text-content-small text-[11px]">
              {t('advisor.delayed_quote', { minutes: quote.delay_minutes })}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function NewsListCard({ payload, title }: { payload: NewsListPayload; title: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <CardTitle>{title}</CardTitle>
      <ul className="flex flex-col gap-1.5">
        {payload.items.map((item) => (
          <li key={item.url || item.title} className="flex flex-col gap-0.5">
            <span className="text-content text-xs leading-relaxed">{item.title}</span>
            <span className="text-content-small text-[11px]">
              {item.source} · {formatDate(item.published_at)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CalendarListCard({ payload }: { payload: CalendarListPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <CardTitle>{t('advisor.calendar')}</CardTitle>
      {payload.events.map((event) => (
        <Row
          key={`${event.date}-${event.name}`}
          label={`${formatDate(event.date)} · ${event.region}`}
          value={`${event.name} (${event.importance})`}
        />
      ))}
    </div>
  );
}

// ── simulation, fees, transactions ──────────────────────────────────────────

function SimulationChartCard({ payload }: { payload: SimulationChartPayload }) {
  const { t } = useTranslation();
  const scenarios = [
    { key: 'pessimistic' as const, label: t('advisor.scenario_pessimistic') },
    { key: 'base' as const, label: t('advisor.scenario_base') },
    { key: 'optimistic' as const, label: t('advisor.scenario_optimistic') },
  ];
  const max = Math.max(...scenarios.map((s) => Number(payload.scenarios[s.key].amount)), 1);
  return (
    <div className="flex flex-col gap-1.5">
      <CardTitle>{t('advisor.simulation')}</CardTitle>
      <span className="text-content-small text-[11px]">
        {t('advisor.horizon_months', { months: payload.horizon_months })}
      </span>
      {scenarios.map((scenario) => {
        const value = payload.scenarios[scenario.key];
        return (
          <div key={scenario.key} className="flex flex-col gap-0.5">
            <Row label={scenario.label} value={money(value)} />
            <div className="bg-outline/40 h-1 w-full overflow-hidden rounded-full">
              <div
                className="bg-info h-full rounded-full"
                style={{ width: `${Math.round((Number(value.amount) / max) * 100)}%` }}
              />
            </div>
          </div>
        );
      })}
      {payload.disclosures.map((disclosure) => (
        <p key={disclosure} className="text-content-small text-[11px] leading-relaxed">
          {disclosure}
        </p>
      ))}
    </div>
  );
}

function FeeBreakdownCard({ payload }: { payload: FeeBreakdownPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <CardTitle>{t('advisor.fees')}</CardTitle>
      {payload.fees.map((fee) => (
        <Row key={fee.name} label={fee.name} value={money(fee.amount)} />
      ))}
      <Row label={t('advisor.isr_withholding')} value={money(payload.estimated_isr_withholding)} />
      <Row label={t('advisor.total')} value={money(payload.total)} />
    </div>
  );
}

function TransactionListCard({ payload }: { payload: TransactionListPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <CardTitle>{t('advisor.transactions')}</CardTitle>
      {payload.items.map((item) => (
        <Row
          key={item.operation_id}
          label={`${formatDate(item.date)} · ${item.type}`}
          value={`${money(item.amount)} · ${item.status}`}
        />
      ))}
    </div>
  );
}

function StatementLinkCard({ payload }: { payload: StatementLinkPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1">
      <CardTitle>{t('advisor.statement')}</CardTitle>
      <Row label={`${payload.month}/${payload.year}`} value={t('advisor.download')} />
      <a
        href={payload.url}
        target="_blank"
        rel="noreferrer"
        className="text-info text-xs underline underline-offset-2"
      >
        {payload.url}
      </a>
    </div>
  );
}

function ServicesGuideCard({ payload }: { payload: ServicesGuidePayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <CardTitle>{t('advisor.services_guide')}</CardTitle>
      {payload.sections.map((section) => (
        <div key={section.id} className="flex flex-col gap-0.5">
          <span className="text-content text-xs font-medium">{section.title}</span>
          <span className="text-content-small text-[11px] leading-relaxed">{section.text}</span>
        </div>
      ))}
    </div>
  );
}

// ── compliance and transactional ────────────────────────────────────────────

function SuitabilitySummaryCard({ payload }: { payload: SuitabilitySummaryPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <CardTitle>{t('advisor.suitability')}</CardTitle>
      {payload.evaluations.map((evaluation) => (
        <div key={evaluation.product_id} className="flex flex-col gap-0.5">
          <Row label={evaluation.product_id} value={evaluation.outcome} />
          <span className="text-content-small text-[11px] leading-relaxed">
            {evaluation.rationale}
          </span>
        </div>
      ))}
    </div>
  );
}

function DisclosureCard({ payload }: { payload: DisclosurePayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-0.5">
      <CardTitle>{t('advisor.disclosure')}</CardTitle>
      <p className="text-content-small text-xs leading-relaxed">{payload.text}</p>
    </div>
  );
}

function FormSpecCard({ payload }: { payload: FormSpecPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1">
      <CardTitle>{t('advisor.form_pending')}</CardTitle>
      <Row label={payload.operation} value={payload.product.name ?? payload.product.product_id} />
      {payload.approved_amount && (
        <Row label={t('advisor.total')} value={money(payload.approved_amount)} />
      )}
      <span className="text-content-small text-[11px]">
        {t('advisor.form_expires', { date: formatDate(payload.expires_at.slice(0, 10)) })}
      </span>
    </div>
  );
}

function OrderReceiptCard({ payload }: { payload: OrderReceiptPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1">
      <CardTitle>{t('advisor.order_receipt')}</CardTitle>
      {payload.order_id && <Row label={t('advisor.order_id')} value={payload.order_id} />}
      <Row label={payload.operation} value={payload.product.name ?? payload.product.product_id} />
      {payload.settlement_date && (
        <Row
          label={t('advisor.settlement_date')}
          value={formatDate(payload.settlement_date.slice(0, 10))}
        />
      )}
      {payload.status && <Row label={t('advisor.total')} value={payload.status} />}
    </div>
  );
}

function EscalationCardBody({ payload }: { payload: EscalationCardPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1">
      <CardTitle>{t('advisor.escalation')}</CardTitle>
      <Row label={payload.promotor_name} value={payload.sla} />
      <span className="text-content-small text-[11px] leading-relaxed">{payload.reason}</span>
    </div>
  );
}

function ComplaintCardBody({ payload }: { payload: ComplaintCardPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1">
      <CardTitle>{t('advisor.complaint')}</CardTitle>
      <Row label={t('advisor.complaint_folio')} value={payload.folio} />
      <Row label={t('advisor.response_deadline')} value={formatDate(payload.response_deadline)} />
      <span className="text-content-small text-[11px] leading-relaxed">
        {payload.condusef_notice}
      </span>
    </div>
  );
}

function OfferCard({ label, reason }: { label: string; reason: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-content text-xs font-medium">{label}</span>
      <span className="text-content-small text-[11px]">{reason}</span>
    </div>
  );
}

/**
 * An unknown component used to render nothing at all, which made a server-side
 * type the client had not shipped yet indistinguishable from a bug. Outside
 * production it is now visible.
 */
function UnsupportedCard({ type }: { type: string }) {
  const { t } = useTranslation();
  if (import.meta.env.PROD) return null;
  return (
    <p
      role="status"
      className="border-warning/30 bg-warning/10 text-warning flex items-start gap-2 rounded-xs border px-2.5 py-2 text-xs"
    >
      <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {t('advisor.unsupported_component', { type })}
    </p>
  );
}

const CARD_BODY_STYLES =
  'flex w-full flex-col gap-2 rounded-xl border border-outline-soft bg-surface-sub px-3 py-2.5 text-left text-content';

/**
 * Maps one server component to its card. Returns `null` only when the payload
 * fails its schema; an unrecognised `type` falls through to UnsupportedCard so
 * a server type the client has not shipped is visible instead of silent.
 */
function useCardBody(component: UIComponent): React.ReactNode {
  const { t } = useTranslation();
  switch (component.type) {
    case 'portfolio_summary': {
      const payload = matchPayload(PortfolioSummaryPayloadSchema, component);
      return payload ? <PortfolioSummaryCard payload={payload} /> : null;
    }
    case 'portfolio_positions': {
      const payload = matchPayload(PortfolioPositionsPayloadSchema, component);
      return payload ? <PortfolioPositionsCard payload={payload} /> : null;
    }
    case 'attribution_bars': {
      const payload = matchPayload(AttributionBarsPayloadSchema, component);
      return payload ? <AttributionBarsCard payload={payload} /> : null;
    }
    case 'cash_summary': {
      const payload = matchPayload(CashSummaryPayloadSchema, component);
      return payload ? <CashSummaryCard payload={payload} /> : null;
    }
    case 'accounts_list': {
      const payload = matchPayload(AccountsListPayloadSchema, component);
      return payload ? <AccountsListCard payload={payload} /> : null;
    }
    case 'product_list':
    case 'product_comparison': {
      const payload = matchPayload(ProductListPayloadSchema, component);
      return payload ? <ProductListCard payload={payload} title={t('advisor.products')} /> : null;
    }
    case 'product_detail': {
      const payload = matchPayload(ProductDetailPayloadSchema, component);
      return payload ? <ProductDetailCard payload={payload} /> : null;
    }
    case 'quote_table': {
      const payload = matchPayload(QuoteTablePayloadSchema, component);
      return payload ? <QuoteTableCard payload={payload} /> : null;
    }
    case 'market_quote': {
      const payload = matchPayload(MarketQuotePayloadSchema, component);
      return payload ? <MarketQuoteCard payload={payload} /> : null;
    }
    case 'news_list': {
      const payload = matchPayload(NewsListPayloadSchema, component);
      return payload ? <NewsListCard payload={payload} title={t('advisor.news')} /> : null;
    }
    case 'research_list': {
      const payload = matchPayload(NewsListPayloadSchema, component);
      return payload ? <NewsListCard payload={payload} title={t('advisor.research')} /> : null;
    }
    case 'calendar_list': {
      const payload = matchPayload(CalendarListPayloadSchema, component);
      return payload ? <CalendarListCard payload={payload} /> : null;
    }
    case 'simulation_chart': {
      const payload = matchPayload(SimulationChartPayloadSchema, component);
      return payload ? <SimulationChartCard payload={payload} /> : null;
    }
    case 'fee_breakdown': {
      const payload = matchPayload(FeeBreakdownPayloadSchema, component);
      return payload ? <FeeBreakdownCard payload={payload} /> : null;
    }
    case 'transaction_list': {
      const payload = matchPayload(TransactionListPayloadSchema, component);
      return payload ? <TransactionListCard payload={payload} /> : null;
    }
    case 'statement_link': {
      const payload = matchPayload(StatementLinkPayloadSchema, component);
      return payload ? <StatementLinkCard payload={payload} /> : null;
    }
    case 'services_guide': {
      const payload = matchPayload(ServicesGuidePayloadSchema, component);
      return payload ? <ServicesGuideCard payload={payload} /> : null;
    }
    case 'suitability_summary': {
      const payload = matchPayload(SuitabilitySummaryPayloadSchema, component);
      return payload ? <SuitabilitySummaryCard payload={payload} /> : null;
    }
    case 'warning_banner': {
      const payload = matchPayload(WarningBannerPayloadSchema, component);
      return payload ? <WarningBannerCard payload={payload} /> : null;
    }
    case 'disclosure': {
      const payload = matchPayload(DisclosurePayloadSchema, component);
      return payload ? <DisclosureCard payload={payload} /> : null;
    }
    case 'form_spec': {
      const payload = matchPayload(FormSpecPayloadSchema, component);
      return payload ? <FormSpecCard payload={payload} /> : null;
    }
    case 'order_receipt': {
      const payload = matchPayload(OrderReceiptPayloadSchema, component);
      return payload ? <OrderReceiptCard payload={payload} /> : null;
    }
    case 'escalation_card': {
      const payload = matchPayload(EscalationCardPayloadSchema, component);
      return payload ? <EscalationCardBody payload={payload} /> : null;
    }
    case 'complaint_card': {
      const payload = matchPayload(ComplaintCardPayloadSchema, component);
      return payload ? <ComplaintCardBody payload={payload} /> : null;
    }
    case 'escalation_offer': {
      const payload = matchPayload(EscalationOfferPayloadSchema, component);
      return payload ? <OfferCard label={payload.cta_es} reason={payload.reason} /> : null;
    }
    case 'profile_update_offer': {
      const payload = matchPayload(ProfileUpdateOfferPayloadSchema, component);
      return payload ? <OfferCard label={payload.cta_es} reason={payload.reason} /> : null;
    }
    case 'citations': {
      const payload = matchPayload(CitationsPayloadSchema, component);
      return payload ? <CitationsCard payload={payload} /> : null;
    }
    default:
      return <UnsupportedCard type={component.type} />;
  }
}

/** One server component rendered as its card, or nothing when it has no body. */
function UIPayloadCard({ component }: { component: UIComponent }) {
  const body = useCardBody(component);
  if (body === null) return null;
  return <div className={CARD_BODY_STYLES}>{body}</div>;
}

/** Renders the ui_payload cards attached to an avatar chat message. */
export function UIPayloadCards({ components }: { components: UIComponent[] }) {
  if (components.length === 0) return null;
  return (
    <div className="mt-2 flex flex-col gap-2">
      {components.map((component, index) => (
        <UIPayloadCard key={index} component={component} />
      ))}
    </div>
  );
}
