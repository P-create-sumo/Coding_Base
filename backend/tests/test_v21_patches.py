"""FORGE v2.1 hardening patch tests:
   1. tool_calculator AST sandbox + exponent bounds
   2. linked_project_id + knowledge_base_id validation at agent creation
   3. SSE streaming /agents/{id}/chat-stream (conversational + coding)
   4. Hybrid BM25 + LLM rerank /knowledge/{kb_id}/search-hybrid
   5. Web search graceful fallback (no API key)
"""
import os
import io
import sys
import time
import json
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

# Make the agents_router tool_calculator importable for direct unit tests
sys.path.insert(0, "/app/backend")

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
USER_A = f"TEST_v21_userA_{TS}"
USER_B = f"TEST_v21_userB_{TS}"
SESS_A = f"TEST_v21_session_A_{TS}"
SESS_B = f"TEST_v21_session_B_{TS}"


def _seed():
    now = datetime.now(timezone.utc).isoformat()
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    _db.users.insert_many([
        {"user_id": USER_A, "email": f"v21A_{TS}@example.com", "name": "V21 A",
         "picture": None, "created_at": now},
        {"user_id": USER_B, "email": f"v21B_{TS}@example.com", "name": "V21 B",
         "picture": None, "created_at": now},
    ])
    _db.user_sessions.insert_many([
        {"user_id": USER_A, "session_token": SESS_A, "expires_at": expires, "created_at": now},
        {"user_id": USER_B, "session_token": SESS_B, "expires_at": expires, "created_at": now},
    ])


def _cleanup():
    for u in [USER_A, USER_B]:
        _db.users.delete_many({"user_id": u})
        _db.projects.delete_many({"user_id": u})
        _db.knowledge_bases.delete_many({"user_id": u})
        _db.kb_documents.delete_many({"user_id": u})
        _db.kb_chunks.delete_many({"user_id": u})
        _db.agents.delete_many({"user_id": u})
    _db.user_sessions.delete_many({"session_token": {"$in": [SESS_A, SESS_B]}})


def setup_module(module):
    _cleanup()
    _seed()


def teardown_module(module):
    _cleanup()


def H(t):
    return {"Content-Type": "application/json", "Authorization": f"Bearer {t}"}


# ============== 1. tool_calculator (direct unit test) ==============
class TestCalculatorSandbox:
    def setup_class(cls):
        from agents_router import tool_calculator
        cls.calc = staticmethod(tool_calculator)

    def test_basic_addition(self):
        assert TestCalculatorSandbox.calc("2+2") == "4"

    def test_basic_multiplication(self):
        assert TestCalculatorSandbox.calc("(12*5)/3") == "20.0"

    def test_caret_to_pow_small(self):
        assert TestCalculatorSandbox.calc("9^9") == "387420489"

    def test_double_caret_too_large(self):
        # 9^9^9 → exponent is 9^9=387M which exceeds bound (>100)
        out = TestCalculatorSandbox.calc("9^9^9")
        assert "Exponent too large" in out or "Calc error" in out

    def test_huge_left_pow(self):
        # 1e7 ** 10 → left>1e6
        out = TestCalculatorSandbox.calc("10000000**10")
        assert "Calc error" in out

    def test_no_code_execution_dunder(self):
        out = TestCalculatorSandbox.calc("__import__('os').system('echo pwned')")
        assert "Calc error" in out
        assert "pwned" not in out

    def test_no_function_call(self):
        out = TestCalculatorSandbox.calc("abs(-5)")
        # abs would be a Call node which is rejected
        assert "Calc error" in out

    def test_empty_expression(self):
        out = TestCalculatorSandbox.calc("")
        assert "Error" in out

    def test_unary_minus(self):
        assert TestCalculatorSandbox.calc("-5+10") == "5"


# ============== 2. coding agent linked_project_id validation ==============
class TestAgentValidation:
    project_id = None
    other_user_project_id = None

    def test_coding_no_project_400(self):
        r = requests.post(f"{API}/agents",
                          json={"name": "TEST_v21_no_proj", "type": "coding"},
                          headers=H(SESS_A), timeout=15)
        assert r.status_code == 400
        assert "linked_project_id" in r.json()["detail"]

    def test_coding_bogus_project_400(self):
        r = requests.post(f"{API}/agents",
                          json={"name": "TEST_v21_bogus", "type": "coding",
                                "linked_project_id": "does-not-exist-xyz"},
                          headers=H(SESS_A), timeout=15)
        assert r.status_code == 400
        assert "does not exist" in r.json()["detail"].lower() or "linked_project_id" in r.json()["detail"]

    def test_coding_other_users_project_400(self):
        # B creates a project; A tries to link to it
        rb = requests.post(f"{API}/apps/projects",
                           json={"name": "TEST_v21_B_proj"},
                           headers=H(SESS_B), timeout=15)
        assert rb.status_code == 200
        TestAgentValidation.other_user_project_id = rb.json()["id"]

        r = requests.post(f"{API}/agents",
                          json={"name": "TEST_v21_xuser", "type": "coding",
                                "linked_project_id": TestAgentValidation.other_user_project_id},
                          headers=H(SESS_A), timeout=15)
        assert r.status_code == 400

    def test_coding_real_project_succeeds(self):
        rp = requests.post(f"{API}/apps/projects",
                           json={"name": "TEST_v21_A_proj"},
                           headers=H(SESS_A), timeout=15)
        TestAgentValidation.project_id = rp.json()["id"]
        requests.put(f"{API}/apps/projects/{TestAgentValidation.project_id}/code",
                     json={"code": "const App=()=><div>hi v21</div>;render(<App/>);"},
                     headers=H(SESS_A), timeout=15)

        r = requests.post(f"{API}/agents",
                          json={"name": "TEST_v21_real", "type": "coding",
                                "linked_project_id": TestAgentValidation.project_id},
                          headers=H(SESS_A), timeout=15)
        assert r.status_code == 200, r.text[:300]

    def test_bogus_kb_id_400(self):
        r = requests.post(f"{API}/agents",
                          json={"name": "TEST_v21_bad_kb", "type": "conversational",
                                "knowledge_base_id": "kb-does-not-exist"},
                          headers=H(SESS_A), timeout=15)
        assert r.status_code == 400


# ============== 3. /chat-stream SSE endpoint ==============
class TestChatStream:
    conv_id = None
    coding_id = None
    auto_id = None
    proj_id = None

    def test_setup_agents(self):
        rc = requests.post(f"{API}/agents",
                           json={"name": "TEST_v21_stream_conv", "type": "conversational"},
                           headers=H(SESS_A), timeout=15)
        TestChatStream.conv_id = rc.json()["id"]

        ra = requests.post(f"{API}/agents",
                           json={"name": "TEST_v21_stream_auto", "type": "autonomous"},
                           headers=H(SESS_A), timeout=15)
        TestChatStream.auto_id = ra.json()["id"]

        rp = requests.post(f"{API}/apps/projects",
                           json={"name": "TEST_v21_stream_proj"},
                           headers=H(SESS_A), timeout=15)
        TestChatStream.proj_id = rp.json()["id"]
        requests.put(f"{API}/apps/projects/{TestChatStream.proj_id}/code",
                     json={"code": "const App=()=><div>v0</div>;render(<App/>);"},
                     headers=H(SESS_A), timeout=15)
        rcd = requests.post(f"{API}/agents",
                            json={"name": "TEST_v21_stream_code", "type": "coding",
                                  "linked_project_id": TestChatStream.proj_id},
                            headers=H(SESS_A), timeout=15)
        TestChatStream.coding_id = rcd.json()["id"]

    def _read_sse(self, r):
        events = []
        chunk_count = 0
        final = None
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line[6:])
            t = payload.get("type")
            events.append(t)
            if t == "chunk":
                chunk_count += 1
            elif t == "done":
                final = payload
                break
            elif t == "error":
                pytest.fail(f"SSE error: {payload}")
        return events, chunk_count, final

    def test_conversational_stream(self):
        r = requests.post(f"{API}/agents/{TestChatStream.conv_id}/chat-stream",
                          json={"prompt": "Reply with the single word: pong."},
                          headers=H(SESS_A), timeout=120, stream=True)
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        events, chunk_count, final = self._read_sse(r)
        assert "user" in events
        assert chunk_count > 0, f"expected streaming chunks, got events={events}"
        assert final is not None
        assert final["message"]["role"] == "assistant"
        assert final["message"]["content"]

    def test_coding_stream_updates_project(self):
        r = requests.post(f"{API}/agents/{TestChatStream.coding_id}/chat-stream",
                          json={"prompt": "Change the text inside the div from v0 to v2. Output only the file."},
                          headers=H(SESS_A), timeout=120, stream=True)
        assert r.status_code == 200
        events, chunk_count, final = self._read_sse(r)
        assert "user" in events
        assert chunk_count > 0
        assert final is not None
        # Verify project current_code mutated
        rp = requests.get(f"{API}/apps/projects/{TestChatStream.proj_id}",
                          headers=H(SESS_A), timeout=15)
        new_code = rp.json()["current_code"]
        assert new_code != "const App=()=><div>v0</div>;render(<App/>);"

    def test_autonomous_stream_400(self):
        r = requests.post(f"{API}/agents/{TestChatStream.auto_id}/chat-stream",
                          json={"prompt": "hi"}, headers=H(SESS_A), timeout=15)
        assert r.status_code == 400

    def test_chat_stream_unknown_agent_404(self):
        r = requests.post(f"{API}/agents/no-such-agent/chat-stream",
                          json={"prompt": "hi"}, headers=H(SESS_A), timeout=15)
        assert r.status_code == 404


# ============== 4. Hybrid rerank search ==============
class TestHybridSearch:
    kb_id = None

    def test_setup_kb(self):
        r = requests.post(f"{API}/knowledge",
                          json={"name": "TEST_v21_kb", "description": "v21 hybrid"},
                          headers=H(SESS_A), timeout=15)
        TestHybridSearch.kb_id = r.json()["id"]

        # Upload a doc with multiple distinct topics so reranker has work to do
        text = (
            "Photosynthesis is the process by which plants use sunlight, water and "
            "carbon dioxide to create oxygen and energy in the form of sugar. "
            "Mitochondria are the powerhouse of the cell and produce ATP through "
            "cellular respiration. The capital of France is Paris and it is located "
            "on the Seine river. Python is a high-level programming language created "
            "by Guido van Rossum. The Eiffel Tower in Paris attracts millions of "
            "tourists every year. Quantum entanglement is a phenomenon in quantum "
            "physics where particles remain connected. The mitochondrial DNA is "
            "inherited from the mother. Photosynthesis occurs in chloroplasts." * 3
        )
        files = {"file": ("v21_hybrid.txt", io.BytesIO(text.encode()), "text/plain")}
        rh = {"Authorization": f"Bearer {SESS_A}"}
        ru = requests.post(f"{API}/knowledge/{TestHybridSearch.kb_id}/upload",
                           files=files, headers=rh, timeout=30)
        assert ru.status_code == 200, ru.text[:200]

    def test_hybrid_search_paris(self):
        r = requests.post(f"{API}/knowledge/{TestHybridSearch.kb_id}/search-hybrid",
                          json={"query": "Where is the Eiffel Tower located?", "top_k": 3},
                          headers=H(SESS_A), timeout=60)
        assert r.status_code == 200, r.text[:300]
        results = r.json()["results"]
        assert isinstance(results, list)
        assert len(results) > 0
        joined = " ".join([c["content"] for c in results]).lower()
        assert "paris" in joined or "eiffel" in joined

    def test_hybrid_search_returns_topk_or_less(self):
        r = requests.post(f"{API}/knowledge/{TestHybridSearch.kb_id}/search-hybrid",
                          json={"query": "photosynthesis chloroplasts", "top_k": 2},
                          headers=H(SESS_A), timeout=60)
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) <= 2


# ============== 5. web_search tool graceful behaviour ==============
class TestWebSearchTool:
    def test_returns_string(self):
        import asyncio
        from agents_router import tool_web_search
        out = asyncio.run(tool_web_search("python language"))
        assert isinstance(out, str)
        assert len(out) > 0
