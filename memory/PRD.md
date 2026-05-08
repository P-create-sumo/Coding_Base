# FORGE — AI App Builder

## Original Problem Statement
Build a SaaS platform where users can describe a web app via a chat interface. Use Claude 3.5 Sonnet to generate React code, save in a database linked to the user's project, render via react-live preview. User asked for a platform similar to Emergent.sh, with pre-made templates for marketing campaign dashboards and smart contract generators for non-developers.

## Architecture
- **Backend**: FastAPI + MongoDB + litellm (direct call to Emergent proxy for streaming) + emergentintegrations (utils only)
- **Frontend**: React 19 + TailwindCSS + react-live + @phosphor-icons/react
- **Auth**: Emergent Google Auth (httpOnly cookie + 7-day session_token)
- **Design**: Swiss/Brutalist dark theme — Chivo / IBM Plex Sans / JetBrains Mono fonts; sharp corners; red/yellow accents

## User Personas
- **Non-technical creators** wanting to bootstrap UIs without coding
- **Marketing/Web3 teams** needing quick prototypes
- **Developers** for ideation & scaffolding

## Implemented (2026-02-08)

### v1.0
- Landing page: hero, engine stats, 4-template gallery, projects list
- Project CRUD
- Single-prompt AI generation via Claude Sonnet 4.5
- 4 templates (Marketing Dashboard, Smart Contract Generator, Data Viz, SaaS Landing)
- react-live preview + editable code panel
- Tab switching, copy-to-clipboard, debounced code persistence

### v1.1 (this iteration)
- **Auth**: Emergent Google Login, /login + /auth/callback, ProtectedRoute, user menu with logout
- **Streaming**: Real-time SSE generation via `/api/projects/{id}/generate-stream`. Progressive chunks rendered in chat with blinking cursor
- **Multi-file generation**: Claude outputs `===FILE: path===...===END===` format. Files stored as list, file tabs in code panel. App.jsx is preview entry (must be self-contained)
- **Version history**: Snapshot per generation, last-20 retained per project. Modal UI with rollback button
- **Export `.zip`**: Vite-ready scaffold (package.json, index.html, vite.config.js, src/main.jsx, README.md, src/App.jsx adapted for standalone use)
- **Migration**: localStorage `user_id` projects auto-migrate to authenticated user on first login
- 24/24 backend pytest pass, all frontend flows verified

## Backlog
### P1
- Toast position fix (moved to bottom-right ✓)
- Robust clipboard fallback (already implemented in v1.0 fix)
- True multi-component preview via iframe-based bundler (currently single self-contained App.jsx)
- Project sharing via public URL

### P2
- Custom user templates
- Team workspaces
- Stripe credit-based billing
- Real-time collaborative editing
- GitHub direct push integration

## Test Credentials
Production uses real Google OAuth (no static credentials). For testing: seed users + user_sessions in MongoDB per `/app/auth_testing.md`.

## Key Files
- `/app/backend/server.py` — All endpoints, auth, streaming, multi-file, versioning, export
- `/app/backend/.env` — `EMERGENT_LLM_KEY`
- `/app/frontend/src/App.js` — Router with `ProtectedRoute` + `AppRouter` (synchronous OAuth hash check)
- `/app/frontend/src/lib/auth.jsx` — `AuthProvider`, `useAuth`
- `/app/frontend/src/pages/LoginPage.jsx`
- `/app/frontend/src/pages/AuthCallback.jsx`
- `/app/frontend/src/pages/Workspace.jsx` — SSE streaming, file tabs, history, export
- `/app/frontend/src/components/VersionHistory.jsx`
- `/app/auth_testing.md` — Auth testing playbook
