import { z } from 'zod';

/** Decimal money — amount is a string to avoid IEEE 754 issues. */
export const MoneySchema = z.object({
  amount: z.string(),
  currency: z.literal('MXN'),
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

export const WarningBannerPayloadSchema = z.object({
  severity: z.enum(['info', 'warning']),
  message: z.string(),
});
export type WarningBannerPayload = z.infer<typeof WarningBannerPayloadSchema>;

export const UIComponentSchema = z.union([
  z.object({
    type: z.literal('portfolio_summary'),
    payload: PortfolioSummaryPayloadSchema,
    as_of: z.string().optional(),
    source: z.string().optional(),
  }),
  z.object({
    type: z.literal('attribution_bars'),
    payload: AttributionBarsPayloadSchema,
    as_of: z.string().optional(),
    source: z.string().optional(),
  }),
  z.object({
    type: z.literal('market_quote'),
    payload: MarketQuotePayloadSchema,
    as_of: z.string().optional(),
    source: z.string().optional(),
  }),
  z.object({
    type: z.literal('citations'),
    payload: CitationsPayloadSchema,
    as_of: z.string().optional(),
    source: z.string().optional(),
  }),
  z.object({
    type: z.literal('warning_banner'),
    payload: WarningBannerPayloadSchema,
    as_of: z.string().optional(),
    source: z.string().optional(),
  }),
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
