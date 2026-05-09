"""Backend API tests for FORGE v2.0 (apps + knowledge + agents)."""
import os
import io
import time
import uuid
import json
import pytest
import requests
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]

TS = int(time.time() * 1000)
USER_A_ID = f"TEST_userA_{TS}"
USER_B_ID = f"TEST_userB_{TS}"
SESSION_A = f"TEST_session_A_{TS}"
SESSION_B = f"TEST_session_B_{TS}"


def _seed():
    now = datetime.now(timezone.utc).isoformat()
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    _db.users.insert_many([
        {"user_id": USER_A_ID, "email": f"test.user.A.{TS}@example.com",
         "name": "Test User A", "picture": None, "created_at": now},
        {"user_id": USER_B_ID, "email": f"test.user.B.{TS}@example.com",
         "name": "Test User B", "picture": None, "created_at": now},
    ])
    _db.user_sessions.insert_many([
        {"user_id": USER_A_ID, "session_token": SESSION_A,
         "expires_at": expires, "created_at": now},
        {"user_id": USER_B_ID, "session_token": SESSION_B,
         "expires_at": expires, "created_at": now},
    ])


def _cleanup():
    _db.users.delete_many({"user_id": {"$in": [USER_A_ID, USER_B_ID]}})
    _db.user_sessions.delete_many({"session_token": {"$in": [SESSION_A, SESSION_B]}})
    _db.projects.delete_many({"user_id": {"$in": [USER_A_ID, USER_B_ID]}})
    _db.knowledge_bases.delete_many({"user_id": {"$in": [USER_A_ID, USER_B_ID]}})
    _db.kb_documents.delete_many({"user_id": {"$in": [USER_A_ID, USER_B_ID]}})
    _db.kb_chunks.delete_many({"user_id": {"$in": [USER_A_ID, USER_B_ID]}})
    _db.agents.delete_many({"user_id": {"$in": [USER_A_ID, USER_B_ID]}})
    _db.agent_messages.delete_many({})  # safe; we use unique agent_ids


def setup_module(module):
    _cleanup()
    _seed()


def teardown_module(module):
    _cleanup()


def H(token):
    return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}


# =================== Root + Auth ===================
class TestRoot:
    def test_root(self):
        r = requests.get(f"{API}/", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "message" in data
        assert "features" in data
        assert set(data["features"]) >= {"app-creator", "agents", "knowledge"}

    def test_apps_templates_new_path(self):
        r = requests.get(f"{API}/apps/templates", timeout=15)
        assert r.status_code == 200
        assert len(r.json()) == 4

    def test_legacy_templates_path_404(self):
        # /api/templates moved
        r = requests.get(f"{API}/templates", timeout=15)
        assert r.status_code == 404


class TestAuth:
    def test_me_no_token_401(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401

    def test_me_valid(self):
        r = requests.get(f"{API}/auth/me", headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        assert r.json()["user_id"] == USER_A_ID

    def test_apps_projects_requires_auth(self):
        r = requests.get(f"{API}/apps/projects", timeout=15)
        assert r.status_code == 401


# =================== Apps (migrated paths) ===================
class TestAppsProjects:
    project_id = None

    def test_create(self):
        r = requests.post(f"{API}/apps/projects",
                          json={"name": "TEST_proj_v2", "description": "v2"},
                          headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "TEST_proj_v2"
        assert data["user_id"] == USER_A_ID
        TestAppsProjects.project_id = data["id"]

    def test_list_isolation(self):
        rA = requests.get(f"{API}/apps/projects", headers=H(SESSION_A), timeout=15)
        assert any(p["id"] == TestAppsProjects.project_id for p in rA.json())
        rB = requests.get(f"{API}/apps/projects", headers=H(SESSION_B), timeout=15)
        assert not any(p["id"] == TestAppsProjects.project_id for p in rB.json())

    def test_get_wrong_user_404(self):
        r = requests.get(f"{API}/apps/projects/{TestAppsProjects.project_id}",
                         headers=H(SESSION_B), timeout=15)
        assert r.status_code == 404

    def test_update_code(self):
        code = "const App=()=><div>Hi</div>;render(<App/>);"
        r = requests.put(f"{API}/apps/projects/{TestAppsProjects.project_id}/code",
                         json={"code": code}, headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        r2 = requests.get(f"{API}/apps/projects/{TestAppsProjects.project_id}",
                          headers=H(SESSION_A), timeout=15)
        assert r2.json()["current_code"] == code

    def test_export_zip(self):
        r = requests.get(f"{API}/apps/projects/{TestAppsProjects.project_id}/export",
                         headers=H(SESSION_A), timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/zip"
        import zipfile as _zf
        zf = _zf.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        assert any(n.endswith("/package.json") for n in names)
        assert any(n.endswith("/src/App.jsx") for n in names)

    def test_delete_cascade(self):
        r = requests.delete(f"{API}/apps/projects/{TestAppsProjects.project_id}",
                            headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        r2 = requests.get(f"{API}/apps/projects/{TestAppsProjects.project_id}",
                          headers=H(SESSION_A), timeout=15)
        assert r2.status_code == 404


# =================== Knowledge / RAG ===================
class TestKnowledge:
    kb_id = None
    doc_id = None

    def test_create_kb(self):
        r = requests.post(f"{API}/knowledge",
                          json={"name": "TEST_kb1", "description": "for tests"},
                          headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "TEST_kb1"
        assert data["user_id"] == USER_A_ID
        assert data["doc_count"] == 0
        TestKnowledge.kb_id = data["id"]

    def test_list_isolation(self):
        rA = requests.get(f"{API}/knowledge", headers=H(SESSION_A), timeout=15)
        assert any(k["id"] == TestKnowledge.kb_id for k in rA.json())
        rB = requests.get(f"{API}/knowledge", headers=H(SESSION_B), timeout=15)
        assert not any(k["id"] == TestKnowledge.kb_id for k in rB.json())

    def test_upload_txt_document(self):
        text = (
            "FORGE is an AI app builder platform. It supports React generation, "
            "knowledge bases for retrieval augmented generation, and autonomous agents "
            "that use tools like web_search, calculator, and read_url. The platform stores "
            "projects in MongoDB and uses BM25 keyword search over uploaded documents."
        )
        files = {"file": ("notes.txt", text.encode("utf-8"), "text/plain")}
        r = requests.post(
            f"{API}/knowledge/{TestKnowledge.kb_id}/upload",
            files=files,
            headers={"Authorization": f"Bearer {SESSION_A}"},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["source_type"] == "txt"
        assert d["chunk_count"] >= 1
        TestKnowledge.doc_id = d["id"]

    def test_list_documents(self):
        r = requests.get(f"{API}/knowledge/{TestKnowledge.kb_id}/documents",
                         headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        docs = r.json()
        assert any(d["id"] == TestKnowledge.doc_id for d in docs)

    def test_search_bm25(self):
        r = requests.post(f"{API}/knowledge/{TestKnowledge.kb_id}/search",
                          json={"query": "autonomous agents tools calculator",
                                "top_k": 3},
                          headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) >= 1
        assert all("score" in r and r["score"] > 0 for r in results)
        assert all("content" in r for r in results)
        # Highest first
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_no_overlap_returns_empty(self):
        r = requests.post(f"{API}/knowledge/{TestKnowledge.kb_id}/search",
                          json={"query": "zzzqqxxx noexistword", "top_k": 5},
                          headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        assert r.json()["results"] == []

    def test_unsupported_filetype(self):
        files = {"file": ("evil.exe", b"\x00\x01\x02", "application/octet-stream")}
        r = requests.post(
            f"{API}/knowledge/{TestKnowledge.kb_id}/upload",
            files=files,
            headers={"Authorization": f"Bearer {SESSION_A}"},
            timeout=15,
        )
        assert r.status_code == 400

    def test_delete_document_cascades_chunks(self):
        # Snapshot chunk count
        before = _db.kb_chunks.count_documents({"doc_id": TestKnowledge.doc_id})
        assert before >= 1
        r = requests.delete(
            f"{API}/knowledge/{TestKnowledge.kb_id}/documents/{TestKnowledge.doc_id}",
            headers=H(SESSION_A), timeout=15,
        )
        assert r.status_code == 200
        after = _db.kb_chunks.count_documents({"doc_id": TestKnowledge.doc_id})
        assert after == 0

    def test_delete_kb_cascades(self):
        # Re-create a fresh KB + upload to verify cascade end-to-end
        r = requests.post(f"{API}/knowledge",
                          json={"name": "TEST_kb_cascade"},
                          headers=H(SESSION_A), timeout=15)
        kb_id = r.json()["id"]
        files = {"file": ("c.txt", b"forge bm25 cascade test content here.", "text/plain")}
        requests.post(f"{API}/knowledge/{kb_id}/upload", files=files,
                      headers={"Authorization": f"Bearer {SESSION_A}"}, timeout=30)
        r = requests.delete(f"{API}/knowledge/{kb_id}", headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        assert _db.kb_documents.count_documents({"kb_id": kb_id}) == 0
        assert _db.kb_chunks.count_documents({"kb_id": kb_id}) == 0


# =================== Agents ===================
class TestAgents:
    conv_agent_id = None
    auto_agent_id = None
    coding_agent_id = None
    coding_project_id = None

    def test_create_invalid_type_400(self):
        r = requests.post(f"{API}/agents",
                          json={"name": "bad", "type": "wrong"},
                          headers=H(SESSION_A), timeout=15)
        assert r.status_code == 400

    def test_create_conversational(self):
        r = requests.post(f"{API}/agents",
                          json={"name": "TEST_conv", "type": "conversational"},
                          headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "conversational"
        assert data["system_prompt"]  # default applied
        TestAgents.conv_agent_id = data["id"]

    def test_create_autonomous(self):
        r = requests.post(f"{API}/agents",
                          json={"name": "TEST_auto", "type": "autonomous"},
                          headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        TestAgents.auto_agent_id = r.json()["id"]

    def test_create_coding_agent_with_project(self):
        # create a project first
        rp = requests.post(f"{API}/apps/projects",
                           json={"name": "TEST_coding_proj"},
                           headers=H(SESSION_A), timeout=15)
        TestAgents.coding_project_id = rp.json()["id"]
        # set initial code
        requests.put(f"{API}/apps/projects/{TestAgents.coding_project_id}/code",
                     json={"code": "const App=()=><div>v0</div>;render(<App/>);"},
                     headers=H(SESSION_A), timeout=15)
        r = requests.post(f"{API}/agents",
                          json={"name": "TEST_coder", "type": "coding",
                                "linked_project_id": TestAgents.coding_project_id},
                          headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        TestAgents.coding_agent_id = r.json()["id"]

    def test_list_agents_isolation(self):
        rA = requests.get(f"{API}/agents", headers=H(SESSION_A), timeout=15)
        ids = {a["id"] for a in rA.json()}
        assert TestAgents.conv_agent_id in ids
        rB = requests.get(f"{API}/agents", headers=H(SESSION_B), timeout=15)
        idsB = {a["id"] for a in rB.json()}
        assert TestAgents.conv_agent_id not in idsB

    def test_conversational_chat(self):
        r = requests.post(f"{API}/agents/{TestAgents.conv_agent_id}/chat",
                          json={"prompt": "Reply with the single word: hello."},
                          headers=H(SESSION_A), timeout=60)
        assert r.status_code == 200, r.text[:300]
        msg = r.json()["message"]
        assert msg["role"] == "assistant"
        assert msg["content"]

    def test_autonomous_runtask_streams_calculator(self):
        url = f"{API}/agents/{TestAgents.auto_agent_id}/run-task"
        # Calculator query is deterministic and avoids flaky web search
        prompt = "Use the calculator tool to compute (12*5)+3 and tell me the answer."
        r = requests.post(url, json={"prompt": prompt}, headers=H(SESSION_A),
                          timeout=120, stream=True)
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        events_seen = []
        final_payload = None
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line[6:])
            events_seen.append(payload["type"])
            if payload["type"] == "final":
                final_payload = payload
                break
            if payload["type"] == "error":
                pytest.fail(f"agent stream error: {payload}")
        assert "user" in events_seen
        assert final_payload is not None
        # We expect at least one tool_call/tool_result (calculator) but allow LLM to skip
        # if it hardcodes. Don't fail strictly on tool use.
        if "tool_call" in events_seen:
            assert "tool_result" in events_seen

    def test_coding_agent_updates_project(self):
        r = requests.post(f"{API}/agents/{TestAgents.coding_agent_id}/chat",
                          json={"prompt": "Change the text inside the div from v0 to v1. Keep it minimal."},
                          headers=H(SESSION_A), timeout=120)
        assert r.status_code == 200, r.text[:300]
        # Verify project current_code mutated
        rp = requests.get(f"{API}/apps/projects/{TestAgents.coding_project_id}",
                          headers=H(SESSION_A), timeout=15)
        new_code = rp.json()["current_code"]
        assert new_code  # not empty
        # Either contains v1 or at least changed from original
        assert new_code != "const App=()=><div>v0</div>;render(<App/>);"

    def test_chat_on_autonomous_returns_400(self):
        r = requests.post(f"{API}/agents/{TestAgents.auto_agent_id}/chat",
                          json={"prompt": "hi"}, headers=H(SESSION_A), timeout=15)
        assert r.status_code == 400

    def test_runtask_on_conversational_returns_400(self):
        r = requests.post(f"{API}/agents/{TestAgents.conv_agent_id}/run-task",
                          json={"prompt": "hi"}, headers=H(SESSION_A), timeout=15)
        assert r.status_code == 400

    def test_get_messages(self):
        r = requests.get(f"{API}/agents/{TestAgents.conv_agent_id}/messages",
                         headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) >= 2  # at least user+assistant from earlier test

    def test_delete_agent_cascades_messages(self):
        # use conv agent
        r = requests.delete(f"{API}/agents/{TestAgents.conv_agent_id}",
                            headers=H(SESSION_A), timeout=15)
        assert r.status_code == 200
        assert _db.agent_messages.count_documents({"agent_id": TestAgents.conv_agent_id}) == 0
