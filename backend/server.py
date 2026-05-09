"""FORGE backend — main FastAPI app, auth + module routers."""
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import logging
import uuid
import httpx
from datetime import datetime, timezone, timedelta

from core import db, get_current_user, User, client, logger
from apps_router import router as apps_router
from knowledge_router import router as knowledge_router
from agents_router import router as agents_router


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = FastAPI()
api_router = APIRouter(prefix="/api")


# ======== Auth Endpoints ========

class SessionRequest(BaseModel):
    session_id: str


class MigrateRequest(BaseModel):
    legacy_user_id: str


@api_router.post("/auth/session")
async def auth_session(req: SessionRequest, response: Response):
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

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user.user_id,
        "session_token": data["session_token"],
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    response.set_cookie(
        key="session_token", value=data["session_token"],
        httponly=True, secure=True, samesite="none", path="/",
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
    if not req.legacy_user_id or req.legacy_user_id == user.user_id:
        return {"migrated": 0}
    result = await db.projects.update_many(
        {"user_id": req.legacy_user_id}, {"$set": {"user_id": user.user_id}},
    )
    return {"migrated": result.modified_count}


@api_router.get("/")
async def root():
    return {"message": "FORGE AI Platform API", "features": ["app-creator", "agents", "knowledge"]}


# Mount sub-routers under /api
api_router.include_router(apps_router)
api_router.include_router(knowledge_router)
api_router.include_router(agents_router)

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
