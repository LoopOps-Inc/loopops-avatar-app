import { z } from 'zod';

/** The currencies the backend's Money model accepts (graph/state.py::Money). */
export const CurrencySchema = z.enum(['MXN', 'USD', 'EUR']);
export type Currency = z.infer<typeof CurrencySchema>;

/** Decimal money — amount is a string to avoid IEEE 754 issues. */
export const MoneySchema = z.object({
  amount: z.string(),
  currency: CurrencySchema,
});
export type Money = z.infer<typeof MoneySchema>;

export const CapabilitiesSchema = z.object({
  chat: z.boolean(),
  voice: z.boolean(),
  advisory: z.boolean(),
  transactional: z.boolean(),
});
export type Capabilities = z.infer<typeof CapabilitiesSchema>;

export const DisclosureSchema = z.object({
  id: z.string(),
  version: z.string(),
  acknowledged: z.boolean(),
  required_for: z.enum(['first_turn', 'voice', 'optional']).optional(),
  text_url: z.string().optional(),
});
export type Disclosure = z.infer<typeof DisclosureSchema>;

export const SessionResponseSchema = z.object({
  thread_id: z.string(),
  /** ISO-8601 timestamp for when the advisor thread was first opened. */
  thread_started_at: z.string().datetime({ offset: true }),
  capabilities: CapabilitiesSchema,
  disclosures_required: z.array(DisclosureSchema),
  client: z.object({
    first_name: z.string(),
    risk_category: z.string(),
    profile_expires_at: z.string().nullish(),
    register: z.enum(['tu', 'usted']).optional(),
  }),
  mode_defaults: z
    .object({
      default_mode: z.enum(['chat', 'voice']),
      voice_available: z.boolean(),
      filler_threshold_ms: z.number(),
      thinking_ceiling_s: z.number(),
      background_grace_s: z.number(),
    })
    .optional(),
  promotor: z
    .object({
      name: z.string().optional(),
      phone: z.string().optional(),
      hours: z.string().optional(),
    })
    .optional(),
  kill_switch: z.boolean().optional(),
  risk_mode: z.enum(['normal', 'restricted']).optional(),
});
export type SessionResponse = z.infer<typeof SessionResponseSchema>;

export const PortfolioSummaryPayloadSchema = z.object({
  as_of: z.string(),
  market_value: MoneySchema,
  period_return_pct: z.number(),
  period: z.string(),
});
export type PortfolioSummaryPayload = z.infer<typeof PortfolioSummaryPayloadSchema>;

export const AttributionContributionSchema = z.object({
  sleeve: z.string(),
  bps: z.number(),
});
export type AttributionContribution = z.infer<typeof AttributionContributionSchema>;

export const AttributionBarsPayloadSchema = z.object({
  contributions: z.array(AttributionContributionSchema),
  source: z.string().optional(),
  trace_id: z.string().optional(),
});
export type AttributionBarsPayload = z.infer<typeof AttributionBarsPayloadSchema>;

export const MarketQuotePayloadSchema = z.object({
  symbol: z.string(),
  value: z.string(),
  change_pct: z.number().optional(),
  as_of: z.string().optional(),
});
export type MarketQuotePayload = z.infer<typeof MarketQuotePayloadSchema>;

export const CitationSchema = z.object({
  title: z.string(),
  url: z.string().optional(),
  published: z.string().optional(),
  published_at: z.string().optional(),
  source: z.string().optional(),
});
export type Citation = z.infer<typeof CitationSchema>;

export const CitationsPayloadSchema = z.object({
  items: z.array(CitationSchema),
});
export type CitationsPayload = z.infer<typeof CitationsPayloadSchema>;

export const WarningBannerPayloadSchema = z.union([
  // Emitted by the composer for APTO_CON_ADVERTENCIA suitability outcomes.
  z.object({ product_id: z.string(), warnings: z.array(z.string()) }),
  z.object({ severity: z.enum(['info', 'warning']), message: z.string() }),
]);
export type WarningBannerPayload = z.infer<typeof WarningBannerPayloadSchema>;

// ── ui_payload: the closed component registry (docs/03-mobile/01 §4) ─────────
// Shapes mirror the tool results the composer forwards verbatim
// (services/agent/src/actinver_agent/tools/results.py) and the payloads it
// builds itself (graph/nodes/composer.py). Adding a type here is the client
// release that makes the server's component renderable.

export const PositionSchema = z.object({
  product_id: z.string(),
  name: z.string(),
  asset_class: z.string(),
  quantity: z.number(),
  market_value: MoneySchema,
  cost_basis: MoneySchema,
  weight_pct: z.number(),
  currency: CurrencySchema,
});
export type Position = z.infer<typeof PositionSchema>;

export const PortfolioPositionsPayloadSchema = z.object({
  as_of: z.string(),
  total_market_value: MoneySchema,
  cash: MoneySchema,
  liquid_pct: z.number(),
  positions: z.array(PositionSchema),
});
export type PortfolioPositionsPayload = z.infer<typeof PortfolioPositionsPayloadSchema>;

export const SettlementSchema = z.object({ date: z.string(), amount: MoneySchema });
export type Settlement = z.infer<typeof SettlementSchema>;

export const CashSummaryPayloadSchema = z.object({
  as_of: z.string(),
  available: MoneySchema,
  pending: MoneySchema,
  settlements: z.array(SettlementSchema),
});
export type CashSummaryPayload = z.infer<typeof CashSummaryPayloadSchema>;

export const AccountSchema = z.object({
  account_id: z.string(),
  label: z.string(),
  type: z.string(),
  currency: CurrencySchema,
  eligible_for: z.array(z.enum(['debit', 'credit'])),
});
export type Account = z.infer<typeof AccountSchema>;

export const AccountsListPayloadSchema = z.object({
  as_of: z.string(),
  accounts: z.array(AccountSchema),
});
export type AccountsListPayload = z.infer<typeof AccountsListPayloadSchema>;

export const HistoricalReturnSchema = z.object({
  period: z.string(),
  return_pct: z.number(),
  as_of: z.string(),
});
export type HistoricalReturn = z.infer<typeof HistoricalReturnSchema>;

export const RiskLevelSchema = z.enum(['bajo', 'medio', 'alto']);
export const ComplexitySchema = z.enum(['simple', 'moderada', 'compleja']);

export const ProductSummarySchema = z.object({
  product_id: z.string(),
  name: z.string(),
  risk_level: RiskLevelSchema,
  complexity: ComplexitySchema,
  asset_class: z.string(),
  currency: CurrencySchema,
  liquidity_hours: z.number().nullable().optional(),
  min_holding_months: z.number(),
  minimum_investment: MoneySchema,
  annual_cost_pct: z.number(),
  committee_version: z.number(),
  historical_returns: z.array(HistoricalReturnSchema).nullable().optional(),
});
export type ProductSummary = z.infer<typeof ProductSummarySchema>;

export const ProductListPayloadSchema = z.object({
  as_of: z.string(),
  items: z.array(ProductSummarySchema),
});
export type ProductListPayload = z.infer<typeof ProductListPayloadSchema>;

export const FeesSchema = z.object({
  annual_cost_pct: z.number(),
  entry_fee_pct: z.number(),
  exit_fee_pct: z.number(),
});

export const ProductDetailPayloadSchema = ProductSummarySchema.extend({
  as_of: z.string(),
  objective: z.string(),
  policy: z.string(),
  fees: FeesSchema,
  historical_returns: z.array(HistoricalReturnSchema),
  dici_url: z.string(),
  prospectus_url: z.string(),
});
export type ProductDetailPayload = z.infer<typeof ProductDetailPayloadSchema>;

export const QuoteSchema = z.object({
  symbol: z.string(),
  price: z.number(),
  currency: z.string(),
  change_pct: z.number(),
  timestamp: z.string(),
  delayed: z.boolean(),
  delay_minutes: z.number(),
});
export type Quote = z.infer<typeof QuoteSchema>;

export const QuoteTablePayloadSchema = z.object({
  as_of: z.string(),
  quotes: z.array(QuoteSchema),
});
export type QuoteTablePayload = z.infer<typeof QuoteTablePayloadSchema>;

export const NewsItemSchema = z.object({
  title: z.string(),
  url: z.string(),
  source: z.string(),
  published_at: z.string(),
  summary: z.string(),
});
export type NewsItem = z.infer<typeof NewsItemSchema>;

export const NewsListPayloadSchema = z.object({
  as_of: z.string(),
  items: z.array(NewsItemSchema),
});
export type NewsListPayload = z.infer<typeof NewsListPayloadSchema>;

export const CalendarEventSchema = z.object({
  date: z.string(),
  region: z.enum(['MX', 'US', 'GLOBAL']),
  name: z.string(),
  importance: z.enum(['alta', 'media', 'baja']),
});
export type CalendarEvent = z.infer<typeof CalendarEventSchema>;

export const CalendarListPayloadSchema = z.object({
  as_of: z.string(),
  events: z.array(CalendarEventSchema),
});
export type CalendarListPayload = z.infer<typeof CalendarListPayloadSchema>;

export const SimulationChartPayloadSchema = z.object({
  as_of: z.string(),
  product_id: z.string(),
  amount: MoneySchema,
  horizon_months: z.number(),
  annual_volatility_pct: z.number(),
  scenarios: z.object({
    pessimistic: MoneySchema,
    base: MoneySchema,
    optimistic: MoneySchema,
  }),
  disclosures: z.array(z.string()),
});
export type SimulationChartPayload = z.infer<typeof SimulationChartPayloadSchema>;

export const FeeLineSchema = z.object({ name: z.string(), amount: MoneySchema });

export const FeeBreakdownPayloadSchema = z.object({
  as_of: z.string(),
  fees: z.array(FeeLineSchema),
  estimated_isr_withholding: MoneySchema,
  total: MoneySchema,
  disclosures: z.array(z.string()),
});
export type FeeBreakdownPayload = z.infer<typeof FeeBreakdownPayloadSchema>;

export const OperationSchema = z.object({
  operation_id: z.string(),
  date: z.string(),
  type: z.enum(['BUY', 'SELL', 'DIVIDEND', 'FEE', 'SWITCH', 'REDEEM']),
  product_id: z.string(),
  amount: MoneySchema,
  status: z.string(),
});
export type Operation = z.infer<typeof OperationSchema>;

export const TransactionListPayloadSchema = z.object({
  as_of: z.string(),
  items: z.array(OperationSchema),
});
export type TransactionListPayload = z.infer<typeof TransactionListPayloadSchema>;

export const StatementLinkPayloadSchema = z.object({
  as_of: z.string(),
  year: z.number(),
  month: z.number(),
  url: z.string(),
  expires_at: z.string(),
});
export type StatementLinkPayload = z.infer<typeof StatementLinkPayloadSchema>;

export const GuideSectionSchema = z.object({
  id: z.string(),
  title: z.string(),
  text: z.string(),
});

export const ServicesGuidePayloadSchema = z.object({
  as_of: z.string(),
  version: z.string(),
  section: z.string(),
  sections: z.array(GuideSectionSchema),
  download_url: z.string(),
});
export type ServicesGuidePayload = z.infer<typeof ServicesGuidePayloadSchema>;

export const SuitabilityEvaluationSchema = z.object({
  product_id: z.string(),
  outcome: z.string(),
  rule_id: z.string().nullable().optional(),
  rationale: z.string(),
  warnings: z.array(z.string()),
});
export type SuitabilityEvaluation = z.infer<typeof SuitabilityEvaluationSchema>;

export const SuitabilitySummaryPayloadSchema = z.object({
  verdict_id: z.string(),
  ruleset_version: z.number(),
  evaluations: z.array(SuitabilityEvaluationSchema),
});
export type SuitabilitySummaryPayload = z.infer<typeof SuitabilitySummaryPayloadSchema>;

export const EscalationCardPayloadSchema = z.object({
  as_of: z.string(),
  case_id: z.string(),
  sla: z.string(),
  promotor_name: z.string(),
  reason: z.string(),
});
export type EscalationCardPayload = z.infer<typeof EscalationCardPayloadSchema>;

export const ComplaintCardPayloadSchema = z.object({
  as_of: z.string(),
  folio: z.string(),
  category: z.string(),
  response_deadline: z.string(),
  condusef_notice: z.string(),
});
export type ComplaintCardPayload = z.infer<typeof ComplaintCardPayloadSchema>;

export const EscalationOfferPayloadSchema = z.object({
  reason: z.string(),
  cta_es: z.string(),
});
export type EscalationOfferPayload = z.infer<typeof EscalationOfferPayloadSchema>;

export const ProfileUpdateOfferPayloadSchema = z.object({
  reason: z.string(),
  cta_es: z.string(),
});
export type ProfileUpdateOfferPayload = z.infer<typeof ProfileUpdateOfferPayloadSchema>;

export const DisclosurePayloadSchema = z.object({
  id: z.string(),
  text: z.string(),
  version: z.union([z.string(), z.number()]).nullable().optional(),
});
export type DisclosurePayload = z.infer<typeof DisclosurePayloadSchema>;

export const FormProductSchema = z.object({
  product_id: z.string(),
  name: z.string().optional(),
});

export const FormFieldSchema = z.object({
  name: z.string(),
  label_es: z.string().optional(),
  type: z.string().optional(),
  required: z.boolean().optional(),
});

export const FormSpecPayloadSchema = z.object({
  form_id: z.string(),
  operation: z.enum(['BUY', 'SELL', 'SWITCH', 'REDEEM', 'RECURRING']),
  product: FormProductSchema.passthrough(),
  target_product: FormProductSchema.passthrough().nullable().optional(),
  approved_amount: MoneySchema.nullable().optional(),
  fields: z.array(FormFieldSchema.passthrough()),
  expires_at: z.string(),
});
export type FormSpecPayload = z.infer<typeof FormSpecPayloadSchema>;

export const OrderReceiptPayloadSchema = z.object({
  order_id: z.string().nullable().optional(),
  status: z.string().nullable().optional(),
  settlement_date: z.string().nullable().optional(),
  operation: z.string(),
  product: FormProductSchema.passthrough(),
  form_id: z.string(),
  suitability_verdict_id: z.string().nullable().optional(),
});
export type OrderReceiptPayload = z.infer<typeof OrderReceiptPayloadSchema>;

/**
 * The server's closed component registry (graph/state.py::UIComponentType).
 * Every entry must have a case in the client renderer; a type here without
 * one is an undelivered client release, not a silent drop.
 */
export const UI_COMPONENT_TYPES = [
  'portfolio_summary',
  'portfolio_positions',
  'attribution_bars',
  'cash_summary',
  'product_list',
  'product_detail',
  'product_comparison',
  'quote_table',
  'news_list',
  'research_list',
  'calendar_list',
  'simulation_chart',
  'fee_breakdown',
  'transaction_list',
  'statement_link',
  'accounts_list',
  'services_guide',
  'suitability_summary',
  'warning_banner',
  'form_spec',
  'citations',
  'escalation_offer',
  'escalation_card',
  'complaint_card',
  'order_receipt',
  'disclosure',
  'profile_update_offer',
] as const;
export type UIComponentType = (typeof UI_COMPONENT_TYPES)[number];

export const UIComponentSchema = z.union([
  z.object({
    type: z.literal('portfolio_summary'),
    payload: PortfolioSummaryPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('portfolio_positions'),
    payload: PortfolioPositionsPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('attribution_bars'),
    payload: AttributionBarsPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('cash_summary'),
    payload: CashSummaryPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('accounts_list'),
    payload: AccountsListPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('product_list'),
    payload: ProductListPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('product_comparison'),
    payload: ProductListPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('product_detail'),
    payload: ProductDetailPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('quote_table'),
    payload: QuoteTablePayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('market_quote'),
    payload: MarketQuotePayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('news_list'),
    payload: NewsListPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('research_list'),
    payload: NewsListPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('calendar_list'),
    payload: CalendarListPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('simulation_chart'),
    payload: SimulationChartPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('fee_breakdown'),
    payload: FeeBreakdownPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('transaction_list'),
    payload: TransactionListPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('statement_link'),
    payload: StatementLinkPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('services_guide'),
    payload: ServicesGuidePayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('suitability_summary'),
    payload: SuitabilitySummaryPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('warning_banner'),
    payload: WarningBannerPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('form_spec'),
    payload: FormSpecPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('order_receipt'),
    payload: OrderReceiptPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('citations'),
    payload: CitationsPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('escalation_offer'),
    payload: EscalationOfferPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('escalation_card'),
    payload: EscalationCardPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('complaint_card'),
    payload: ComplaintCardPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('disclosure'),
    payload: DisclosurePayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('profile_update_offer'),
    payload: ProfileUpdateOfferPayloadSchema,
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
  // Unknown types still parse so the renderer can surface them instead of
  // dropping them silently (docs/03-mobile/01 4: adding a type is a client release).
  z.object({
    type: z.string(),
    payload: z.record(z.unknown()).optional(),
    as_of: z.string().nullable().optional(),
    source: z.string().nullable().optional(),
  }),
]);
export type UIComponent = z.infer<typeof UIComponentSchema>;

export const SseTokenEventSchema = z.object({ text: z.string() });
export type SseTokenEvent = z.infer<typeof SseTokenEventSchema>;

export const SseCitationsEventSchema = z.object({ items: z.array(CitationSchema) });
export type SseCitationsEvent = z.infer<typeof SseCitationsEventSchema>;

export const SseErrorEventSchema = z.object({
  code: z.string(),
  message: z.string(),
  escalate: z.boolean().optional(),
});
export type SseErrorEvent = z.infer<typeof SseErrorEventSchema>;

export const SseDoneEventSchema = z.object({
  turn_id: z.string(),
  evidence_id: z.string(),
  service_type: z.string(),
  service_subtype: z.string().optional(),
  intent: z.string().optional(),
  degraded_from: z.string().nullable().optional(),
  disclosures_shown: z.record(z.string()).optional(),
});
export type SseDoneEvent = z.infer<typeof SseDoneEventSchema>;

export const SseFormSpecEventSchema = z.object({ form_id: z.string() }).passthrough();
export type SseFormSpecEvent = z.infer<typeof SseFormSpecEventSchema>;

export type SseEventName = 'token' | 'ui' | 'citations' | 'form_spec' | 'error' | 'done';

export const ChatMessageRequestSchema = z.object({
  text: z.string().min(1),
  locale: z.string().optional(),
  client_turn_id: z.string().optional(),
});
export type ChatMessageRequest = z.infer<typeof ChatMessageRequestSchema>;

export const ConsentTypeSchema = z.enum([
  'privacy_notice',
  'investment_services_guide',
  'ai_disclosure',
  'voice_recording',
  'model_improvement',
]);
export type ConsentType = z.infer<typeof ConsentTypeSchema>;

export const ConsentViewSchema = z.object({
  type: ConsentTypeSchema,
  public_id: z.string(),
  current_version: z.string(),
  granted: z.boolean(),
  granted_version: z.string().nullable().optional(),
  granted_at: z.string().nullable().optional(),
  revoked_at: z.string().nullable().optional(),
  required_for: z.enum(['first_turn', 'voice', 'optional']),
});
export type ConsentView = z.infer<typeof ConsentViewSchema>;

export const ConsentAckRequestSchema = z.object({
  type: ConsentTypeSchema,
  version: z.string(),
  granted: z.boolean(),
  channel: z.enum(['chat', 'voice', 'app']),
});
export type ConsentAckRequest = z.infer<typeof ConsentAckRequestSchema>;

export const ConsentsResponseSchema = z.object({
  consents: z.array(ConsentViewSchema),
});
export type ConsentsResponse = z.infer<typeof ConsentsResponseSchema>;

export const ClientConfigResponseSchema = z.object({
  kill_switch: z.boolean(),
  kill_switch_message: z.string().optional(),
  voice_mode: z.record(z.unknown()).optional(),
  advisory: z.record(z.unknown()).optional(),
  transactional: z.record(z.unknown()).optional(),
  avatar: z.record(z.unknown()).optional(),
  disclosure_versions: z.record(z.string()).optional(),
  promotor: z
    .object({
      name: z.string().optional(),
      phone: z.string().optional(),
      hours: z.string().optional(),
    })
    .optional(),
  poll_interval_s: z.number().optional(),
});
export type ClientConfigResponse = z.infer<typeof ClientConfigResponseSchema>;

export const InvestorSummarySchema = z.object({
  id_cliente_pk: z.number(),
  numero_cliente_unico: z.number(),
  nombre_completo: z.string(),
  rfc: z.string(),
  correo_electronico: z.string().nullish(),
  perfil_riesgo: z.string().nullish(),
  total_contratos: z.number().optional(),
});
export type InvestorSummary = z.infer<typeof InvestorSummarySchema>;

export const InvestorsListResponseSchema = z.object({
  investors: z.array(InvestorSummarySchema),
  total: z.number(),
});
export type InvestorsListResponse = z.infer<typeof InvestorsListResponseSchema>;

export const DevTokenRequestSchema = z.object({
  client_id: z.string(),
  roles: z.array(z.string()).optional(),
  ttl_s: z.number().min(60).max(86400).optional(),
});
export type DevTokenRequest = z.infer<typeof DevTokenRequestSchema>;

export const DevTokenResponseSchema = z.object({
  access_token: z.string(),
  client_id: z.string(),
  token_type: z.string().optional(),
  expires_in: z.number(),
});
export type DevTokenResponse = z.infer<typeof DevTokenResponseSchema>;

export const AvatarSessionResponseSchema = z.object({
  avatar_session_id: z.string(),
  livekit_url: z.string(),
  livekit_client_token: z.string(),
  max_session_duration_s: z.number(),
  expires_at: z.string(),
  audio_ws_path: z.string(),
  emulated: z.boolean().optional(),
});
export type AvatarSessionResponse = z.infer<typeof AvatarSessionResponseSchema>;

// ============================================================
// Embed bridge protocol (v1) — WebView <-> host app postMessage
// ============================================================

export const EMBED_BRIDGE_VERSION = 1 as const;

/** Host app -> WebView commands. */
export const EmbedCommandSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('start') }),
  z.object({ type: z.literal('stop') }),
  z.object({
    type: z.literal('setMuted'),
    payload: z.object({ muted: z.boolean() }),
  }),
]);
export type EmbedCommand = z.infer<typeof EmbedCommandSchema>;

/** WebView -> host app events. */
export const EmbedEventSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('sessionState'),
    payload: z.object({ state: z.string(), quality: z.string() }),
  }),
  z.object({
    type: z.literal('message'),
    payload: z.object({
      sender: z.enum(['user', 'avatar']),
      message: z.string(),
      timestamp: z.number(),
    }),
  }),
  z.object({ type: z.literal('error'), payload: z.object({ message: z.string() }) }),
  z.object({
    type: z.literal('ended'),
    payload: z.object({ reason: z.enum(['user', 'server', 'error']) }),
  }),
]);
export type EmbedEvent = z.infer<typeof EmbedEventSchema>;

export const EmbedEnvelopeSchema = z.object({
  version: z.literal(EMBED_BRIDGE_VERSION),
  ts: z.number(),
  message: z.union([EmbedCommandSchema, EmbedEventSchema]),
});
export type EmbedEnvelope = z.infer<typeof EmbedEnvelopeSchema>;
