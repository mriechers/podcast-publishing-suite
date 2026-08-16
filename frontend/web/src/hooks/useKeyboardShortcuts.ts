import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export interface KeyboardShortcut {
  key: string
  description: string
  category: string
}

export function getKeyboardShortcuts(): KeyboardShortcut[] {
  return [
    { key: 'g + h', description: 'Go to Dashboard', category: 'Navigation' },
    { key: 'g + i', description: 'Go to Items', category: 'Navigation' },
    { key: 'g + s', description: 'Go to Settings', category: 'Navigation' },
    { key: 'g + y', description: 'Go to System', category: 'Navigation' },
    { key: '/', description: 'Focus search input', category: 'Actions' },
    { key: '?', description: 'Show keyboard shortcuts', category: 'Actions' },
  ]
}

interface UseKeyboardShortcutsOptions {
  onShowHelp?: () => void
}

export function useKeyboardShortcuts(options: UseKeyboardShortcutsOptions = {}) {
  const navigate = useNavigate()
  const { onShowHelp } = options

  useEffect(() => {
    let lastKey: string | null = null
    let lastKeyTime = 0

    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      const target = e.target as HTMLElement
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        // Allow '/' to focus search even in inputs
        if (e.key !== '/') {
          return
        }
      }

      const now = Date.now()
      const timeSinceLastKey = now - lastKeyTime

      // Handle '?' for help
      if (e.key === '?' && !e.shiftKey) {
        e.preventDefault()
        onShowHelp?.()
        return
      }

      // Handle '/' for search focus
      if (e.key === '/') {
        e.preventDefault()
        const searchInput = document.getElementById('items-search') as HTMLInputElement
        if (searchInput) {
          searchInput.focus()
          searchInput.select()
        }
        return
      }

      // Handle 'g' key sequences (must be within 1 second)
      if (e.key === 'g') {
        lastKey = 'g'
        lastKeyTime = now
        return
      }

      // Check if this is part of a 'g + X' sequence
      if (lastKey === 'g' && timeSinceLastKey < 1000) {
        e.preventDefault()

        switch (e.key) {
          case 'h':
            navigate('/')
            break
          case 'i':
            navigate('/items')
            break
          case 's':
            navigate('/settings')
            break
          case 'y':
            navigate('/system')
            break
        }

        lastKey = null
        lastKeyTime = 0
      } else {
        lastKey = null
      }
    }

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [navigate, onShowHelp])
}
