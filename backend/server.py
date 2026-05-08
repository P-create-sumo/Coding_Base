from fastapi import FastAPI, APIRouter, HTTPException, Header
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone

from emergentintegrations.llm.chat import LlmChat, UserMessage


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
LLM_MODEL_PROVIDER = "anthropic"
LLM_MODEL_NAME = "claude-sonnet-4-5-20250929"

app = FastAPI()
api_router = APIRouter(prefix="/api")


# ============== MODELS ==============

class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    description: str = ""
    template_id: Optional[str] = None
    current_code: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    template_id: Optional[str] = None


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    role: str  # 'user' or 'assistant'
    content: str
    code: Optional[str] = None  # extracted code if assistant message
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GenerateRequest(BaseModel):
    prompt: str


class UpdateCodeRequest(BaseModel):
    code: str


# ============== TEMPLATES ==============

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


# ============== HELPERS ==============

SYSTEM_PROMPT = """You are an expert React developer that generates COMPLETE, RUNNABLE React components for a live preview environment using react-live.

CRITICAL RULES:
1. Output ONLY a single React functional component called `App` - no imports, no exports, no JSX.Fragment shortcuts (<>), use React.Fragment if needed.
2. The environment has `React` available globally. Use `React.useState`, `React.useEffect`, etc. NOT bare `useState`.
3. End your code with: `render(<App />);`
4. NO import statements. NO export statements. NO require().
5. Use ONLY inline Tailwind CSS classes for styling. No external CSS, no styled-components.
6. NO external libraries. Only React and Tailwind. NO lucide-react, NO framer-motion, NO axios.
7. For icons, use unicode symbols (▲▼●■★✓✗→←↑↓) or simple inline SVG.
8. Make the component visually impressive, functional, and interactive where appropriate.
9. Default styling: dark theme with black/charcoal backgrounds (#050505, #121212), white text, accents in red (#FF3B30) and yellow (#FFCC00). Sharp corners (no rounded-* classes by default unless explicitly asked).
10. Make components responsive and use semantic HTML.
11. Handle edge cases gracefully (empty states, loading states if applicable).

OUTPUT FORMAT:
Wrap your code in a single ```jsx code block. Optionally provide a brief 1-2 sentence explanation BEFORE the code block.

EXAMPLE OUTPUT:
Here's your dashboard with KPIs and chart.

```jsx
const App = () => {
  const [count, setCount] = React.useState(0);
  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <h1 className="text-4xl font-bold">Dashboard</h1>
      <button 
        onClick={() => setCount(count + 1)}
        className="mt-4 bg-[#FF3B30] text-white px-6 py-3 font-bold uppercase"
      >
        Clicks: {count}
      </button>
    </div>
  );
};

render(<App />);
```
"""


def extract_code(content: str) -> Optional[str]:
    """Extract the first code block from a markdown string."""
    pattern = r"```(?:jsx|javascript|js|tsx)?\s*\n([\s\S]*?)\n```"
    match = re.search(pattern, content)
    if match:
        return match.group(1).strip()
    return None


async def call_claude(session_id: str, history: List[Message], new_prompt: str) -> str:
    """Call Claude with full session history."""
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=SYSTEM_PROMPT,
    ).with_model(LLM_MODEL_PROVIDER, LLM_MODEL_NAME)

    # Build a contextual prompt that includes prior history for stateless re-init
    context_parts = []
    for msg in history:
        if msg.role == "user":
            context_parts.append(f"User previously said: {msg.content}")
        else:
            # only summarize that we generated something
            if msg.code:
                context_parts.append("Assistant previously generated code (kept in current state).")
    context_block = "\n".join(context_parts[-6:]) if context_parts else ""

    full_prompt = (
        f"{context_block}\n\nNew user request: {new_prompt}"
        if context_block
        else new_prompt
    )

    user_message = UserMessage(text=full_prompt)
    response = await chat.send_message(user_message)
    return response


# ============== ROUTES ==============

@api_router.get("/")
async def root():
    return {"message": "AI App Builder API", "model": LLM_MODEL_NAME}


@api_router.get("/templates")
async def get_templates():
    return TEMPLATES


@api_router.get("/projects", response_model=List[Project])
async def list_projects(x_user_id: str = Header(...)):
    docs = await db.projects.find({"user_id": x_user_id}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    return [Project(**doc) for doc in docs]


@api_router.post("/projects", response_model=Project)
async def create_project(req: CreateProjectRequest, x_user_id: str = Header(...)):
    project = Project(
        user_id=x_user_id,
        name=req.name,
        description=req.description,
        template_id=req.template_id,
    )
    await db.projects.insert_one(project.model_dump())
    return project


@api_router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str, x_user_id: str = Header(...)):
    doc = await db.projects.find_one({"id": project_id, "user_id": x_user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    return Project(**doc)


@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, x_user_id: str = Header(...)):
    result = await db.projects.delete_one({"id": project_id, "user_id": x_user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.messages.delete_many({"project_id": project_id})
    return {"success": True}


@api_router.get("/projects/{project_id}/messages", response_model=List[Message])
async def list_messages(project_id: str, x_user_id: str = Header(...)):
    project = await db.projects.find_one({"id": project_id, "user_id": x_user_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    docs = await db.messages.find({"project_id": project_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return [Message(**doc) for doc in docs]


@api_router.post("/projects/{project_id}/generate")
async def generate_code(project_id: str, req: GenerateRequest, x_user_id: str = Header(...)):
    project_doc = await db.projects.find_one({"id": project_id, "user_id": x_user_id}, {"_id": 0})
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")

    # Save user message
    user_msg = Message(project_id=project_id, role="user", content=req.prompt)
    await db.messages.insert_one(user_msg.model_dump())

    # Get history
    history_docs = await db.messages.find({"project_id": project_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    history = [Message(**d) for d in history_docs[:-1]]  # exclude the just-inserted user msg

    # Call Claude
    try:
        response_text = await call_claude(project_id, history, req.prompt)
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

    # Extract code
    code = extract_code(response_text)

    # Save assistant message
    assistant_msg = Message(
        project_id=project_id,
        role="assistant",
        content=response_text,
        code=code,
    )
    await db.messages.insert_one(assistant_msg.model_dump())

    # Update project current code
    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if code:
        update_fields["current_code"] = code
    await db.projects.update_one({"id": project_id}, {"$set": update_fields})

    return {
        "user_message": user_msg.model_dump(),
        "assistant_message": assistant_msg.model_dump(),
        "code": code,
    }


@api_router.put("/projects/{project_id}/code")
async def update_code(project_id: str, req: UpdateCodeRequest, x_user_id: str = Header(...)):
    result = await db.projects.update_one(
        {"id": project_id, "user_id": x_user_id},
        {"$set": {"current_code": req.code, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True}


# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
