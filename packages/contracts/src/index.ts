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
});
export type Disclosure = z.infer<typeof DisclosureSchema>;

export const SessionResponseSchema = z.object({
  thread_id: z.string(),
  capabilities: CapabilitiesSchema,
  disclosures_required: z.array(DisclosureSchema),
  client: z.object({
    first_name: z.string(),
    risk_category: z.string(),
  }),
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

export const CitationSchema = z.object({
  title: z.string(),
  url: z.string().optional(),
  published: z.string().optional(),
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

export const UIComponentSchema = z.discriminatedUnion('type', [
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
  service_type: z.enum(['asesorado', 'no_asesorado']),
});
export type SseDoneEvent = z.infer<typeof SseDoneEventSchema>;

export type SseEventName = 'token' | 'ui' | 'citations' | 'error' | 'done';

export const ChatMessageRequestSchema = z.object({
  message: z.string().min(1),
});
export type ChatMessageRequest = z.infer<typeof ChatMessageRequestSchema>;
