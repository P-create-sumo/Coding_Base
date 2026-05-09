# FORGE — AI Platform v2.0

## Original Problem Statement
Build a SaaS platform where users describe a web app via chat, generate React code with Claude, save in DB, preview via react-live. Evolved through 3 iterations to a 3-feature AI workshop:
1. App Creator (v1.0–1.1)
2. Agents (v2.0)
3. Knowledge / RAG (v2.0)

## Architecture
- **Backend**: FastAPI + MongoDB. Modular: `core.py`, `apps_router.py`, `knowledge_router.py`, `agents_router.py`. LLM via litellm + Emergent proxy (Claude Sonnet 4.5).
- **Frontend**: React 19 + TailwindCSS + react-live + @phosphor-icons/react. Routes: `/` (Hub), `/apps`, `/apps/:id`, `/agents`, `/agents/:id`, `/knowledge`, `/knowledge/:id`, `/login`, `/auth/callback`.
- **Auth**: Emergent Google Login (httpOnly cookie + Bearer fallback).
- **Design**: Swiss/Brutalist dark theme with feature-specific accents (red for App Creator, yellow for Agents, green for Knowledge).

## Implemented (2026-02-08 / 2026-05-09)

### v1.0
- Landing page, project CRUD, single-prompt generation, 4 templates, react-live preview, code editor.

### v1.1
- Emergent Google auth with localStorage migration.
- SSE streaming generation (litellm direct).
- Multi-file output (`===FILE: path===…===END===`), Vite-ready .zip export.
- Version history (last 20 retained), rollback.

### v2.0 (this iteration)
- **Hub home** at `/` with 3 large cards (App Creator / Agents / Knowledge) showing live counts.
- **Modular backend**: split into `core.py` + 3 routers, all under `/api/{apps,knowledge,agents}/*`.
- **Knowledge / RAG**:
  - KB CRUD, document ingestion (PDF / DOCX / TXT / MD upload, URL scraping via httpx + BeautifulSoup).
  - Chunking (~800 chars w/ 100 overlap, sentence-aware).
  - **BM25 search** (pure-Python, no external embedding dependency — Emergent proxy doesn't expose embedding models).
  - Search UI with score display.
- **Agents** (3 types):
  - **Conversational**: persistent chat, optional KB attachment for grounded answers.
  - **Autonomous**: multi-step research with tools `web_search` (DuckDuckGo HTML), `read_url`, `calculator`, `knowledge_query`. SSE streams thoughts → tool calls → tool results → final answer.
  - **Coding**: linked to a forge project; iterates the App.jsx based on prompts.
- **App Creator KB attachment**: optional `knowledge_base_id` injects top chunks into system prompt for grounded codegen.
- 33/33 backend pytest pass, all frontend flows verified.

## Backlog
### P1
- Sandbox / timeout for `tool_calculator` (currently raw eval with regex whitelist; vulnerable to large exponents).
- Validate `linked_project_id` on coding agent creation (currently fails on first chat).
- Improved web_search (Tavily / Bing key) for more reliable agent tool use.
- Streaming responses for conversational agent.

### P2
- Hybrid BM25 + LLM rerank for higher RAG quality.
- Multi-modal documents (image OCR).
- Public agent marketplace.
- Stripe credit billing.
- Real-time collaboration.

## Test Credentials
Production uses real Google OAuth. For testing, seed users + user_sessions in MongoDB per `/app/auth_testing.md`.

## Key Files
- `/app/backend/server.py` — FastAPI app + auth + router mounts
- `/app/backend/core.py` — db, auth, litellm helpers, BM25 utilities
- `/app/backend/apps_router.py` — App Creator (templates, projects, generation, versions, export)
- `/app/backend/knowledge_router.py` — KB CRUD, file/URL ingest, BM25 search
- `/app/backend/agents_router.py` — agents CRUD, tool registry, autonomous SSE loop
- `/app/frontend/src/App.js` — routing
- `/app/frontend/src/pages/HubHome.jsx` — 3-card hub
- `/app/frontend/src/pages/AppsHub.jsx`, `Workspace.jsx` — App Creator
- `/app/frontend/src/pages/AgentsHub.jsx`, `AgentChat.jsx` — Agents
- `/app/frontend/src/pages/KnowledgeHub.jsx`, `KnowledgeBaseDetail.jsx` — Knowledge / RAG
- `/app/frontend/src/components/HubHeader.jsx` — shared sub-page header
- `/app/backend/tests/test_api.py` — 33-test pytest suite
