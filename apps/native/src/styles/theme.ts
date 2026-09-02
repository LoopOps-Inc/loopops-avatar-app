/**
 * Actinver / LoopOps design tokens adapted for React Native Stylesheet.
 */
export const theme = {
  colors: {
    background: '#0b121f', // Dark background as specified in App.tsx / splash
    surface: '#0f172a',
    surfaceSecondary: '#1e293b',
    text: '#ffffff',
    textMuted: '#94a3b8',
    
    // Core neutral primitives
    neutral0: '#ffffff',
    neutral5: '#fafafa',
    neutral10: '#f5f5f5',
    neutral20: '#eeeeee',
    neutral30: '#e2e2e2',
    neutral40: '#bebebe',
    neutral50: '#9a9a9a',
    neutral55: '#7d7d7d',
    neutral60: '#525252',
    neutral70: '#2f2f2f',
    neutral80: '#1a1a1a',
    neutral90: '#0f0f0f',

    // Brand colors
    brandAccent: '#0431c0',
    brandAccentLight: '#dfe5f9',
    brandInk: '#041e41',
    brandGold: '#927b2f',
    brandGoldBright: '#f0ca4d',

    // Chat bubbles and borders
    chatBg: '#f7f8fa',
    chatBorder: '#e2e4e9',
    chatBorderSoft: '#ebebeb',
    chatMeta: '#4b5563',
    chatDate: '#6d7382',
    chatPlaceholder: '#9398a5',

    // Actinver CTA style
    ctaBg: '#f0ca4d',
    ctaFg: '#041e41',

    // Semantic status
    success: '#31a147',
    successBg: '#eaf6ed',
    error: '#c53f3f',
    errorBg: '#f6e4e4',
    warning: '#a48823',
    warningBg: '#f0ead1',
    info: '#6581d9',
    infoBg: '#dfe5f9',
    
    // Alphas
    blackA40: 'rgba(12, 12, 13, 0.4)',
    blackA70: 'rgba(12, 12, 13, 0.7)',
    blackA80: 'rgba(12, 12, 13, 0.8)',
    whiteA10: 'rgba(255, 255, 255, 0.1)',
    whiteA20: 'rgba(255, 255, 255, 0.2)',
    whiteA40: 'rgba(255, 255, 255, 0.4)',
    whiteA80: 'rgba(255, 255, 255, 0.8)',
    whiteA90: 'rgba(255, 255, 255, 0.9)',
  },
  radius: {
    xs: 8,
    sm: 16,
    md: 24,
    lg: 32,
    cta: 26.5,
    bubble: 20,
    tail: 4,
    full: 999,
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    xxl: 24,
  },
};
