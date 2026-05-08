# FORGE — AI App Builder

## Original Problem Statement
Build a SaaS platform where users can describe a web app via a chat interface. Use Claude 3.5 Sonnet to generate React code, save in a database linked to the user's project, and render via react-live preview. User asked for a platform similar to Emergent.sh, with pre-made templates for marketing campaign dashboards and smart contract generators for non-developers.

## Architecture
- **Backend**: FastAPI + MongoDB + emergentintegrations (Claude Sonnet 4.5 — `claude-sonnet-4-5-20250929`)
- **Frontend**: React 19 + TailwindCSS + shadcn/ui + react-live + @phosphor-icons/react
- **Auth**: Single-user mode using `X-User-Id` header sourced from localStorage (no login)
- **Design**: Swiss/Brutalist dark theme — Chivo / IBM Plex Sans / JetBrains Mono fonts; sharp corners; red/yellow accents

## User Personas
- **Non-technical creators** wanting to bootstrap UIs without coding
- **Marketing/Web3 teams** needing quick prototypes (campaign dashboards, smart-contract UIs)
- **Developers** using it for quick scaffolding & ideation

## Implemented (2026-02-08)
- Landing page: hero, engine stats, 4-template gallery, projects list
- Project CRUD (`/api/projects` + GET/POST/DELETE/code update)
- Chat-based AI generation via Claude Sonnet 4.5 (`/api/projects/{id}/generate`)
- 4 pre-made templates (Marketing Dashboard, Smart Contract Generator, Data Viz, SaaS Landing)
- Live preview & editable code panel via react-live (`noInline` mode)
- Tab switching preview/code, copy-to-clipboard, debounced code persistence
- Workspace: split-pane layout with chat (left) + preview (right)
- 100% backend test coverage (16/16 pytest)

## Backlog
### P0
- Add user auth (Emergent Google login or JWT) for true multi-user SaaS
- Streaming responses from Claude (currently one-shot)

### P1
- Multi-file/multi-component generation (currently single component due to react-live constraints)
- Project sharing via public URL
- Export project as `.zip` with full Vite/CRA scaffold
- Version history per project (rollback to previous generation)

### P2
- Custom template creation by users
- Team workspaces & roles
- Stripe billing for credit-based generation
- Real-time collaborative editing

## Test Credentials
N/A — single-user via localStorage. Auto-generated user_id per browser.

## Key Files
- `/app/backend/server.py` — All API endpoints + LLM integration
- `/app/frontend/src/lib/api.js` — Axios client with X-User-Id header
- `/app/frontend/src/pages/LandingPage.jsx` — Templates + projects gallery
- `/app/frontend/src/pages/Workspace.jsx` — IDE with chat + preview
- `/app/frontend/src/components/ChatPanel.jsx` — Chat UI
- `/app/frontend/src/components/PreviewPanel.jsx` — react-live preview/code
- `/app/backend/tests/test_api.py` — Backend pytest suite
