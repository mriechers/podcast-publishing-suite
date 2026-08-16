import { useState, useEffect, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { branding } from '../config/branding'

const guideContent = `# ${branding.appName} Guide

Welcome to your dashboard. This guide covers everything you need to know.

## Getting Started

### Quick Start

1. Start the backend: run uvicorn with api.main:app on port 8000
2. Start the frontend: cd web and run npm run dev
3. Open http://localhost:3000 in your browser

### Dashboard Overview

The **Dashboard** page shows a summary of your items with stat cards and a recent items list. Click any item to view its details.

## Pages

### Dashboard

The home page displays:
- **Stat cards** showing counts by status (pending, active, completed, failed)
- **Recent items** list with quick links to details
- Real-time updates via WebSocket connection

### Items

The items page provides a full list view with:
- **Status filter tabs** to narrow results
- **Search** to find items by title
- **Pagination** for large datasets
- **Actions** to view details or delete items

### Item Detail

Click any item to see its full details including:
- Status with action buttons (Start, Complete, Retry, Delete)
- Priority and timestamps
- Description text
- Timeline showing creation and update history

### Settings

Customize your dashboard experience:
- **Reduce Motion** - Minimize animations for accessibility
- **Text Size** - Choose from default, large, or larger base font
- **High Contrast** - Boost contrast for better visibility

### System

Monitor your API connection:
- **Connection status** indicator with health check button
- **Troubleshooting** steps when the API is offline
- **Connection log** showing recent check results
- **API endpoint** reference for developers

## Keyboard Shortcuts

| Keys | Action |
|------|--------|
| g h | Go to Dashboard |
| g i | Go to Items |
| g s | Go to Settings |
| g y | Go to System |
| / | Focus search (on Items page) |
| ? | Show keyboard shortcuts |

## Customization

### Brand Colors

Edit branding.json in the project root to change:
- App name and version
- Organization name
- Primary and secondary colors
- Logo URL
- Local storage key for preferences

### Adding Pages

1. Create a new component in web/src/pages/
2. Add a route in App.tsx
3. Add a nav link in Layout.tsx
4. (Optional) Add a keyboard shortcut in useKeyboardShortcuts.ts

## Accessibility

This dashboard is built with accessibility in mind:
- **Skip navigation** link (press Tab on page load)
- **Focus management** with visible focus indicators
- **Keyboard navigation** for all interactive elements
- **Screen reader** support with ARIA labels and live regions
- **Reduced motion** support (system preference + manual toggle)
- **Focus trapping** in modals and dialogs
- **High contrast** mode for low-vision users

## Tech Stack

- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS
- **Backend:** FastAPI + Pydantic (Python)
- **Real-time:** WebSocket with auto-reconnect
- **Styling:** Tailwind CSS with dark theme + CSS custom properties
`

interface TocEntry {
  id: string
  text: string
  level: number
}

function extractToc(markdown: string): TocEntry[] {
  const headingRegex = /^(#{1,3})\s+(.+)$/gm
  const entries: TocEntry[] = []
  let match

  while ((match = headingRegex.exec(markdown)) !== null) {
    const level = match[1].length
    const text = match[2]
    const id = text
      .toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/\s+/g, '-')
    entries.push({ id, text, level })
  }

  return entries
}

export default function Help() {
  const [activeSection, setActiveSection] = useState('')
  const toc = useMemo(() => extractToc(guideContent), [])

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id)
          }
        }
      },
      { rootMargin: '-80px 0px -60% 0px' }
    )

    const timer = setTimeout(() => {
      toc.forEach(({ id }) => {
        const el = document.getElementById(id)
        if (el) observer.observe(el)
      })
    }, 100)

    return () => {
      clearTimeout(timer)
      observer.disconnect()
    }
  }, [toc])

  const scrollTo = (id: string) => {
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  return (
    <div className="flex gap-8">
      {/* Table of Contents Sidebar */}
      <nav
        className="hidden lg:block w-56 flex-shrink-0 sticky top-20 self-start max-h-[calc(100vh-6rem)] overflow-y-auto"
        aria-label="Table of contents"
      >
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Contents
        </h2>
        <ul className="space-y-1">
          {toc
            .filter((e) => e.level <= 2)
            .map((entry) => (
              <li key={entry.id}>
                <button
                  onClick={() => scrollTo(entry.id)}
                  className={`block w-full text-left text-sm px-2 py-1 rounded transition-colors ${
                    entry.level === 2 ? 'pl-4' : ''
                  } ${
                    activeSection === entry.id
                      ? 'text-blue-400 bg-gray-800'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                  }`}
                >
                  {entry.text}
                </button>
              </li>
            ))}
        </ul>
      </nav>

      {/* Main Content */}
      <article className="flex-1 min-w-0">
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-8">
          <div
            className="prose prose-invert prose-gray max-w-none
            prose-headings:scroll-mt-20
            prose-h1:text-2xl prose-h1:font-bold prose-h1:text-white prose-h1:border-b prose-h1:border-gray-700 prose-h1:pb-3 prose-h1:mb-6
            prose-h2:text-xl prose-h2:font-semibold prose-h2:text-white prose-h2:mt-10 prose-h2:mb-4
            prose-h3:text-lg prose-h3:font-medium prose-h3:text-gray-200
            prose-p:text-gray-300 prose-p:leading-relaxed
            prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline
            prose-strong:text-white
            prose-code:text-blue-300 prose-code:bg-gray-900 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-sm
            prose-table:border-collapse
            prose-th:bg-gray-900 prose-th:text-gray-200 prose-th:text-left prose-th:px-3 prose-th:py-2 prose-th:border prose-th:border-gray-700 prose-th:text-sm
            prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-gray-700 prose-td:text-sm prose-td:text-gray-300
            prose-li:text-gray-300
            prose-hr:border-gray-700
          "
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children, ...props }) => {
                  const text = String(children)
                  const id = text
                    .toLowerCase()
                    .replace(/[^\w\s-]/g, '')
                    .replace(/\s+/g, '-')
                  return (
                    <h1 id={id} {...props}>
                      {children}
                    </h1>
                  )
                },
                h2: ({ children, ...props }) => {
                  const text = String(children)
                  const id = text
                    .toLowerCase()
                    .replace(/[^\w\s-]/g, '')
                    .replace(/\s+/g, '-')
                  return (
                    <h2 id={id} {...props}>
                      {children}
                    </h2>
                  )
                },
                h3: ({ children, ...props }) => {
                  const text = String(children)
                  const id = text
                    .toLowerCase()
                    .replace(/[^\w\s-]/g, '')
                    .replace(/\s+/g, '-')
                  return (
                    <h3 id={id} {...props}>
                      {children}
                    </h3>
                  )
                },
              }}
            >
              {guideContent}
            </ReactMarkdown>
          </div>
        </div>
      </article>
    </div>
  )
}
