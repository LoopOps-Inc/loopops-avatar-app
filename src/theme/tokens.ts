/**
 * LoopOps / Actinver design tokens for React Native.
 * Source: DESIGN.md (synced from loopops-web-app)
 */

export const colors = {
  neutral: {
    0: '#FFFFFF',
    5: '#FAFAFA',
    10: '#F5F5F5',
    15: '#F0F0F0',
    20: '#EEEEEE',
    30: '#E2E2E2',
    40: '#BEBEBE',
    50: '#9A9A9A',
    55: '#7D7D7D',
    60: '#525252',
    70: '#2F2F2F',
    80: '#1A1A1A',
    90: '#0F0F0F',
  },
  brandAccent: {
    0: '#DFE5F9',
    5: '#EAEEFB',
    20: '#C6D1F2',
    50: '#0431C0',
    60: '#021D73',
    70: '#011050',
  },
  success: { 10: '#EAF6ED', 50: '#31A147' },
  error: { 10: '#F6E4E4', 50: '#C53F3F' },
  warning: { 10: '#F0EAD1', 50: '#A48823' },
  info: { 10: '#DFE5F9', 50: '#6581D9' },
  element: {
    1: '#306EE1',
    2: '#40AD82',
    3: '#DD9B25',
    4: '#E7823F',
    5: '#D856A8',
  },
} as const;

export const spacing = {
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  7: 28,
  8: 32,
  10: 40,
  12: 48,
  16: 64,
  20: 80,
  24: 96,
  32: 128,
} as const;

export const radius = {
  xs: 8,
  xsInner: 6,
  sm: 16,
  md: 24,
  lg: 32,
  cta: 26.5,
  full: 999,
} as const;

export const fontSize = {
  xs: 8,
  sm: 11,
  md: 12,
  base: 14,
  lg: 16,
  xl: 18,
  '2xl': 20,
  '3xl': 24,
  '4xl': 32,
} as const;

export const fontFamily = {
  heading: 'Funnel Display',
  body: 'System',
} as const;

export const lineHeight = {
  tight: 1.2,
  heading: 1.3,
  normal: 1.5,
  relaxed: 1.75,
} as const;

export type ThemeColors = {
  surface: string;
  surfaceSub: string;
  content: string;
  contentSub: string;
  contentMuted: string;
  contentInverse: string;
  accent: string;
  accentFg: string;
  filledDark: string;
  filledDarkFg: string;
  outline: string;
  success: string;
  error: string;
  warning: string;
};

export type Theme = {
  colors: ThemeColors;
};

const lightColors: ThemeColors = {
  surface: colors.neutral[0],
  surfaceSub: colors.neutral[10],
  content: colors.neutral[90],
  contentSub: colors.neutral[60],
  contentMuted: colors.neutral[40],
  contentInverse: colors.neutral[0],
  accent: colors.brandAccent[50],
  accentFg: colors.neutral[0],
  filledDark: colors.neutral[70],
  filledDarkFg: colors.neutral[5],
  outline: colors.neutral[20],
  success: colors.success[50],
  error: colors.error[50],
  warning: colors.warning[50],
};

const darkColors: ThemeColors = {
  surface: colors.neutral[70],
  surfaceSub: colors.neutral[80],
  content: colors.neutral[5],
  contentSub: colors.neutral[20],
  contentMuted: colors.neutral[40],
  contentInverse: colors.neutral[90],
  accent: colors.brandAccent[50],
  accentFg: colors.neutral[0],
  filledDark: colors.neutral[15],
  filledDarkFg: colors.neutral[90],
  outline: colors.neutral[60],
  success: colors.success[50],
  error: colors.error[50],
  warning: colors.warning[50],
};

export function getTheme(isDark: boolean): Theme {
  return { colors: isDark ? darkColors : lightColors };
}
