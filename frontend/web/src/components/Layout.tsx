import { Outlet, NavLink } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'
import StatusBar from './StatusBar'
import { useKeyboardShortcuts, getKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import { usePreferences } from '../context/PreferencesContext'
import { branding } from '../config/branding'

export default function Layout() {
  const [showShortcuts, setShowShortcuts] = useState(false)
  const { preferences } = usePreferences()
  const modalRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useKeyboardShortcuts({
    onShowHelp: () => setShowShortcuts(true),
  })

  // Apply preferences to document root
  useEffect(() => {
    const root = document.documentElement

    // Text size
    root.classList.remove('text-default', 'text-large', 'text-larger')
    root.classList.add(`text-${preferences.textSize}`)

    // Reduce motion
    if (preferences.reduceMotion) {
      root.classList.add('reduce-motion')
    } else {
      root.classList.remove('reduce-motion')
    }

    // High contrast
    if (preferences.highContrast) {
      root.classList.add('high-contrast')
    } else {
      root.classList.remove('high-contrast')
    }
  }, [preferences])

  // Focus trap for modal
  useEffect(() => {
    if (!showShortcuts) return

    const modal = modalRef.current
    if (!modal) return

    const focusableElements = modal.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    const firstElement = focusableElements[0]
    const lastElement = focusableElements[focusableElements.length - 1]

    // Focus close button when modal opens
    closeButtonRef.current?.focus()

    const handleTabKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault()
          lastElement.focus()
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault()
          firstElement.focus()
        }
      }
    }

    const handleEscapeKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowShortcuts(false)
      }
    }

    document.addEventListener('keydown', handleTabKey)
    document.addEventListener('keydown', handleEscapeKey)

    return () => {
      document.removeEventListener('keydown', handleTabKey)
      document.removeEventListener('keydown', handleEscapeKey)
    }
  }, [showShortcuts])

  const shortcuts = getKeyboardShortcuts()
  const shortcutsByCategory = shortcuts.reduce((acc, shortcut) => {
    if (!acc[shortcut.category]) {
      acc[shortcut.category] = []
    }
    acc[shortcut.category].push(shortcut)
    return acc
  }, {} as Record<string, typeof shortcuts>)

  return (
    <div className="min-h-screen flex flex-col bg-gray-950 text-gray-100">
      {/* Skip to main content link for screen readers */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded"
      >
        Skip to main content
      </a>

      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-[1600px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {branding.logoUrl ? (
                <img
                  src={branding.logoUrl}
                  alt={branding.appName}
                  className="h-8"
                />
              ) : (
                <h1 className="text-xl font-bold">{branding.appName}</h1>
              )}
              <span className="text-sm text-gray-500">{branding.appVersion}</span>
            </div>

            <nav className="flex gap-6" role="navigation" aria-label="Main navigation">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  `text-sm hover:text-gray-100 transition-colors ${
                    isActive ? 'text-blue-400 font-semibold' : 'text-gray-400'
                  }`
                }
              >
                Dashboard
              </NavLink>
              <NavLink
                to="/items"
                className={({ isActive }) =>
                  `text-sm hover:text-gray-100 transition-colors ${
                    isActive ? 'text-blue-400 font-semibold' : 'text-gray-400'
                  }`
                }
              >
                Items
              </NavLink>
              <NavLink
                to="/settings"
                className={({ isActive }) =>
                  `text-sm hover:text-gray-100 transition-colors ${
                    isActive ? 'text-blue-400 font-semibold' : 'text-gray-400'
                  }`
                }
              >
                Settings
              </NavLink>
              <NavLink
                to="/system"
                className={({ isActive }) =>
                  `text-sm hover:text-gray-100 transition-colors ${
                    isActive ? 'text-blue-400 font-semibold' : 'text-gray-400'
                  }`
                }
              >
                System
              </NavLink>
              <NavLink
                to="/help"
                className={({ isActive }) =>
                  `text-sm hover:text-gray-100 transition-colors ${
                    isActive ? 'text-blue-400 font-semibold' : 'text-gray-400'
                  }`
                }
              >
                Help
              </NavLink>
            </nav>

            <button
              onClick={() => setShowShortcuts(true)}
              className="text-sm text-gray-400 hover:text-gray-100 transition-colors"
              aria-label="Show keyboard shortcuts"
            >
              ?
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main id="main-content" className="flex-1">
        <div className="max-w-[1600px] mx-auto px-6 py-6">
          <Outlet />
        </div>
      </main>

      {/* Status Bar */}
      <StatusBar />

      {/* Keyboard Shortcuts Modal */}
      {showShortcuts && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setShowShortcuts(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="shortcuts-title"
        >
          <div
            ref={modalRef}
            className="bg-gray-900 border border-gray-800 rounded-lg p-6 max-w-2xl w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h2 id="shortcuts-title" className="text-xl font-bold">
                Keyboard Shortcuts
              </h2>
              <button
                ref={closeButtonRef}
                onClick={() => setShowShortcuts(false)}
                className="text-gray-400 hover:text-gray-100 transition-colors"
                aria-label="Close keyboard shortcuts"
              >
                ✕
              </button>
            </div>

            <div className="space-y-6">
              {Object.entries(shortcutsByCategory).map(([category, categoryShortcuts]) => (
                <div key={category}>
                  <h3 className="text-sm font-semibold text-gray-400 mb-3">
                    {category}
                  </h3>
                  <div className="space-y-2">
                    {categoryShortcuts.map((shortcut) => (
                      <div
                        key={shortcut.key}
                        className="flex items-center justify-between"
                      >
                        <span className="text-sm">{shortcut.description}</span>
                        <kbd className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs font-mono">
                          {shortcut.key}
                        </kbd>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
