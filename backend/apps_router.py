"""App Creator router (existing functionality)."""
from fastapi import APIRouter, HTTPException, Depends, Response as FastResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import re
import io
import json
import zipfile
import asyncio
from datetime import datetime, timezone

from core import db, get_current_user, User, chat_completion, now_iso, new_id, logger


router = APIRouter(prefix="/apps", tags=["apps"])


# ======== Models ========

class FileEntry(BaseModel):
    path: str
    content: str


class Project(BaseModel):
    id: str = Field(default_factory=lambda: new_id())
    user_id: str
    name: str
    description: str = ""
    template_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    current_code: str = ""
    files: List[FileEntry] = []
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    template_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None


class Message(BaseModel):
    id: str = Field(default_factory=lambda: new_id())
    project_id: str
    role: str
    content: str
    code: Optional[str] = None
    files: List[FileEntry] = []
    created_at: str = Field(default_factory=now_iso)


class GenerateRequest(BaseModel):
    prompt: str


class UpdateCodeRequest(BaseModel):
    code: str
    path: Optional[str] = None


class Version(BaseModel):
    id: str = Field(default_factory=lambda: new_id())
    project_id: str
    user_id: str
    prompt: str
    files: List[FileEntry] = []
    current_code: str = ""
    created_at: str = Field(default_factory=now_iso)


# ======== Templates ========

TEMPLATES = [
    {
        "id": "marketing-dashboard",
        "name": "Marketing Campaign Dashboard",
        "category": "Dashboard",
        "description": "Analytics dashboard for marketing campaigns with KPIs, charts, and conversion metrics.",
        "thumbnail": "https://images.pexels.com/photos/27141307/pexels-photo-27141307.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "prompt": "Create a sleek, dark-themed marketing campaign dashboard. Include 4 KPI cards at top (Total Spend, Impressions, CTR, Conversions) with mock numbers and trend percentages. Below show a bar chart visualization area with 7 days of campaign performance using inline SVG bars in red and yellow colors. Add a campaigns table with 5 mock entries. Use Tailwind, dark theme black background (#050505), red accent (#FF3B30), yellow accent (#FFCC00), sharp corners.",
    },
    {
        "id": "smart-contract-generator",
        "name": "Smart Contract Generator",
        "category": "Web3",
        "description": "No-code interface for generating Solidity smart contracts (ERC-20, NFT, etc.).",
        "thumbnail": "https://images.pexels.com/photos/27141317/pexels-photo-27141317.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "prompt": "Create a smart contract generator UI for non-developers. Left side: a form with contract type dropdown (ERC-20 Token, ERC-721 NFT, Multisig Wallet), token name input, symbol input, total supply input, decimals input, and a 'Generate Contract' button. Right side: a code preview area showing mock Solidity code in a monospace font with green text on black background. Add a 'Deploy' button. Dark theme, sharp corners, Tailwind only. Make it functional with React useState so the form updates the preview Solidity code dynamically.",
    },
    {
        "id": "data-viz-dashboard",
        "name": "Data Visualization Dashboard",
        "category": "Analytics",
        "description": "Real-time data visualization with charts, metrics, and insights.",
        "thumbnail": "https://images.unsplash.com/photo-1526628953301-3e589a6a8b74?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA4Mzl8MHwxfHNlYXJjaHw0fHxhYnN0cmFjdCUyMGRhc2hib2FyZCUyMGdyYXBoaWN8ZW58MHx8fHwxNzc4MjcyMjcwfDA&ixlib=rb-4.1.0&q=85",
        "prompt": "Create a beautiful data visualization dashboard with header 'Analytics Overview', 4 metric cards with trends (Revenue, Users, Sessions, Bounce Rate) with mock numbers and up/down arrows, a large chart visualization area built with inline SVG showing a line chart with 12 data points, and a side panel listing top 5 sources with progress bars. Dark theme black bg, red and yellow accents, sharp corners, Tailwind only.",
    },
    {
        "id": "landing-page",
        "name": "SaaS Landing Page",
        "category": "Marketing",
        "description": "Modern landing page with hero, features, and pricing sections.",
        "thumbnail": "https://images.pexels.com/photos/27141307/pexels-photo-27141307.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "prompt": "Create a modern SaaS landing page with: hero with bold headline 'Build Faster' and subheadline, CTA button, features grid (3 columns) with icons (use unicode symbols), pricing section with 3 tiers (Starter, Pro, Enterprise) with feature lists. Dark theme, red and yellow accents, sharp corners, Tailwind only.",
    },
]


SYSTEM_PROMPT = """You are an expert React developer that generates COMPLETE, PRODUCTION-READY React projects.

You output a project structure with multiple files. The PRIMARY file `App.jsx` MUST be self-contained for live preview (no imports from sibling files), but you may create additional files for export.

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
7. Default styling: dark theme black/charcoal (#050505, #121212), white text, accents red (#FF3B30) and yellow (#FFCC00). Sharp corners.
8. Make components visually impressive, interactive, responsive.
9. Always wrap in `<div className="min-h-screen bg-[#050505] ...">` so the preview fills space.

== ADDITIONAL FILES (OPTIONAL) ==
You MAY include README.md, package.json (if non-trivial), index.html, src/main.jsx.
"""


# ======== Helpers ========

def parse_files_from_response(content: str) -> List[FileEntry]:
    files = []
    pattern = r"===FILE:\s*(.+?)\s*===\s*\n(.*?)\n===END==="
    matches = re.findall(pattern, content, re.DOTALL)
    for path, body in matches:
        files.append(FileEntry(path=path.strip(), content=body.strip()))
    if not files:
        cb = re.search(r"```(?:jsx|javascript|js|tsx)?\s*\n([\s\S]*?)\n```", content)
        if cb:
            files.append(FileEntry(path="App.jsx", content=cb.group(1).strip()))
    return files


def get_entry_code(files: List[FileEntry]) -> str:
    for f in files:
        if f.path.lower().endswith("app.jsx"):
            return f.content
    for f in files:
        if f.path.lower().endswith((".jsx", ".js")):
            return f.content
    return files[0].content if files else ""


def build_chat_messages(history: List[Message], new_prompt: str, knowledge_context: str = "") -> List[Dict[str, Any]]:
    system = SYSTEM_PROMPT
    if knowledge_context:
        system += f"\n\n== KNOWLEDGE BASE CONTEXT ==\nUse the following information when relevant:\n{knowledge_context}"
    msgs: List[Dict[str, Any]] = [{"role": "system", "content": system}]
    for m in history:
        msgs.append({"role": "user" if m.role == "user" else "assistant", "content": m.content})
    msgs.append({"role": "user", "content": new_prompt})
    return msgs


async def get_kb_context(kb_id: Optional[str], query: str, user_id: str) -> str:
    """Fetch top-3 chunks from a knowledge base."""
    if not kb_id:
        return ""
    try:
        from knowledge_router import search_chunks
        chunks = await search_chunks(kb_id, user_id, query, top_k=3)
        if not chunks:
            return ""
        return "\n\n".join([f"[{c['doc_name']}] {c['content']}" for c in chunks])
    except Exception:
        logger.exception("KB context fetch failed")
        return ""


# ======== Routes ========

@router.get("/templates")
async def get_templates():
    return TEMPLATES


@router.get("/projects", response_model=List[Project])
async def list_projects(user: User = Depends(get_current_user)):
    docs = await db.projects.find({"user_id": user.user_id}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    return [Project(**doc) for doc in docs]


@router.post("/projects", response_model=Project)
async def create_project(req: CreateProjectRequest, user: User = Depends(get_current_user)):
    project = Project(
        user_id=user.user_id,
        name=req.name,
        description=req.description,
        template_id=req.template_id,
        knowledge_base_id=req.knowledge_base_id,
    )
    await db.projects.insert_one(project.model_dump())
    return project


@router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str, user: User = Depends(get_current_user)):
    doc = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    return Project(**doc)


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: User = Depends(get_current_user)):
    result = await db.projects.delete_one({"id": project_id, "user_id": user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.messages.delete_many({"project_id": project_id})
    await db.versions.delete_many({"project_id": project_id})
    return {"success": True}


@router.get("/projects/{project_id}/messages", response_model=List[Message])
async def list_messages(project_id: str, user: User = Depends(get_current_user)):
    project = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    docs = await db.messages.find({"project_id": project_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return [Message(**doc) for doc in docs]


async def _save_assistant_response(project_id: str, user_id: str, response_text: str, prompt: str) -> Dict[str, Any]:
    files = parse_files_from_response(response_text)
    entry_code = get_entry_code(files) if files else ""

    assistant_msg = Message(
        project_id=project_id, role="assistant", content=response_text,
        code=entry_code or None, files=files,
    )
    await db.messages.insert_one(assistant_msg.model_dump())

    update_fields: Dict[str, Any] = {"updated_at": now_iso()}
    if entry_code:
        update_fields["current_code"] = entry_code
    if files:
        update_fields["files"] = [f.model_dump() for f in files]
    await db.projects.update_one({"id": project_id}, {"$set": update_fields})

    if files:
        version = Version(project_id=project_id, user_id=user_id, prompt=prompt, files=files, current_code=entry_code)
        await db.versions.insert_one(version.model_dump())
        all_versions = await db.versions.find({"project_id": project_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        if len(all_versions) > 20:
            old_ids = [v["id"] for v in all_versions[20:]]
            await db.versions.delete_many({"id": {"$in": old_ids}})

    return {"assistant_message": assistant_msg.model_dump(), "code": entry_code, "files": [f.model_dump() for f in files]}


@router.post("/projects/{project_id}/generate")
async def generate_code(project_id: str, req: GenerateRequest, user: User = Depends(get_current_user)):
    project_doc = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")

    user_msg = Message(project_id=project_id, role="user", content=req.prompt)
    await db.messages.insert_one(user_msg.model_dump())

    history_docs = await db.messages.find({"project_id": project_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    history = [Message(**d) for d in history_docs[:-1]]

    kb_ctx = await get_kb_context(project_doc.get("knowledge_base_id"), req.prompt, user.user_id)
    messages = build_chat_messages(history, req.prompt, kb_ctx)

    try:
        response = chat_completion(messages, stream=False)
        response_text = response.choices[0].message.content or ""
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

    saved = await _save_assistant_response(project_id, user.user_id, response_text, req.prompt)
    return {"user_message": user_msg.model_dump(), **saved}


@router.post("/projects/{project_id}/generate-stream")
async def generate_code_stream(project_id: str, req: GenerateRequest, user: User = Depends(get_current_user)):
    project_doc = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")

    user_msg = Message(project_id=project_id, role="user", content=req.prompt)
    await db.messages.insert_one(user_msg.model_dump())

    history_docs = await db.messages.find({"project_id": project_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    history = [Message(**d) for d in history_docs[:-1]]

    kb_ctx = await get_kb_context(project_doc.get("knowledge_base_id"), req.prompt, user.user_id)
    messages = build_chat_messages(history, req.prompt, kb_ctx)

    async def event_stream():
        yield f"data: {json.dumps({'type': 'user', 'message': user_msg.model_dump()})}\n\n"
        full_text = ""
        try:
            response = chat_completion(messages, stream=True)
            for chunk in response:
                try:
                    delta = chunk.choices[0].delta.content if chunk.choices and chunk.choices[0].delta else None
                    if delta:
                        full_text += delta
                        yield f"data: {json.dumps({'type': 'chunk', 'text': delta})}\n\n"
                        await asyncio.sleep(0)
                except Exception:
                    continue
            saved = await _save_assistant_response(project_id, user.user_id, full_text, req.prompt)
            yield f"data: {json.dumps({'type': 'done', **saved})}\n\n"
        except Exception as e:
            logger.exception("Stream error")
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.put("/projects/{project_id}/code")
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
    update_doc: Dict[str, Any] = {"files": files, "updated_at": now_iso()}
    if target_path == "App.jsx":
        update_doc["current_code"] = req.code
    await db.projects.update_one({"id": project_id}, {"$set": update_doc})
    return {"success": True}


@router.get("/projects/{project_id}/versions", response_model=List[Version])
async def list_versions(project_id: str, user: User = Depends(get_current_user)):
    proj = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    docs = await db.versions.find({"project_id": project_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return [Version(**d) for d in docs]


@router.post("/projects/{project_id}/rollback/{version_id}")
async def rollback_version(project_id: str, version_id: str, user: User = Depends(get_current_user)):
    proj = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    ver = await db.versions.find_one({"id": version_id, "project_id": project_id}, {"_id": 0})
    if not ver:
        raise HTTPException(status_code=404, detail="Version not found")
    await db.projects.update_one({"id": project_id}, {"$set": {
        "current_code": ver["current_code"], "files": ver["files"], "updated_at": now_iso(),
    }})
    return {"success": True, "current_code": ver["current_code"], "files": ver["files"]}


# ======== Export ========

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
    "vite": "^5.4.0"
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

Generated with FORGE — AI App Builder.

## Run

```bash
npm install
npm run dev
```
"""


def adapt_app_for_export(code: str) -> str:
    code = re.sub(r"^\s*render\(\s*<App\s*/>\s*\)\s*;?\s*$", "", code, flags=re.MULTILINE).strip()
    if "import React" not in code:
        code = "import React from 'react';\n\n" + code
    if "export default" not in code:
        code += "\n\nexport default App;\n"
    return code


@router.get("/projects/{project_id}/export")
async def export_project(project_id: str, user: User = Depends(get_current_user)):
    proj_doc = await db.projects.find_one({"id": project_id, "user_id": user.user_id}, {"_id": 0})
    if not proj_doc:
        raise HTTPException(status_code=404, detail="Project not found")
    project = Project(**proj_doc)

    safe_name = re.sub(r"[^a-z0-9-]", "-", project.name.lower())[:40] or "forge-project"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{safe_name}/package.json", DEFAULT_PACKAGE_JSON.replace("__NAME__", safe_name))
        zf.writestr(f"{safe_name}/index.html", DEFAULT_INDEX_HTML.replace("__NAME__", project.name))
        zf.writestr(f"{safe_name}/vite.config.js", DEFAULT_VITE_CONFIG)
        zf.writestr(f"{safe_name}/src/main.jsx", DEFAULT_MAIN_JSX)
        zf.writestr(f"{safe_name}/README.md", DEFAULT_README.replace("__NAME__", project.name))

        files_to_write = list(project.files) if project.files else []
        if not files_to_write and project.current_code:
            files_to_write = [FileEntry(path="App.jsx", content=project.current_code)]

        for f in files_to_write:
            target = f.content
            if f.path.lower().endswith("app.jsx"):
                target = adapt_app_for_export(target)
                zf.writestr(f"{safe_name}/src/App.jsx", target)
            elif f.path in ("package.json", "index.html", "vite.config.js", "README.md"):
                continue
            else:
                if f.path.lower().endswith((".jsx", ".js", ".ts", ".tsx", ".css")):
                    zf.writestr(f"{safe_name}/src/{f.path}", target)
                else:
                    zf.writestr(f"{safe_name}/{f.path}", target)

    buf.seek(0)
    return FastResponse(content=buf.read(), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'})
