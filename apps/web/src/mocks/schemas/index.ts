import { z } from 'zod';

export const MoneySchema = z.object({
  amount: z.string(),
  currency: z.literal('MXN'),
});
export type Money = z.infer<typeof MoneySchema>;

export const UserSchema = z.object({
  id: z.string(),
  firstName: z.string(),
  lastName: z.string(),
  initials: z.string().length(2),
  email: z.string().email().optional(),
  curp: z.string().optional(),
});
export type User = z.infer<typeof UserSchema>;

export const AdvisorSchema = z.object({
  id: z.string(),
  firstName: z.string(),
  lastName: z.string(),
  title: z.string(),
  branch: z.string(),
  photoUrl: z.string().url().optional(),
  nextAvailableSlot: z.string().optional(),
});
export type Advisor = z.infer<typeof AdvisorSchema>;

export const InvestorProfileSchema = z.object({
  riskCategory: z.enum(['conservador', 'moderado', 'crecimiento', 'agresivo']),
  horizonMonths: z.number().int().positive(),
  knowledgeLevel: z.enum(['basico', 'intermedio', 'avanzado']),
  objectives: z.array(z.string()),
  assessedAt: z.string(),
  expiresAt: z.string().optional(),
  version: z.number().int(),
});
export type InvestorProfile = z.infer<typeof InvestorProfileSchema>;

export const AccountSchema = z.object({
  id: z.string(),
  label: z.string(),
  type: z.enum(['cuenta', 'inversion', 'retiro']),
  balance: MoneySchema,
  available: MoneySchema,
  asOf: z.string(),
});
export type Account = z.infer<typeof AccountSchema>;

export const PositionSchema = z.object({
  id: z.string(),
  symbol: z.string(),
  name: z.string(),
  assetClass: z.enum([
    'renta_fija_gubernamental',
    'renta_fija_corporativa',
    'renta_variable',
    'efectivo',
    'otro',
  ]),
  quantity: z.number().optional(),
  marketValue: MoneySchema,
  weightPct: z.number(),
  periodReturnPct: z.number(),
  costBasis: MoneySchema.optional(),
  asOf: z.string(),
});
export type Position = z.infer<typeof PositionSchema>;

export const PortfolioSummarySchema = z.object({
  marketValue: MoneySchema,
  periodReturnPct: z.number(),
  periodReturnAmount: MoneySchema.optional(),
  dayReturnAmount: MoneySchema.optional(),
  period: z.string(),
  asOf: z.string(),
});
export type PortfolioSummary = z.infer<typeof PortfolioSummarySchema>;

export const PortfolioSchema = z.object({
  summary: PortfolioSummarySchema,
  positions: z.array(PositionSchema),
});
export type Portfolio = z.infer<typeof PortfolioSchema>;

export const ProductProfileSchema = z.object({
  riskLevel: z.enum(['bajo', 'medio', 'alto']),
  complexity: z.enum(['baja', 'media', 'alta']),
  liquidity: z.string(),
  minimumInvestment: MoneySchema,
  committeeVersion: z.number().int(),
});
export type ProductProfile = z.infer<typeof ProductProfileSchema>;

export const ProductSchema = z.object({
  id: z.string(),
  symbol: z.string(),
  name: z.string(),
  type: z.string(),
  profile: ProductProfileSchema,
  feesDescription: z.string(),
  diciUrl: z.string().url().optional(),
  eligible: z.boolean(),
  ineligibilityReason: z.string().optional(),
});
export type Product = z.infer<typeof ProductSchema>;

export const AttributionItemSchema = z.object({
  positionId: z.string(),
  label: z.string(),
  contributionBps: z.number(),
  reason: z.string(),
  citationTitle: z.string().optional(),
  citationUrl: z.string().url().optional(),
});
export type AttributionItem = z.infer<typeof AttributionItemSchema>;

export const AttributionSchema = z.object({
  period: z.string(),
  totalReturnPct: z.number(),
  items: z.array(AttributionItemSchema),
  asOf: z.string(),
});
export type Attribution = z.infer<typeof AttributionSchema>;

export const SuggestionChipSchema = z.object({
  id: z.string(),
  label: z.string(),
});
export type SuggestionChip = z.infer<typeof SuggestionChipSchema>;

export const SuitabilityJustificationSchema = z.object({
  productId: z.string(),
  productName: z.string(),
  outcome: z.literal('APTO'),
  clientProfileSummary: z.string(),
  productProfileSummary: z.string(),
  rationale: z.string(),
  rulesetVersion: z.number().int(),
});
export type SuitabilityJustification = z.infer<typeof SuitabilityJustificationSchema>;

export const BlockedProductSchema = z.object({
  productId: z.string(),
  productName: z.string(),
  outcome: z.literal('NO_APTO'),
  mismatch: z.string(),
  educationOffer: z.string().optional(),
});
export type BlockedProduct = z.infer<typeof BlockedProductSchema>;

export const HandoffBriefingSchema = z.object({
  clientQuestion: z.string(),
  summary: z.string(),
  productsExplored: z.array(z.string()),
  simulationsRun: z.array(z.string()),
  blockedItems: z.array(z.string()),
  pendingDocuments: z.array(z.string()),
  advisorId: z.string(),
});
export type HandoffBriefing = z.infer<typeof HandoffBriefingSchema>;

export const FormDraftSchema = z.object({
  id: z.string(),
  title: z.string(),
  productName: z.string(),
  amount: MoneySchema,
  settlementDate: z.string(),
  prefilledFields: z.record(z.string(), z.string()),
  keyTermsPlainLanguage: z.array(z.string()),
});
export type FormDraft = z.infer<typeof FormDraftSchema>;
