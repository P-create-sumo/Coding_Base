"""Shared models, db, auth, and llm helpers."""
from fastapi import HTTPException, Request, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import uuid
import logging
from datetime import datetime, timezone

import litellm
# emergentintegrations removed — using direct OpenAI API
def get_integration_proxy_url(): return 'https://api.openai.com'


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
LLM_MODEL_NAME = "claude-sonnet-4-5-20250929"

logger = logging.getLogger(__name__)


# ======== Tokenization for BM25 ========

import re as _re
_STOP = set("a an the is are was were be been being have has had do does did will would should could may might must can of in on at to for from with by about as into like through after before between out against without within near no not yes and or but if then so than that this these those it its he she they we you i".split())
_WORD = _re.compile(r"[A-Za-z][A-Za-z0-9_]+")


def tokenize(text: str) -> list:
    if not text:
        return []
    return [w.lower() for w in _WORD.findall(text) if len(w) > 1 and w.lower() not in _STOP]


# ======== Auth Models ========

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ======== Auth helper ========

async def get_current_user(request: Request) -> User:
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


# ======== LLM helpers ========

def proxy_params() -> Dict[str, Any]:
    proxy_url = get_integration_proxy_url()
    return {
        "api_key": EMERGENT_LLM_KEY,
        "api_base": proxy_url + "/llm",
        "custom_llm_provider": "openai",
    }


def chat_completion(messages: List[Dict[str, Any]], stream: bool = False, model: str = LLM_MODEL_NAME, **extra) -> Any:
    params = {
        "model": model,
        "messages": messages,
        "stream": stream,
        **proxy_params(),
        **extra,
    }
    return litellm.completion(**params)


def embed_text(text: str) -> list:
    """Return tokens for BM25 (no external embedding API)."""
    return tokenize(text)


def embed_batch(texts: list) -> list:
    return [tokenize(t) for t in texts]


def cosine_similarity(a: list, b: list) -> float:
    """Kept for backward compat (unused with BM25)."""
    return 0.0


def bm25_score(query_tokens: list, doc_tokens: list, idf: dict, avgdl: float, k1: float = 1.5, b: float = 0.75) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    score = 0.0
    dl = len(doc_tokens)
    from collections import Counter
    tf = Counter(doc_tokens)
    for q in query_tokens:
        if q not in tf:
            continue
        f = tf[q]
        i = idf.get(q, 0.0)
        score += i * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / max(avgdl, 1)))
    return score


# ======== Generic helpers ========

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}" if prefix else str(uuid.uuid4())
