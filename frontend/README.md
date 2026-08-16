# Cardigan Dashboard Template

A full-stack dashboard starter with a dark-first UI, real-time updates via WebSocket, and single-file branding. Built with React, TypeScript, Tailwind CSS, and FastAPI.

## Origin

This template was extracted from [ai-editorial-assistant-v3](https://github.com/mriechers/ai-editorial-assistant-v3), the PBS Wisconsin Digital Editorial Assistant featuring "Cardigan" — a Mister Rogers-inspired copy editor. The dashboard shell, accessibility features, and real-time architecture were generalized into this standalone starter so other projects can build on the same foundation.

## Features

- **Dark-first design** — `gray-950` base with accessible contrast ratios and optional high-contrast mode
- **Real-time updates** — WebSocket connection with heartbeat, auto-reconnect, and graceful degradation to polling
- **Keyboard navigation** — Vim-style `g + h/i/s/y` page jumps, `/` to focus search, `?` for shortcut reference
- **Accessibility** — Skip-to-content link, focus trapping in modals, ARIA attributes, `prefers-reduced-motion` and `prefers-contrast` detection
- **White-label ready** — Edit one `branding.json` to change app name, version, logo, colors, and storage key
- **Full CRUD API** — Paginated items with search, status filtering, and WebSocket broadcast on mutations
- **User preferences** — Text size, motion reduction, and high contrast with live preview and `localStorage` persistence

## Tech Stack

| Layer    | Technology                           |
| -------- | ------------------------------------ |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS 3 |
| Backend  | FastAPI, Pydantic v2, Uvicorn        |
| Realtime | WebSocket (native + FastAPI)         |
| Routing  | React Router v6                      |

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.10+

### 1. Clone and install

```bash
git clone https://github.com/mriechers/cardigan-dashboard-template.git
cd cardigan-dashboard-template

# Frontend
cd web && npm install && cd ..

# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start both servers

Open two terminals:

```bash
# Terminal 1 — API (port 8000)
uvicorn api.main:app --reload

# Terminal 2 — Frontend (port 3000)
cd web && npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The Vite dev server proxies `/api` requests to the backend automatically.

## Project Structure

```
├── branding.json              # App name, colors, logo — edit this to white-label
├── api/
│   ├── main.py                # FastAPI app with CORS and lifespan
│   ├── models/item.py         # Pydantic models (Item, ItemCreate, ItemUpdate, etc.)
│   ├── routers/
│   │   ├── health.py          # GET /api/health
│   │   ├── items.py           # CRUD endpoints for /api/items
│   │   └── websocket.py       # WS /api/ws/updates + broadcast helper
│   └── services/mock_data.py  # In-memory store seeded with 15 sample items
├── web/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Layout.tsx     # Shell: header, nav, status bar, shortcut modal
│   │   │   ├── StatusBar.tsx  # Bottom bar: health indicator, item counts
│   │   │   └── ui/            # Reusable components (StatCard, Toast, Toggle, etc.)
│   │   ├── config/branding.ts # Typed import of branding.json + CSS variable injection
│   │   ├── context/           # PreferencesContext (text size, motion, contrast)
│   │   ├── hooks/             # useWebSocket, useKeyboardShortcuts, useApiHealth, etc.
│   │   ├── pages/             # Home, Items, ItemDetail, Settings, System, Help
│   │   └── utils/             # formatTime, statusColors
│   ├── tailwind.config.js
│   └── vite.config.ts         # Dev server on :3000, proxy /api → :8000
└── requirements.txt
```

## Branding

Edit `branding.json` at the project root to customize the dashboard:

```json
{
  "appName": "Cardigan Dashboard",
  "appVersion": "1.0.0",
  "orgName": "Acme Corp",
  "logoUrl": "/favicon.svg",
  "colors": {
    "primary": "#3b82f6",
    "secondary": "#8b5cf6"
  },
  "storageKey": "cardigan-dashboard-preferences"
}
```

Brand colors are injected as CSS custom properties (`--color-brand-primary`, `--color-brand-secondary`) at startup, so Tailwind utilities and custom CSS can reference them.

## API Reference

| Method   | Endpoint              | Description                     |
| -------- | --------------------- | ------------------------------- |
| `GET`    | `/api/health`         | Health check with item stats    |
| `GET`    | `/api/items`          | List items (paginated, filterable) |
| `GET`    | `/api/items/stats`    | Aggregate status counts         |
| `GET`    | `/api/items/:id`      | Get single item                 |
| `POST`   | `/api/items`          | Create item                     |
| `PATCH`  | `/api/items/:id`      | Partial update                  |
| `DELETE` | `/api/items/:id`      | Delete item                     |
| `WS`     | `/api/ws/updates`     | Real-time item & stats events   |

**Query parameters** for `GET /api/items`:

| Param       | Type   | Default | Description           |
| ----------- | ------ | ------- | --------------------- |
| `page`      | int    | 1       | Page number           |
| `page_size` | int    | 20      | Items per page (1–100)|
| `status`    | string | —       | Filter: pending, active, completed, failed |
| `search`    | string | —       | Search title and description |

## Keyboard Shortcuts

| Shortcut | Action              |
| -------- | ------------------- |
| `g h`    | Go to Dashboard     |
| `g i`    | Go to Items         |
| `g s`    | Go to Settings      |
| `g y`    | Go to System        |
| `/`      | Focus search input  |
| `?`      | Show shortcut modal |

## Extending the Template

**Replace mock data with a real database:** Swap `api/services/mock_data.py` with a database-backed service (SQLAlchemy, Tortoise ORM, etc.) that implements the same `get_all`, `get_by_id`, `create`, `update`, `delete`, and `get_stats` interface.

**Add authentication:** The FastAPI CORS middleware is set to allow all origins for local development. For production, restrict `allow_origins` in `api/main.py` and add an auth middleware.

**Add new pages:** Create a component in `web/src/pages/`, add a `<Route>` in `App.tsx`, and a `<NavLink>` in `Layout.tsx`.

## License

[MIT](LICENSE)
