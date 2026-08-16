/**
 * Brand Configuration
 *
 * Colors, typography, and asset references for consistent branding
 * across all video compositions. Customize these values for your podcast.
 */

export const brand = {
  colors: {
    /** Primary brand green */
    primary: "#10a544",
    /** Darker green for gradients */
    primaryDark: "#0d8a38",
    /** Lighter green for highlights */
    primaryLight: "#15c752",

    /** Background black */
    backgroundDark: "#000000",
    /** Slightly lighter for depth */
    backgroundMedium: "#0a0a0a",
    /** Card/cabinet background */
    backgroundSurface: "#1a1a1a",

    /** Text colors */
    textPrimary: "#ffffff",
    textSecondary: "#cccccc",
    textMuted: "#888888",

    /** Accent colors for waveform/highlights */
    accentWarm: "#e94560", // Vibrant pink-red
    accentCool: "#4a90d9", // Cool blue
  },

  typography: {
    /** Headline font — Futura PT with Jost as free fallback */
    fontHeadline:
      '"Futura PT", "Jost", "Nunito Sans", sans-serif',
    /** Body font — Adobe Garamond Pro with EB Garamond as free fallback */
    fontBody:
      '"Adobe Garamond Pro", "EB Garamond", "Garamond", Georgia, serif',
    /** Legacy system font stack for backward compatibility */
    fontFamily:
      '"Futura PT", "Jost", "Nunito Sans", sans-serif',
    /** Weights */
    weights: {
      regular: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
  },

  assets: {
    /** Galaxy spiral background (for dark backgrounds) */
    galaxySpiral: "bg-galaxy-spiral-1200w@2x.png",
    /** Logo with cabinet icon only */
    logoIcon: "logo-primary-dark-bg-800w.png",
    /** Logo with wordmark */
    logoWordmark: "logo-primary-wordmark-dark-bg-800w.png",
  },

  show: {
    name: "Wonder Cabinet",
    tagline: "From the creators of To The Best Of Our Knowledge",
  },
} as const;

/**
 * Default color schemes for different video types
 */
export const colorSchemes = {
  /** Dark theme with green accents - primary brand look */
  dark: {
    primaryColor: brand.colors.backgroundDark,
    secondaryColor: brand.colors.backgroundMedium,
    accentColor: brand.colors.primary,
    waveformColor: brand.colors.primary,
    textColor: brand.colors.textPrimary,
  },

  /** Green-forward theme - bolder brand presence */
  green: {
    primaryColor: brand.colors.primaryDark,
    secondaryColor: brand.colors.primary,
    accentColor: brand.colors.primaryLight,
    waveformColor: brand.colors.textPrimary,
    textColor: brand.colors.textPrimary,
  },

  /** Warm accent theme - for energetic clips */
  warm: {
    primaryColor: brand.colors.backgroundDark,
    secondaryColor: "#1a0a10",
    accentColor: brand.colors.accentWarm,
    waveformColor: brand.colors.accentWarm,
    textColor: brand.colors.textPrimary,
  },
} as const;

export type ColorScheme = keyof typeof colorSchemes;
