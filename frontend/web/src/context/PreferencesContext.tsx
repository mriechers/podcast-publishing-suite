import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { branding } from '../config/branding'

export type TextSize = 'default' | 'large' | 'larger'

export interface UserPreferences {
  reduceMotion: boolean
  textSize: TextSize
  highContrast: boolean
}

interface PreferencesContextType {
  preferences: UserPreferences
  updatePreferences: (updates: Partial<UserPreferences>) => void
}

const PreferencesContext = createContext<PreferencesContextType | undefined>(undefined)

const DEFAULT_PREFERENCES: UserPreferences = {
  reduceMotion: false,
  textSize: 'default',
  highContrast: false,
}

function getSystemPreferences(): Partial<UserPreferences> {
  const systemPrefs: Partial<UserPreferences> = {}
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    systemPrefs.reduceMotion = true
  }
  if (window.matchMedia('(prefers-contrast: more)').matches) {
    systemPrefs.highContrast = true
  }
  return systemPrefs
}

function loadPreferences(): UserPreferences {
  try {
    const stored = localStorage.getItem(branding.storageKey)
    if (stored) {
      const parsed = JSON.parse(stored)
      return { ...DEFAULT_PREFERENCES, ...parsed }
    }
  } catch (error) {
    console.error('Failed to load preferences from localStorage:', error)
  }
  const systemPrefs = getSystemPreferences()
  return { ...DEFAULT_PREFERENCES, ...systemPrefs }
}

function savePreferences(preferences: UserPreferences): void {
  try {
    localStorage.setItem(branding.storageKey, JSON.stringify(preferences))
  } catch (error) {
    console.error('Failed to save preferences to localStorage:', error)
  }
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState<UserPreferences>(loadPreferences)

  useEffect(() => {
    savePreferences(preferences)
  }, [preferences])

  const updatePreferences = (updates: Partial<UserPreferences>) => {
    setPreferences((prev) => ({ ...prev, ...updates }))
  }

  return (
    <PreferencesContext.Provider value={{ preferences, updatePreferences }}>
      {children}
    </PreferencesContext.Provider>
  )
}

export function usePreferences() {
  const context = useContext(PreferencesContext)
  if (!context) {
    throw new Error('usePreferences must be used within PreferencesProvider')
  }
  return context
}
