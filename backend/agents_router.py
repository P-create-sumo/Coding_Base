"""Agents router: conversational, autonomous (with tools), coding (project iteration)."""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import json
import asyncio
import re
import httpx
from bs4 import BeautifulSoup

from core import db, get_current_user, User, chat_completion, now_iso, new_id, logger
from knowledge_router import search_chunks, rerank_chunks


router = APIRouter(prefix="/agents", tags=["agents"])


# ======== Models ========

AGENT_TYPES = ["conversational", "autonomous", "coding"]


class Agent(BaseModel):
    id: str = Field(default_factory=lambda: new_id())
    user_id: str
    name: str
    type: str  # conversational | autonomous | coding
    description: str = ""
    system_prompt: str = ""
    knowledge_base_id: Optional[str] = None
    linked_project_id: Optional[str] = None  # for coding agent
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class AgentMessage(BaseModel):
    id: str = Field(default_factory=lambda: new_id())
    agent_id: str
    role: str  # user | assistant | tool
    content: str
    tool_calls: List[Dict[str, Any]] = []
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class CreateAgentRequest(BaseModel):
    name: str
    type: str
    description: str = ""
    system_prompt: str = ""
    knowledge_base_id: Optional[str] = None
    linked_project_id: Optional[str] = None


class ChatRequest(BaseModel):
    prompt: str


# ======== Default System Prompts ========

DEFAULT_SYSTEM_PROMPTS = {
    "conversational": "You are a helpful AI assistant. Have natural, friendly conversations with the user. Use markdown formatting for clarity. Remember the conversation context.",
    "autonomous": (
        "You are an autonomous research AI agent. Break down complex tasks into steps and use the available tools to accomplish them. "
        "Always think step by step. Use web_search to find information, read_url to fetch full page content, "
        "calculator to evaluate math expressions, and knowledge_query to search the linked knowledge base when relevant. "
        "After gathering enough information, synthesise a clear, well-formatted final answer for the user using markdown."
    ),
    "coding": (
        "You are a coding agent that helps improve and debug a React project. "
        "Analyse the current code shown in context. When asked to fix a bug or add a feature, output the COMPLETE updated App.jsx using the same multi-file format used by the App Creator (===FILE: App.jsx===...===END===). "
        "Keep the file self-contained for react-live preview (no imports/exports, use React.useState etc, end with render(<App />))."
    ),
}


# ======== Tools ========

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information. Returns a list of results with titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Fetch the textual content of a webpage URL.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Full URL to fetch"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a math expression. Supports +, -, *, /, parentheses, **, sqrt, common math.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "Math expression e.g. (12*5)/3"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_query",
            "description": "Search the agent's linked knowledge base for relevant chunks. Use this when the user references uploaded documents.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    },
]


async def tool_web_search(query: str) -> str:
    """DuckDuckGo HTML search with lite fallback (no API key)."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    # Try main HTML interface first
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            r = await client.get("https://html.duckduckgo.com/html/", params={"q": query}, headers=headers)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for el in soup.select(".result, .web-result")[:6]:
            title_el = el.select_one(".result__title, .result__a")
            url_el = el.select_one(".result__url")
            snippet_el = el.select_one(".result__snippet")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "url": url_el.get_text(strip=True) if url_el else "",
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                })
        if results:
            return "\n\n".join([f"{i+1}. {r['title']}\n   {r['url']}\n   {r['snippet']}" for i, r in enumerate(results)])
    except Exception as e:
        logger.info(f"DDG main failed: {e}")

    # Fallback: lite version
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            r = await client.get("https://lite.duckduckgo.com/lite/", params={"q": query}, headers=headers)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for a in soup.select("a.result-link")[:6]:
            results.append({"title": a.get_text(strip=True), "url": a.get("href", ""), "snippet": ""})
        # snippets are in a sibling td
        snippets = [td.get_text(strip=True) for td in soup.select("td.result-snippet")][:6]
        for i, s in enumerate(snippets):
            if i < len(results):
                results[i]["snippet"] = s
        if results:
            return "\n\n".join([f"{i+1}. {r['title']}\n   {r['url']}\n   {r['snippet']}" for i, r in enumerate(results)])
    except Exception as e:
        logger.info(f"DDG lite failed: {e}")

    return f"No results found for: {query} (web search unavailable)"


async def tool_read_url(url: str) -> str:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 FORGE-Agent/1.0"})
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        text = re.sub(r"\n\s*\n", "\n\n", text).strip()
        return text[:6000] + ("...[truncated]" if len(text) > 6000 else "")
    except Exception as e:
        return f"Fetch error: {e}"


def tool_calculator(expression: str) -> str:
    """Safe math evaluator using AST whitelist with bounds."""
    import ast
    import operator as op

    OPS = {
        ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
        ast.Div: op.truediv, ast.FloorDiv: op.floordiv, ast.Mod: op.mod,
        ast.USub: op.neg, ast.UAdd: op.pos,
    }
    # Power handled separately with bounds

    expr = expression.replace("^", "**").strip()
    if not expr or len(expr) > 200:
        return "Error: empty or too long"

    def _eval(node):
        if isinstance(node, ast.Num):  # py<3.8
            return node.n
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Only numeric constants allowed")
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Pow):
                # Limit exponent magnitude to prevent DoS
                if abs(right) > 100 or abs(left) > 1e6:
                    raise ValueError("Exponent too large")
                return left ** right
            if type(node.op) in OPS:
                return OPS[type(node.op)](left, right)
            raise ValueError(f"Operator not allowed: {type(node.op).__name__}")
        if isinstance(node, ast.UnaryOp):
            if type(node.op) in OPS:
                return OPS[type(node.op)](_eval(node.operand))
            raise ValueError(f"Unary op not allowed: {type(node.op).__name__}")
        raise ValueError(f"Node not allowed: {type(node).__name__}")

    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval(tree.body)
        if isinstance(result, float) and (abs(result) == float("inf") or result != result):
            return "Error: result overflow / NaN"
        return str(result)
    except ValueError as e:
        return f"Calc error: {e}"
    except Exception as e:
        return f"Calc error: {e}"


async def tool_knowledge_query(query: str, kb_id: Optional[str], user_id: str) -> str:
    if not kb_id:
        return "No knowledge base linked to this agent."
    chunks = await search_chunks(kb_id, user_id, query, top_k=5)
    if not chunks:
        return "No relevant content found in knowledge base."
    return "\n\n".join([f"[{c['doc_name']}]\n{c['content']}" for c in chunks])


async def execute_tool(name: str, args: Dict[str, Any], agent: Agent) -> str:
    if name == "web_search":
        return await tool_web_search(args.get("query", ""))
    if name == "read_url":
        return await tool_read_url(args.get("url", ""))
    if name == "calculator":
        return tool_calculator(args.get("expression", ""))
    if name == "knowledge_query":
        return await tool_knowledge_query(args.get("query", ""), agent.knowledge_base_id, agent.user_id)
    return f"Unknown tool: {name}"


# ======== Routes ========

@router.get("", response_model=List[Agent])
async def list_agents(user: User = Depends(get_current_user)):
    docs = await db.agents.find({"user_id": user.user_id}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    return [Agent(**d) for d in docs]


@router.post("", response_model=Agent)
async def create_agent(req: CreateAgentRequest, user: User = Depends(get_current_user)):
    if req.type not in AGENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of {AGENT_TYPES}")

    if req.type == "coding":
        if not req.linked_project_id:
            raise HTTPException(status_code=400, detail="Coding agents require a linked_project_id")
        proj = await db.projects.find_one(
            {"id": req.linked_project_id, "user_id": user.user_id}, {"_id": 0}
        )
        if not proj:
            raise HTTPException(status_code=400, detail="linked_project_id does not exist or is not yours")

    if req.knowledge_base_id:
        kb = await db.knowledge_bases.find_one(
            {"id": req.knowledge_base_id, "user_id": user.user_id}, {"_id": 0}
        )
        if not kb:
            raise HTTPException(status_code=400, detail="knowledge_base_id does not exist or is not yours")

    sys_prompt = req.system_prompt or DEFAULT_SYSTEM_PROMPTS[req.type]
    agent = Agent(
        user_id=user.user_id, name=req.name, type=req.type, description=req.description,
        system_prompt=sys_prompt, knowledge_base_id=req.knowledge_base_id,
        linked_project_id=req.linked_project_id,
    )
    await db.agents.insert_one(agent.model_dump())
    return agent


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str, user: User = Depends(get_current_user)):
    doc = await db.agents.find_one({"id": agent_id, "user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Agent not found")
    return Agent(**doc)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, user: User = Depends(get_current_user)):
    result = await db.agents.delete_one({"id": agent_id, "user_id": user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.agent_messages.delete_many({"agent_id": agent_id})
    return {"success": True}


@router.get("/{agent_id}/messages", response_model=List[AgentMessage])
async def list_agent_messages(agent_id: str, user: User = Depends(get_current_user)):
    agent = await db.agents.find_one({"id": agent_id, "user_id": user.user_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    docs = await db.agent_messages.find({"agent_id": agent_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return [AgentMessage(**d) for d in docs]


def _build_history_for_llm(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert stored history to OpenAI-compatible messages."""
    out = []
    for m in history:
        if m["role"] == "tool":
            out.append({
                "role": "tool",
                "content": m["content"],
                "tool_call_id": m.get("tool_call_id", ""),
                "name": m.get("name", ""),
            })
        elif m["role"] == "assistant":
            msg = {"role": "assistant", "content": m.get("content") or None}
            if m.get("tool_calls"):
                msg["tool_calls"] = m["tool_calls"]
            out.append(msg)
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out


async def _agent_chat_simple(agent: Agent, prompt: str) -> AgentMessage:
    """Conversational agent (no tools) with KB context injection."""
    user_msg = AgentMessage(agent_id=agent.id, role="user", content=prompt)
    await db.agent_messages.insert_one(user_msg.model_dump())

    history_docs = await db.agent_messages.find({"agent_id": agent.id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    history = history_docs[:-1]

    # Inject KB context (hybrid rerank)
    kb_ctx = ""
    if agent.knowledge_base_id:
        chunks = await rerank_chunks(agent.knowledge_base_id, agent.user_id, prompt, top_k=4)
        if chunks:
            kb_ctx = "\n\n== Relevant context from knowledge base ==\n" + "\n\n".join(
                [f"[{c['doc_name']}] {c['content']}" for c in chunks]
            )

    system = agent.system_prompt + kb_ctx
    messages = [{"role": "system", "content": system}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": prompt})

    response = chat_completion(messages, stream=False)
    content = response.choices[0].message.content or ""

    asst_msg = AgentMessage(agent_id=agent.id, role="assistant", content=content)
    await db.agent_messages.insert_one(asst_msg.model_dump())

    await db.agents.update_one({"id": agent.id}, {"$set": {"updated_at": now_iso()}})
    return asst_msg


async def _agent_run_autonomous(agent: Agent, prompt: str, max_steps: int = 8):
    """Autonomous agent with tool use. Yields SSE events as it works."""
    user_msg = AgentMessage(agent_id=agent.id, role="user", content=prompt)
    await db.agent_messages.insert_one(user_msg.model_dump())
    yield {"type": "user", "message": user_msg.model_dump()}

    history_docs = await db.agent_messages.find({"agent_id": agent.id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    history = history_docs  # includes the user msg we just inserted

    messages = [{"role": "system", "content": agent.system_prompt}] + _build_history_for_llm(history)

    step = 0
    while step < max_steps:
        step += 1
        try:
            response = chat_completion(messages, stream=False, tools=TOOL_DEFS, tool_choice="auto")
        except Exception as e:
            logger.exception("autonomous LLM error")
            yield {"type": "error", "detail": str(e)}
            return

        choice = response.choices[0].message
        content = choice.content or ""
        tool_calls = getattr(choice, "tool_calls", None)

        if tool_calls:
            # Save assistant message with tool_calls
            tc_list = []
            for tc in tool_calls:
                tc_list.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                })
            asst_msg = AgentMessage(agent_id=agent.id, role="assistant", content=content, tool_calls=tc_list)
            await db.agent_messages.insert_one(asst_msg.model_dump())
            yield {"type": "step", "thought": content, "tool_calls": tc_list, "step": step}

            messages.append({
                "role": "assistant",
                "content": content or None,
                "tool_calls": tc_list,
            })

            # Execute each tool
            for tc in tc_list:
                fn = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except Exception:
                    args = {}
                yield {"type": "tool_call", "tool": fn, "args": args, "step": step}
                result = await execute_tool(fn, args, agent)
                tool_msg = AgentMessage(
                    agent_id=agent.id, role="tool", content=result,
                    tool_call_id=tc["id"], name=fn,
                )
                await db.agent_messages.insert_one(tool_msg.model_dump())
                messages.append({
                    "role": "tool", "content": result,
                    "tool_call_id": tc["id"], "name": fn,
                })
                yield {"type": "tool_result", "tool": fn, "result": result[:1500], "step": step}

            continue  # next loop iteration

        # No tool calls = final answer
        asst_msg = AgentMessage(agent_id=agent.id, role="assistant", content=content)
        await db.agent_messages.insert_one(asst_msg.model_dump())
        await db.agents.update_one({"id": agent.id}, {"$set": {"updated_at": now_iso()}})
        yield {"type": "final", "message": asst_msg.model_dump()}
        return

    yield {"type": "final", "message": {"content": "(Max steps reached)", "agent_id": agent.id, "role": "assistant"}}


async def _agent_coding_iterate(agent: Agent, prompt: str) -> AgentMessage:
    """Coding agent: takes the linked project's current code as context and outputs an updated App.jsx."""
    if not agent.linked_project_id:
        raise HTTPException(status_code=400, detail="Coding agent has no linked project")
    proj = await db.projects.find_one(
        {"id": agent.linked_project_id, "user_id": agent.user_id}, {"_id": 0}
    )
    if not proj:
        raise HTTPException(status_code=404, detail="Linked project not found")

    user_msg = AgentMessage(agent_id=agent.id, role="user", content=prompt)
    await db.agent_messages.insert_one(user_msg.model_dump())

    current_code = proj.get("current_code", "") or "// (empty)"
    system = agent.system_prompt + f"\n\n== CURRENT App.jsx ==\n```jsx\n{current_code}\n```\n"

    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    response = chat_completion(messages, stream=False)
    content = response.choices[0].message.content or ""

    # Extract new App.jsx
    new_code = None
    m = re.search(r"===FILE:\s*App\.jsx\s*===\s*\n(.*?)\n===END===", content, re.DOTALL)
    if m:
        new_code = m.group(1).strip()
    else:
        cb = re.search(r"```(?:jsx|javascript|js|tsx)?\s*\n([\s\S]*?)\n```", content)
        if cb:
            new_code = cb.group(1).strip()

    if new_code:
        await db.projects.update_one(
            {"id": agent.linked_project_id},
            {"$set": {
                "current_code": new_code,
                "files": [{"path": "App.jsx", "content": new_code}],
                "updated_at": now_iso(),
            }},
        )

    asst_msg = AgentMessage(agent_id=agent.id, role="assistant", content=content)
    await db.agent_messages.insert_one(asst_msg.model_dump())
    await db.agents.update_one({"id": agent.id}, {"$set": {"updated_at": now_iso()}})
    return asst_msg


@router.post("/{agent_id}/chat")
async def agent_chat(agent_id: str, req: ChatRequest, user: User = Depends(get_current_user)):
    """Sync chat endpoint for conversational + coding agents."""
    agent_doc = await db.agents.find_one({"id": agent_id, "user_id": user.user_id}, {"_id": 0})
    if not agent_doc:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent = Agent(**agent_doc)

    if agent.type == "coding":
        msg = await _agent_coding_iterate(agent, req.prompt)
    elif agent.type == "conversational":
        msg = await _agent_chat_simple(agent, req.prompt)
    else:
        raise HTTPException(status_code=400, detail="Use /run-task for autonomous agents")

    return {"message": msg.model_dump()}


@router.post("/{agent_id}/chat-stream")
async def agent_chat_stream(agent_id: str, req: ChatRequest, user: User = Depends(get_current_user)):
    """Streaming SSE chat for conversational + coding agents."""
    agent_doc = await db.agents.find_one({"id": agent_id, "user_id": user.user_id}, {"_id": 0})
    if not agent_doc:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent = Agent(**agent_doc)
    if agent.type not in ("conversational", "coding"):
        raise HTTPException(status_code=400, detail="Streaming only for conversational/coding agents")

    async def event_stream():
        # Save user message + emit user event
        user_msg = AgentMessage(agent_id=agent.id, role="user", content=req.prompt)
        await db.agent_messages.insert_one(user_msg.model_dump())
        yield f"data: {json.dumps({'type': 'user', 'message': user_msg.model_dump()})}\n\n"

        # Build context
        history_docs = await db.agent_messages.find({"agent_id": agent.id}, {"_id": 0}).sort("created_at", 1).to_list(500)
        history = history_docs[:-1]

        if agent.type == "coding":
            if not agent.linked_project_id:
                yield f"data: {json.dumps({'type': 'error', 'detail': 'No linked project'})}\n\n"
                return
            proj = await db.projects.find_one(
                {"id": agent.linked_project_id, "user_id": agent.user_id}, {"_id": 0}
            )
            if not proj:
                yield f"data: {json.dumps({'type': 'error', 'detail': 'Linked project missing'})}\n\n"
                return
            current_code = proj.get("current_code", "") or "// (empty)"
            system = agent.system_prompt + f"\n\n== CURRENT App.jsx ==\n```jsx\n{current_code}\n```\n"
            messages = [{"role": "system", "content": system}, {"role": "user", "content": req.prompt}]
        else:
            kb_ctx = ""
            if agent.knowledge_base_id:
                chunks = await rerank_chunks(agent.knowledge_base_id, agent.user_id, req.prompt, top_k=4)
                if chunks:
                    kb_ctx = "\n\n== Relevant context from knowledge base ==\n" + "\n\n".join(
                        [f"[{c['doc_name']}] {c['content']}" for c in chunks]
                    )
            system = agent.system_prompt + kb_ctx
            messages = [{"role": "system", "content": system}]
            for m in history:
                messages.append({"role": m["role"], "content": m["content"]})
            messages.append({"role": "user", "content": req.prompt})

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

            # Persist + extras
            asst_msg = AgentMessage(agent_id=agent.id, role="assistant", content=full_text)
            await db.agent_messages.insert_one(asst_msg.model_dump())
            await db.agents.update_one({"id": agent.id}, {"$set": {"updated_at": now_iso()}})

            updated_code = None
            if agent.type == "coding":
                m = re.search(r"===FILE:\s*App\.jsx\s*===\s*\n(.*?)\n===END===", full_text, re.DOTALL)
                if m:
                    updated_code = m.group(1).strip()
                else:
                    cb = re.search(r"```(?:jsx|javascript|js|tsx)?\s*\n([\s\S]*?)\n```", full_text)
                    if cb:
                        updated_code = cb.group(1).strip()
                if updated_code:
                    await db.projects.update_one(
                        {"id": agent.linked_project_id},
                        {"$set": {
                            "current_code": updated_code,
                            "files": [{"path": "App.jsx", "content": updated_code}],
                            "updated_at": now_iso(),
                        }},
                    )

            yield f"data: {json.dumps({'type': 'done', 'message': asst_msg.model_dump(), 'updated_code': updated_code})}\n\n"
        except Exception as e:
            logger.exception("chat stream error")
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{agent_id}/run-task")
async def agent_run_task(agent_id: str, req: ChatRequest, user: User = Depends(get_current_user)):
    """Streaming SSE endpoint for autonomous agent execution."""
    agent_doc = await db.agents.find_one({"id": agent_id, "user_id": user.user_id}, {"_id": 0})
    if not agent_doc:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent = Agent(**agent_doc)
    if agent.type != "autonomous":
        raise HTTPException(status_code=400, detail="Only autonomous agents support run-task")

    async def event_stream():
        try:
            async for evt in _agent_run_autonomous(agent, req.prompt):
                yield f"data: {json.dumps(evt)}\n\n"
                await asyncio.sleep(0)
        except Exception as e:
            logger.exception("agent run error")
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
