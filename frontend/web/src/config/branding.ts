import brandingData from '../../../branding.json'

export interface BrandingConfig {
  appName: string
  appVersion: string
  orgName: string
  logoUrl: string
  colors: {
    primary: string
    secondary: string
  }
  storageKey: string
}

export const branding: BrandingConfig = brandingData as BrandingConfig

/**
 * Inject brand colors as CSS custom properties on :root.
 * Called once at app startup from main.tsx.
 */
export function applyBrandColors(): void {
  const root = document.documentElement
  root.style.setProperty('--color-brand-primary', branding.colors.primary)
  root.style.setProperty('--color-brand-secondary', branding.colors.secondary)
}
