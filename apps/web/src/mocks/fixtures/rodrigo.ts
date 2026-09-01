import type {
  Account,
  Advisor,
  Attribution,
  FormDraft,
  InvestorProfile,
  Portfolio,
  PortfolioSummary,
  Position,
  Product,
  SuggestionChip,
  User,
} from '../schemas';
import { AccountSchema, AdvisorSchema, InvestorProfileSchema, UserSchema } from '../schemas';

const AS_OF = '2026-09-01T18:00:00-06:00';

export const rodrigoUser: User = UserSchema.parse({
  id: 'cli_rodrigo_001',
  firstName: 'Rodrigo',
  lastName: 'Beltrán',
  initials: 'DR',
  email: 'rodrigo.beltran@example.com',
});

export const fernandaAdvisor: Advisor = AdvisorSchema.parse({
  id: 'adv_fernanda_001',
  firstName: 'Fernanda',
  lastName: 'Ruvalcaba',
  title: 'Asesora Patrimonial',
  branch: 'Centro Financiero Guadalajara',
  nextAvailableSlot: '2026-09-04T09:30:00-06:00',
});

export const rodrigoProfile: InvestorProfile = InvestorProfileSchema.parse({
  riskCategory: 'moderado',
  horizonMonths: 36,
  knowledgeLevel: 'intermedio',
  objectives: [
    'Preservar capital para universidad del hijo (USD, 14 meses)',
    'Colocar efectivo idle sin perder liquidez',
  ],
  assessedAt: '2023-06-15',
  expiresAt: '2026-06-15',
  version: 3,
});

/** Storyboard Explorar card — simplified totals */
export const explorarSummary: PortfolioSummary = {
  marketValue: { amount: '948250.00', currency: 'MXN' },
  periodReturnPct: -2.4,
  periodReturnAmount: { amount: '-22758.00', currency: 'MXN' },
  dayReturnAmount: { amount: '1032.00', currency: 'MXN' },
  period: '1M',
  asOf: AS_OF,
};

/** Persona-level book — used in conversation depth */
export const fullPortfolioSummary: PortfolioSummary = {
  marketValue: { amount: '14500000.00', currency: 'MXN' },
  periodReturnPct: -0.8,
  period: 'YTD',
  asOf: AS_OF,
};

export const rodrigoPositions: Position[] = [
  {
    id: 'pos_cetes_28d',
    symbol: 'CETES28',
    name: 'CETES 28d',
    assetClass: 'renta_fija_gubernamental',
    marketValue: { amount: '15200.00', currency: 'MXN' },
    weightPct: 1.6,
    periodReturnPct: 1.2,
    asOf: AS_OF,
  },
  {
    id: 'pos_actiren',
    symbol: 'ACTIREN',
    name: 'ACTIREN',
    assetClass: 'renta_fija_corporativa',
    marketValue: { amount: '23050.00', currency: 'MXN' },
    weightPct: 2.4,
    periodReturnPct: 0.8,
    asOf: AS_OF,
  },
  {
    id: 'pos_naftrac',
    symbol: 'NAFTRAC',
    name: 'NAFTRAC',
    assetClass: 'renta_variable',
    marketValue: { amount: '10000.00', currency: 'MXN' },
    weightPct: 1.1,
    periodReturnPct: 3.5,
    asOf: AS_OF,
  },
];

export const rodrigoAccounts: Account[] = AccountSchema.array().parse([
  {
    id: 'acc_cuenta_001',
    label: 'Cuenta de inversión',
    type: 'cuenta',
    balance: { amount: '3041200.00', currency: 'MXN' },
    available: { amount: '3041200.00', currency: 'MXN' },
    asOf: AS_OF,
  },
]);

export const rodrigoProducts: Product[] = [
  {
    id: 'prod_actiren_plus',
    symbol: 'ACTIREN+',
    name: 'Actinver Renta Fija Plus',
    type: 'Fondo de deuda',
    profile: {
      riskLevel: 'bajo',
      complexity: 'baja',
      liquidity: 'T+1',
      minimumInvestment: { amount: '100000.00', currency: 'MXN' },
      committeeVersion: 12,
    },
    feesDescription: 'Comisión 1.25% anual + IVA',
    eligible: true,
  },
  {
    id: 'prod_uditracs',
    symbol: 'UDITRACS',
    name: 'UDITRACS (UDI + cobertura cambiaria)',
    type: 'ETF de deuda',
    profile: {
      riskLevel: 'bajo',
      complexity: 'media',
      liquidity: 'Intradiario',
      minimumInvestment: { amount: '10000.00', currency: 'MXN' },
      committeeVersion: 12,
    },
    feesDescription: 'Comisión 0.45% + IVA',
    eligible: true,
  },
  {
    id: 'prod_nota_estructurada',
    symbol: 'NE-2026',
    name: 'Nota estructurada multi-activo 2026',
    type: 'Nota estructurada',
    profile: {
      riskLevel: 'alto',
      complexity: 'alta',
      liquidity: 'No líquido hasta vencimiento',
      minimumInvestment: { amount: '500000.00', currency: 'MXN' },
      committeeVersion: 12,
    },
    feesDescription: 'Estructura embebida en precio',
    eligible: false,
    ineligibilityReason: 'Complejidad y riesgo alto no son congruentes con su perfil moderado.',
  },
];

export const portfolioAttribution: Attribution = {
  period: '1M',
  totalReturnPct: -2.4,
  asOf: AS_OF,
  items: [
    {
      positionId: 'pos_naftrac',
      label: 'NAFTRAC',
      contributionBps: -210,
      reason: 'Caída del mercado accionario local tras datos de empleo en EE.UU.',
      citationTitle: 'BMV: índice de referencia −1.8% en la semana',
    },
    {
      positionId: 'pos_actiren',
      label: 'ACTIREN',
      contributionBps: 12,
      reason: 'Spread corporativo estable; cupones aportaron positivo.',
    },
    {
      positionId: 'pos_cetes_28d',
      label: 'CETES 28d',
      contributionBps: 8,
      reason: 'Reinversión a tasa Banxico sin cambio material.',
      citationTitle: 'Banxico mantiene tasa de referencia',
      citationUrl: 'https://www.banxico.org.mx/',
    },
  ],
};

export const defaultChips: SuggestionChip[] = [
  { id: 'chip_horizon', label: 'Horizonte 1–3 años' },
  { id: 'chip_fixed', label: 'Renta fija' },
  { id: 'chip_liquidity', label: 'Liquidez diaria' },
];

export const openingMessage =
  'Hola, soy Tino. Le ayudo a entender su portafolio, explorar instrumentos y preparar lo que necesite firmar. No ejecuto operaciones ni predigo mercados — para eso está Fernanda, su asesora. ¿Qué le gustaría revisar hoy?';

export const sampleFormDraft: FormDraft = {
  id: 'form_001',
  title: 'Inversión en Actinver Renta Fija Plus',
  productName: 'Actinver Renta Fija Plus',
  amount: { amount: '1800000.00', currency: 'MXN' },
  settlementDate: '2026-09-02',
  prefilledFields: {
    nombre: 'Rodrigo Beltrán Ochoa',
    cuenta: 'acc_cuenta_001',
    perfil: 'Moderado',
  },
  keyTermsPlainLanguage: [
    'Liquidez T+1 en días hábiles bursátiles.',
    'Monto mínimo MXN 100,000. Comisión 1.25% anual + IVA.',
    'El rendimiento no está garantizado.',
  ],
};

export const rodrigoFixture = {
  user: rodrigoUser,
  advisor: fernandaAdvisor,
  investorProfile: rodrigoProfile,
  explorarSummary,
  fullPortfolioSummary,
  positions: rodrigoPositions,
  accounts: rodrigoAccounts,
  products: rodrigoProducts,
  attribution: portfolioAttribution,
  defaultChips,
  openingMessage,
  sampleFormDraft,
} as const;

export function getExplorarPortfolio(): Portfolio {
  return { summary: explorarSummary, positions: rodrigoPositions };
}

export function getFullPortfolio(): Portfolio {
  return { summary: fullPortfolioSummary, positions: rodrigoPositions };
}

export function getIdleCashAccount(): Account {
  return rodrigoAccounts[0];
}
