from fastapi import FastAPI, APIRouter, HTTPException, Header, Request, Response, Depends
from fastapi.responses import StreamingResponse, Response as FastResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import json
import logging
import re
import zipfile
import httpx
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta

import litellm
from emergentintegrations.llm.utils import get_integration_proxy_url


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
LLM_MODEL_PROVIDER = "anthropic"
LLM_MODEL_NAME = "claude-sonnet-4-5-20250929"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
api_router = APIRouter(prefix="/api")


# ==================== MODELS ====================

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FileEntry(BaseModel):
    path: str
    content: str


class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    description: str = ""
    template_id: Optional[str] = None
    current_code: str = ""  # entry file (App.jsx) for preview
    files: List[FileEntry] = []  # all generated files
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    template_id: Optional[str] = None


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    role: str
    content: str
    code: Optional[str] = None
    files: List[FileEntry] = []
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GenerateRequest(BaseModel):
    prompt: str


class UpdateCodeRequest(BaseModel):
    code: str
    path: Optional[str] = None  # which file to update; default = App.jsx


class SessionRequest(BaseModel):
    session_id: str


class MigrateRequest(BaseModel):
    legacy_user_id: str


class Version(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    user_id: str
    prompt: str
    files: List[FileEntry] = []
    current_code: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== TEMPLATES ====================

TEMPLATES = [
    {
        "id": "marketing-dashboard",
        "name": "Marketing Campaign Dashboard",
        "category": "Dashboard",
        "description": "Analytics dashboard for marketing campaigns with KPIs, charts, and conversion metrics.",
        "thumbnail": "https://images.pexels.com/photos/27141307/pexels-photo-27141307.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "prompt": "Create a sleek, dark-themed marketing campaign dashboard. Include 4 KPI cards at top (Total Spend, Impressions, CTR, Conversions) with mock numbers and trend percentages. Below show a bar chart visualization area with 7 days of campaign performance using inline SVG bars in red and yellow colors. Add a campaigns table with 5 mock entries showing Campaign Name, Channel, Budget, Status, and ROI. Use Tailwind classes only, sharp corners (no rounded), black background (#050505), red accent (#FF3B30), yellow accent (#FFCC00).",
    },
    {
        "id": "smart-contract-generator",
        "name": "Smart Contract Generator",
        "category": "Web3",
        "description": "No-code interface for generating Solidity smart contracts (ERC-20, NFT, etc.).",
        "thumbnail": "https://images.pexels.com/photos/27141317/pexels-photo-27141317.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "prompt": "Create a smart contract generator UI for non-developers. Left side: a form with contract type dropdown (ERC-20 Token, ERC-721 NFT, Multisig Wallet), token name input, symbol input, total supply input, decimals input, and a 'Generate Contract' button. Right side: a code preview area showing mock Solidity code in a monospace font with green text on black background. Add a 'Deploy' button at the bottom. Use Tailwind, dark theme black background, sharp corners, red accent for the generate button. Make it functional with React useState so the form updates the preview Solidity code dynamically.",
    },
    {
        "id": "data-viz-dashboard",
        "name": "Data Visualization Dashboard",
        "category": "Analytics",
        "description": "Real-time data visualization with charts, metrics, and insights.",
        "thumbnail": "https://images.unsplash.com/photo-1526628953301-3e589a6a8b74?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA4Mzl8MHwxfHNlYXJjaHw0fHxhYnN0cmFjdCUyMGRhc2hib2FyZCUyMGdyYXBoaWN8ZW58MHx8fHwxNzc4MjcyMjcwfDA&ixlib=rb-4.1.0&q=85",
        "prompt": "Create a beautiful data visualization dashboard with a header showing 'Analytics Overview', 4 metric cards with trends (Revenue, Users, Sessions, Bounce Rate) with mock numbers and up/down arrows, a large chart visualization area built with inline SVG showing a line chart with 12 data points, and a side panel listing top 5 sources with progress bars. Use dark theme: black background #050505, red accent #FF3B30, yellow accent #FFCC00, white text. Use sharp corners (no rounded), Tailwind classes only.",
    },
    {
        "id": "landing-page",
        "name": "SaaS Landing Page",
        "category": "Marketing",
        "description": "Modern landing page with hero, features, and pricing sections.",
        "thumbnail": "https://images.pexels.com/photos/27141307/pexels-photo-27141307.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "prompt": "Create a modern SaaS landing page with: a hero section with bold headline 'Build Faster' and subheadline, a CTA button, a features grid (3 columns) with icons (use unicode symbols), a pricing section with 3 tiers (Starter, Pro, Enterprise) with feature lists. Dark theme black background, red and yellow accents, sharp corners, Tailwind only.",
    },
]


# ==================== SYSTEM PROMPT ====================

SYSTEM_PROMPT = """You are an expert React developer that generates COMPLETE, PRODUCTION-READY React projects.

You output a project structure with multiple files. The PRIMARY file `App.jsx` MUST be self-contained for live preview (no imports from sibling files), but you may create additional files for export (README.md, package.json, components.md, etc.).

== OUTPUT FORMAT ==
Optionally provide a brief 1-2 sentence explanation BEFORE the files.

Then output each file using this exact marker format:

===FILE: App.jsx===
<file content>
===END===

===FILE: README.md===
<file content>
===END===

== App.jsx STRICT RULES (PREVIEW FILE) ==
1. Single self-contained React functional component called `App` plus any helper components defined inline in the SAME file.
2. NO imports, NO exports, NO require() — `React` is available globally. Use `React.useState`, `React.useEffect`, etc.
3. End with: `render(<App />);`
4. Use ONLY inline Tailwind CSS classes. No external CSS, no styled-components, no UI libraries.
5. NO external libraries (no lucide-react, no framer-motion, no axios, no recharts).
6. For icons use unicode symbols (▲▼●■★✓✗→←↑↓⚡✨) or simple inline SVG.
7. Default styling: dark theme black/charcoal (#050505, #121212), white text, accents red (#FF3B30) and yellow (#FFCC00). Sharp corners (avoid `rounded-*` unless explicitly asked).
8. Make components visually impressive, interactive, responsive, with semantic HTML.
9. Always wrap in `<div className="min-h-screen bg-[#050505] ...">` so the preview fills space.

== ADDITIONAL FILES (OPTIONAL, FOR EXPORT) ==
You MAY include:
- README.md  (project overview, how to run)
- package.json (with react, react-dom, vite, tailwindcss as deps — but DO NOT include this if the user request is trivial)
- index.html (Vite-style entry)
- src/main.jsx (Vite entry)

Keep these short and only when the user request is significant (a real app vs a single button).

== EXAMPLE ==

Here is a counter dashboard.

===FILE: App.jsx===
const App = () => {
  const [count, setCount] = React.useState(0);
  return (
    <div className="min-h-screen bg-[#050505] text-white p-8 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-6xl font-black tracking-tighter">{count}</h1>
        <button
          onClick={() => setCount(count + 1)}
          className="mt-6 bg-[#FF3B30] text-white px-6 py-3 font-bold uppercase tracking-wide hover:bg-white hover:text-black"
        >
          increment ▲
        </button>
      </div>
    </div>
  );
};
render(<App />);
===END===

===FILE: README.md===
# Counter
Run with `npm install && npm run dev`.
===END===
"""


# ==================== HELPERS ====================

def parse_files_from_response(content: str) -> List[FileEntry]:
    """Parse multi-file format from LLM response."""
    files = []
    pattern = r"===FILE:\s*(.+?)\s*===\s*\n(.*?)\n===END==="
    matches = re.findall(pattern, content, re.DOTALL)
    for path, body in matches:
        files.append(FileEntry(path=path.strip(), content=body.strip()))

    # Fallback: legacy ```jsx code block (single file → App.jsx)
    if not files:
        cb = re.search(r"```(?:jsx|javascript|js|tsx)?\s*\n([\s\S]*?)\n```", content)
        if cb:
            files.append(FileEntry(path="App.jsx", content=cb.group(1).strip()))
    return files


def get_entry_code(files: List[FileEntry]) -> str:
    """Find App.jsx (or first .jsx file) for preview."""
    for f in files:
        if f.path.lower().endswith("app.jsx") or f.path.lower() == "app.jsx":
            return f.content
    for f in files:
        if f.path.lower().endswith(".jsx") or f.path.lower().endswith(".js"):
            return f.content
    return files[0].content if files else ""


def build_litellm_params(messages: List[Dict[str, Any]], stream: bool = False) -> Dict[str, Any]:
    """Build params for direct litellm call (for streaming)."""
    proxy_url = get_integration_proxy_url()
    return {
        "model": LLM_MODEL_NAME,
        "messages": messages,
        "api_key": EMERGENT_LLM_KEY,
        "api_base": proxy_url + "/llm",
        "custom_llm_provider": "openai",
        "stream": stream,
    }


def build_chat_messages(history: List[Message], new_prompt: str) -> List[Dict[str, Any]]:
    """Build OpenAI-format messages array."""
    msgs: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history:
        if m.role == "user":
            msgs.append({"role": "user", "content": m.content})
        else:
            msgs.append({"role": "assistant", "content": m.content})
    msgs.append({"role": "user", "content": new_prompt})
    return msgs


# ==================== AUTH ====================

async def get_current_user(request: Request) -> User:
    """Get authenticated user from session_token cookie or Bearer header."""
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_doc = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user_doc = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    return User(**user_doc)


@api_router.post("/auth/session")
async def auth_session(req: SessionRequest, response: Response):
    """Process session_id from Emergent OAuth callback."""
    async with httpx.AsyncClient() as http_client:
        try:
            r = await http_client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": req.session_id},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.exception("Auth session-data failed")
            raise HTTPException(status_code=401, detail=f"OAuth verification failed: {str(e)}")

    email = data["email"]
    # Upsert user
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user = User(**existing)
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$set": {"name": data.get("name", user.name), "picture": data.get("picture", user.picture)}},
        )
    else:
        user = User(
            user_id=f"user_{uuid.uuid4().hex[:12]}",
            email=email,
            name=data.get("name", email.split("@")[0]),
            picture=data.get("picture"),
        )
        await db.users.insert_one(user.model_dump())

    # Save session
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user.user_id,
        "session_token": data["session_token"],
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Set httpOnly cookie
    response.set_cookie(
        key="session_token",
        value=data["session_token"],
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )

    return {"user": user.model_dump(), "session_token": data["session_token"]}


@api_router.get("/auth/me")
async def auth_me(user: User = Depends(get_current_user)):
    return user.model_dump()


@api_router.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/", samesite="none", secure=True)
    return {"success": True}


@api_router.post("/auth/migrate")
async def auth_migrate(req: MigrateRequest, user: User = Depends(get_current_user)):
    """Migrate projects from legacy localStorage user_id to authenticated user."""
    if not req.legacy_user_id or req.legacy_user_id == user.user_id:
        return {"migrated": 0}
    result = await db.projects.update_many(
        {"user_id": req.legacy_user_id},
        {"$set": {"user_id": user.user_id}},
    )
    return {"migrated": result.modified_count}


# ==================== ROOT & TEMPLATES ====================

@api_router.get("/")
async def root():
    return {"message": "FORGE AI App Builder API", "model": LLM_MODEL_NAME}


@api_router.get("/templates")
async def get_templates():
    return TEMPLATES


# ==================== PROJECTS ====================

@api_router.get("/projects", response_model=List[Project])
async def list_projects(user: User = Depends(get_current_user)):
    docs = await db.projects.find({"user_id": user.user_id}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    return [Project(**doc) for doc in docs]


@api_router.post("/projects", response_model=Project)
async def create_project(req: CreateProjectRequest, user: User = Depends(get_current_user)):
    project = Project(
        user_id=user.user_id,
        name=req.name,
        description=req.description,
        template_id=req.template_id,
    )
    await db.projects.insert_one(project.model_dump())
    return project


@api_router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str, user: User = Depends(get_current_user)):
    doc = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    return Project(**doc)


@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: User = Depends(get_current_user)):
    result = await db.projects.delete_one({"id": project_id, "user_id": user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.messages.delete_many({"project_id": project_id})
    await db.versions.delete_many({"project_id": project_id})
    return {"success": True}


@api_router.get("/projects/{project_id}/messages", response_model=List[Message])
async def list_messages(project_id: str, user: User = Depends(get_current_user)):
    project = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    docs = await db.messages.find({"project_id": project_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return [Message(**doc) for doc in docs]


# ==================== GENERATION ====================

async def _do_generate(project_id: str, user_id: str, prompt: str) -> Dict[str, Any]:
    """Shared logic for sync + streaming generation."""
    project_doc = await db.projects.find_one({"id": project_id, "user_id": user_id}, {"_id": 0})
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")

    user_msg = Message(project_id=project_id, role="user", content=prompt)
    await db.messages.insert_one(user_msg.model_dump())

    history_docs = await db.messages.find({"project_id": project_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    history = [Message(**d) for d in history_docs[:-1]]
    return {"user_msg": user_msg, "history": history, "project": project_doc}


async def _save_assistant_response(
    project_id: str, user_id: str, response_text: str, prompt: str
) -> Dict[str, Any]:
    files = parse_files_from_response(response_text)
    entry_code = get_entry_code(files) if files else ""

    assistant_msg = Message(
        project_id=project_id,
        role="assistant",
        content=response_text,
        code=entry_code or None,
        files=files,
    )
    await db.messages.insert_one(assistant_msg.model_dump())

    update_fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if entry_code:
        update_fields["current_code"] = entry_code
    if files:
        update_fields["files"] = [f.model_dump() for f in files]

    await db.projects.update_one({"id": project_id}, {"$set": update_fields})

    # Save version snapshot
    if files:
        version = Version(
            project_id=project_id,
            user_id=user_id,
            prompt=prompt,
            files=files,
            current_code=entry_code,
        )
        await db.versions.insert_one(version.model_dump())
        # Keep only last 20 versions
        all_versions = await db.versions.find(
            {"project_id": project_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        if len(all_versions) > 20:
            old_ids = [v["id"] for v in all_versions[20:]]
            await db.versions.delete_many({"id": {"$in": old_ids}})

    return {
        "assistant_message": assistant_msg.model_dump(),
        "code": entry_code,
        "files": [f.model_dump() for f in files],
    }


@api_router.post("/projects/{project_id}/generate")
async def generate_code(project_id: str, req: GenerateRequest, user: User = Depends(get_current_user)):
    setup = await _do_generate(project_id, user.user_id, req.prompt)
    messages = build_chat_messages(setup["history"], req.prompt)

    try:
        params = build_litellm_params(messages, stream=False)
        response = litellm.completion(**params)
        response_text = response.choices[0].message.content or ""
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

    saved = await _save_assistant_response(project_id, user.user_id, response_text, req.prompt)
    return {
        "user_message": setup["user_msg"].model_dump(),
        **saved,
    }


@api_router.post("/projects/{project_id}/generate-stream")
async def generate_code_stream(project_id: str, req: GenerateRequest, user: User = Depends(get_current_user)):
    """SSE streaming endpoint."""
    setup = await _do_generate(project_id, user.user_id, req.prompt)
    user_msg = setup["user_msg"]
    messages = build_chat_messages(setup["history"], req.prompt)

    async def event_stream():
        # Send initial event with user message
        yield f"data: {json.dumps({'type': 'user', 'message': user_msg.model_dump()})}\n\n"
        full_text = ""
        try:
            params = build_litellm_params(messages, stream=True)
            response = litellm.completion(**params)
            for chunk in response:
                try:
                    delta = chunk.choices[0].delta.content if chunk.choices and chunk.choices[0].delta else None
                    if delta:
                        full_text += delta
                        yield f"data: {json.dumps({'type': 'chunk', 'text': delta})}\n\n"
                        await asyncio.sleep(0)  # let other tasks run
                except Exception:
                    continue

            saved = await _save_assistant_response(project_id, user.user_id, full_text, req.prompt)
            yield f"data: {json.dumps({'type': 'done', **saved})}\n\n"
        except Exception as e:
            logger.exception("Stream error")
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api_router.put("/projects/{project_id}/code")
async def update_code(project_id: str, req: UpdateCodeRequest, user: User = Depends(get_current_user)):
    proj = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    target_path = req.path or "App.jsx"
    files = proj.get("files", []) or []
    updated = False
    for f in files:
        if f["path"] == target_path:
            f["content"] = req.code
            updated = True
            break
    if not updated:
        files.append({"path": target_path, "content": req.code})

    update_doc: Dict[str, Any] = {
        "files": files,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if target_path == "App.jsx":
        update_doc["current_code"] = req.code

    await db.projects.update_one({"id": project_id}, {"$set": update_doc})
    return {"success": True}


# ==================== VERSIONS ====================

@api_router.get("/projects/{project_id}/versions", response_model=List[Version])
async def list_versions(project_id: str, user: User = Depends(get_current_user)):
    proj = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    docs = await db.versions.find({"project_id": project_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return [Version(**d) for d in docs]


@api_router.post("/projects/{project_id}/rollback/{version_id}")
async def rollback_version(project_id: str, version_id: str, user: User = Depends(get_current_user)):
    proj = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    ver = await db.versions.find_one({"id": version_id, "project_id": project_id}, {"_id": 0})
    if not ver:
        raise HTTPException(status_code=404, detail="Version not found")

    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "current_code": ver["current_code"],
            "files": ver["files"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"success": True, "current_code": ver["current_code"], "files": ver["files"]}


# ==================== EXPORT ====================

DEFAULT_PACKAGE_JSON = '''{
  "name": "__NAME__",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
'''

DEFAULT_INDEX_HTML = '''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>__NAME__</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
'''

DEFAULT_MAIN_JSX = """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
"""

DEFAULT_VITE_CONFIG = """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
});
"""

DEFAULT_README = """# __NAME__

Generated with [FORGE](https://forge.app) — AI App Builder.

## Run

```bash
npm install
npm run dev
```

Open http://localhost:5173
"""


def adapt_app_for_export(code: str) -> str:
    """Convert react-live App.jsx (no imports, render() call) to standalone Vite-compatible App.jsx."""
    code = re.sub(r"^\s*render\(\s*<App\s*/>\s*\)\s*;?\s*$", "", code, flags=re.MULTILINE).strip()
    if "import React" not in code:
        code = "import React from 'react';\n\n" + code
    if "export default" not in code:
        code += "\n\nexport default App;\n"
    return code


@api_router.get("/projects/{project_id}/export")
async def export_project(project_id: str, user: User = Depends(get_current_user)):
    proj_doc = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not proj_doc:
        raise HTTPException(status_code=404, detail="Project not found")
    project = Project(**proj_doc)

    safe_name = re.sub(r"[^a-z0-9-]", "-", project.name.lower())[:40] or "forge-project"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Standard scaffold
        zf.writestr(f"{safe_name}/package.json", DEFAULT_PACKAGE_JSON.replace("__NAME__", safe_name))
        zf.writestr(f"{safe_name}/index.html", DEFAULT_INDEX_HTML.replace("__NAME__", project.name))
        zf.writestr(f"{safe_name}/vite.config.js", DEFAULT_VITE_CONFIG)
        zf.writestr(f"{safe_name}/src/main.jsx", DEFAULT_MAIN_JSX)
        zf.writestr(f"{safe_name}/README.md", DEFAULT_README.replace("__NAME__", project.name))

        # Project files
        files_to_write = list(project.files) if project.files else []
        if not files_to_write and project.current_code:
            files_to_write = [FileEntry(path="App.jsx", content=project.current_code)]

        for f in files_to_write:
            target = f.content
            if f.path.lower().endswith("app.jsx"):
                target = adapt_app_for_export(target)
                zf.writestr(f"{safe_name}/src/App.jsx", target)
            elif f.path in ("package.json", "index.html", "vite.config.js", "README.md"):
                # Skip overriding scaffold defaults
                continue
            else:
                # Place under src/ for code files, root for others
                if f.path.lower().endswith((".jsx", ".js", ".ts", ".tsx", ".css")):
                    zf.writestr(f"{safe_name}/src/{f.path}", target)
                else:
                    zf.writestr(f"{safe_name}/{f.path}", target)

    buf.seek(0)
    return FastResponse(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
    )


# ==================== APP SETUP ====================

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
