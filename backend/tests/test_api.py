"""Backend API tests for FORGE AI App Builder (auth-protected v2).

Seeds two test users + sessions directly into MongoDB and uses
`Authorization: Bearer <session_token>` for all API calls.
"""
import os
import time
import uuid
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

# Direct mongo for seeding
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]

TS = int(time.time() * 1000)
USER_A_ID = f"TEST_userA_{TS}"
USER_B_ID = f"TEST_userB_{TS}"
SESSION_A = f"TEST_session_A_{TS}"
SESSION_B = f"TEST_session_B_{TS}"
LEGACY_USER_ID = f"TEST_legacy_{TS}"


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
    _db.projects.delete_many({"user_id": {"$in": [USER_A_ID, USER_B_ID, LEGACY_USER_ID]}})


def setup_module(module):
    _cleanup()
    _seed()


def teardown_module(module):
    _cleanup()


def headers(token):
    return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}


# ===== Root / Templates =====
class TestRoot:
    def test_root(self):
        r = requests.get(f"{API}/", timeout=15)
        assert r.status_code == 200
        assert "claude-sonnet-4-5" in r.json()["model"]

    def test_templates(self):
        r = requests.get(f"{API}/templates", timeout=15)
        assert r.status_code == 200
        assert len(r.json()) == 4


# ===== Auth =====
class TestAuth:
    def test_me_no_token_401(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401

    def test_me_invalid_token_401(self):
        r = requests.get(f"{API}/auth/me",
                         headers={"Authorization": "Bearer bad_token_xyz"}, timeout=15)
        assert r.status_code == 401

    def test_me_valid_token(self):
        r = requests.get(f"{API}/auth/me", headers=headers(SESSION_A), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == USER_A_ID
        assert data["email"].startswith("test.user.A.")

    def test_projects_requires_auth(self):
        r = requests.get(f"{API}/projects", timeout=15)
        assert r.status_code == 401

    def test_logout_then_session_invalidated(self):
        # Create an extra session for user A so we can test logout
        token = f"TEST_logout_session_{TS}"
        _db.user_sessions.insert_one({
            "user_id": USER_A_ID, "session_token": token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Logout
        r = requests.post(f"{API}/auth/logout", headers=headers(token), timeout=15)
        assert r.status_code == 200
        # Session should now be deleted
        r2 = requests.get(f"{API}/auth/me", headers=headers(token), timeout=15)
        assert r2.status_code == 401

    def test_migrate_legacy_projects(self):
        # Create a project under legacy user_id directly in DB
        legacy_pid = f"TEST_legacy_proj_{uuid.uuid4().hex[:8]}"
        _db.projects.insert_one({
            "id": legacy_pid, "user_id": LEGACY_USER_ID, "name": "TEST_legacy",
            "description": "", "current_code": "", "files": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        r = requests.post(f"{API}/auth/migrate",
                          json={"legacy_user_id": LEGACY_USER_ID},
                          headers=headers(SESSION_A), timeout=15)
        assert r.status_code == 200
        assert r.json()["migrated"] == 1
        # Verify project now belongs to user A
        r2 = requests.get(f"{API}/projects/{legacy_pid}",
                          headers=headers(SESSION_A), timeout=15)
        assert r2.status_code == 200
        # Cleanup
        requests.delete(f"{API}/projects/{legacy_pid}",
                        headers=headers(SESSION_A), timeout=15)


# ===== Project CRUD + Isolation =====
class TestProjectCRUD:
    project_id = None

    def test_create_project(self):
        r = requests.post(f"{API}/projects",
                          json={"name": "TEST_project1", "description": "Test"},
                          headers=headers(SESSION_A), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "TEST_project1"
        assert data["user_id"] == USER_A_ID
        TestProjectCRUD.project_id = data["id"]

    def test_list_isolation(self):
        # User A sees their project
        rA = requests.get(f"{API}/projects", headers=headers(SESSION_A), timeout=15)
        assert any(p["id"] == TestProjectCRUD.project_id for p in rA.json())
        # User B doesn't
        rB = requests.get(f"{API}/projects", headers=headers(SESSION_B), timeout=15)
        assert not any(p["id"] == TestProjectCRUD.project_id for p in rB.json())

    def test_get_wrong_user_404(self):
        r = requests.get(f"{API}/projects/{TestProjectCRUD.project_id}",
                         headers=headers(SESSION_B), timeout=15)
        assert r.status_code == 404

    def test_update_code_default_path(self):
        new_code = "const App=()=><div>Hi</div>;render(<App/>);"
        r = requests.put(f"{API}/projects/{TestProjectCRUD.project_id}/code",
                         json={"code": new_code}, headers=headers(SESSION_A), timeout=15)
        assert r.status_code == 200
        # Verify
        r2 = requests.get(f"{API}/projects/{TestProjectCRUD.project_id}",
                          headers=headers(SESSION_A), timeout=15)
        assert r2.json()["current_code"] == new_code
        # files array updated with App.jsx
        files = r2.json()["files"]
        assert any(f["path"] == "App.jsx" and f["content"] == new_code for f in files)

    def test_update_code_specific_path(self):
        r = requests.put(f"{API}/projects/{TestProjectCRUD.project_id}/code",
                         json={"code": "# Hello", "path": "README.md"},
                         headers=headers(SESSION_A), timeout=15)
        assert r.status_code == 200
        r2 = requests.get(f"{API}/projects/{TestProjectCRUD.project_id}",
                          headers=headers(SESSION_A), timeout=15)
        files = r2.json()["files"]
        assert any(f["path"] == "README.md" and f["content"] == "# Hello" for f in files)


# ===== LLM Generate (non-stream + stream) =====
class TestGenerate:
    project_id = None

    @classmethod
    def setup_class(cls):
        r = requests.post(f"{API}/projects",
                          json={"name": "TEST_gen", "description": ""},
                          headers=headers(SESSION_A), timeout=15)
        cls.project_id = r.json()["id"]

    def test_generate_non_stream(self):
        r = requests.post(f"{API}/projects/{self.project_id}/generate",
                          json={"prompt": "Create a tiny counter button. Minimal."},
                          headers=headers(SESSION_A), timeout=120)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["assistant_message"]["role"] == "assistant"
        assert data.get("code"), "code field empty"
        # Files parsed
        assert isinstance(data.get("files"), list)

    def test_versions_after_generate(self):
        r = requests.get(f"{API}/projects/{self.project_id}/versions",
                         headers=headers(SESSION_A), timeout=15)
        assert r.status_code == 200
        versions = r.json()
        # First generation may or may not have multi-file files; if files were parsed, version exists
        # We ran one generate above
        assert isinstance(versions, list)

    def test_generate_stream(self):
        url = f"{API}/projects/{self.project_id}/generate-stream"
        r = requests.post(url, json={"prompt": "Add a reset button to the counter."},
                          headers=headers(SESSION_A), timeout=120, stream=True)
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        events = []
        chunks_seen = 0
        done_payload = None
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            import json as _j
            payload = _j.loads(line[6:])
            events.append(payload["type"])
            if payload["type"] == "chunk":
                chunks_seen += 1
            elif payload["type"] == "done":
                done_payload = payload
                break
            elif payload["type"] == "error":
                pytest.fail(f"Stream error: {payload}")
        assert "user" in events, f"events: {events}"
        assert chunks_seen > 0, f"no chunks; events: {events}"
        assert done_payload is not None
        assert "assistant_message" in done_payload
        assert "files" in done_payload

    def test_generate_unauthorized_user_404(self):
        r = requests.post(f"{API}/projects/{self.project_id}/generate",
                          json={"prompt": "x"}, headers=headers(SESSION_B), timeout=30)
        assert r.status_code == 404


# ===== Versions / Rollback =====
class TestVersions:
    project_id = None

    @classmethod
    def setup_class(cls):
        # Create a project + seed two versions directly
        r = requests.post(f"{API}/projects",
                          json={"name": "TEST_versions"},
                          headers=headers(SESSION_A), timeout=15)
        cls.project_id = r.json()["id"]
        # Insert 2 fake versions directly into DB
        for i, code in enumerate(["v1_code", "v2_code"]):
            _db.versions.insert_one({
                "id": f"TEST_ver_{TS}_{i}",
                "project_id": cls.project_id,
                "user_id": USER_A_ID,
                "prompt": f"prompt v{i}",
                "files": [{"path": "App.jsx", "content": code}],
                "current_code": code,
                "created_at": (datetime.now(timezone.utc) + timedelta(seconds=i)).isoformat(),
            })

    def test_list_versions_sorted_desc(self):
        r = requests.get(f"{API}/projects/{self.project_id}/versions",
                         headers=headers(SESSION_A), timeout=15)
        assert r.status_code == 200
        vs = r.json()
        assert len(vs) >= 2
        # Newest first
        assert vs[0]["created_at"] >= vs[-1]["created_at"]

    def test_versions_isolation(self):
        r = requests.get(f"{API}/projects/{self.project_id}/versions",
                         headers=headers(SESSION_B), timeout=15)
        assert r.status_code == 404

    def test_rollback(self):
        target_id = f"TEST_ver_{TS}_0"  # rollback to v1_code
        r = requests.post(f"{API}/projects/{self.project_id}/rollback/{target_id}",
                          headers=headers(SESSION_A), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["current_code"] == "v1_code"
        # Verify project reflects rollback
        r2 = requests.get(f"{API}/projects/{self.project_id}",
                          headers=headers(SESSION_A), timeout=15)
        assert r2.json()["current_code"] == "v1_code"

    def test_rollback_invalid_version(self):
        r = requests.post(f"{API}/projects/{self.project_id}/rollback/nonexistent",
                          headers=headers(SESSION_A), timeout=15)
        assert r.status_code == 404


# ===== Multi-file parsing helpers (unit-style via API) =====
class TestMultiFileExportAndPath:
    project_id = None

    @classmethod
    def setup_class(cls):
        r = requests.post(f"{API}/projects",
                          json={"name": "TEST_export"},
                          headers=headers(SESSION_A), timeout=15)
        cls.project_id = r.json()["id"]
        # Set files via direct PUT calls
        app_code = ("const App = () => <div className='p-4'>Hello</div>;\n"
                    "render(<App />);")
        readme = "# Demo\nGenerated."
        requests.put(f"{API}/projects/{cls.project_id}/code",
                     json={"code": app_code}, headers=headers(SESSION_A), timeout=15)
        requests.put(f"{API}/projects/{cls.project_id}/code",
                     json={"code": readme, "path": "README.md"},
                     headers=headers(SESSION_A), timeout=15)

    def test_export_zip_structure(self):
        r = requests.get(f"{API}/projects/{self.project_id}/export",
                         headers=headers(SESSION_A), timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/zip"
        import io as _io, zipfile as _zf
        zf = _zf.ZipFile(_io.BytesIO(r.content))
        names = zf.namelist()
        # At least 1 root folder
        roots = {n.split("/")[0] for n in names}
        assert len(roots) == 1
        root = list(roots)[0]
        expected = {
            f"{root}/package.json",
            f"{root}/index.html",
            f"{root}/vite.config.js",
            f"{root}/src/main.jsx",
            f"{root}/README.md",
            f"{root}/src/App.jsx",
        }
        missing = expected - set(names)
        assert not missing, f"missing: {missing}"

        # Validate package.json is valid JSON (no .format() leftover)
        import json as _j
        pkg = _j.loads(zf.read(f"{root}/package.json").decode())
        assert pkg["name"]
        assert "react" in pkg["dependencies"]

        # App.jsx adapted: import React + export default
        app_content = zf.read(f"{root}/src/App.jsx").decode()
        assert "import React" in app_content
        assert "export default App" in app_content
        assert "render(<App" not in app_content  # render() removed

    def test_export_unauthorized_404(self):
        r = requests.get(f"{API}/projects/{self.project_id}/export",
                         headers=headers(SESSION_B), timeout=15)
        assert r.status_code == 404


# ===== Delete cascade =====
class TestDeleteCascade:
    def test_delete_cascades(self):
        r = requests.post(f"{API}/projects",
                          json={"name": "TEST_delete"},
                          headers=headers(SESSION_A), timeout=15)
        pid = r.json()["id"]
        # Add a fake version
        _db.versions.insert_one({
            "id": f"TEST_delver_{TS}", "project_id": pid, "user_id": USER_A_ID,
            "prompt": "x", "files": [], "current_code": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        r2 = requests.delete(f"{API}/projects/{pid}",
                             headers=headers(SESSION_A), timeout=15)
        assert r2.status_code == 200
        # Versions should be deleted
        assert _db.versions.find_one({"project_id": pid}) is None
        # Project gone
        r3 = requests.get(f"{API}/projects/{pid}",
                          headers=headers(SESSION_A), timeout=15)
        assert r3.status_code == 404
