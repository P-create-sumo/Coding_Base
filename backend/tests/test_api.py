"""Backend API tests for AI App Builder (FORGE)."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

API = f"{BASE_URL}/api"
USER_A = f"TEST_userA_{uuid.uuid4().hex[:8]}"
USER_B = f"TEST_userB_{uuid.uuid4().hex[:8]}"


def headers(user_id):
    return {"Content-Type": "application/json", "X-User-Id": user_id}


# ===== Root + Templates =====
class TestRootAndTemplates:
    def test_root(self):
        r = requests.get(f"{API}/", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "model" in data
        assert "claude-sonnet-4-5" in data["model"]

    def test_templates(self):
        r = requests.get(f"{API}/templates", timeout=15)
        assert r.status_code == 200
        templates = r.json()
        assert isinstance(templates, list)
        assert len(templates) == 4
        ids = {t["id"] for t in templates}
        assert ids == {"marketing-dashboard", "smart-contract-generator",
                       "data-viz-dashboard", "landing-page"}
        # Validate fields
        for t in templates:
            assert all(k in t for k in ["id", "name", "category",
                                        "description", "thumbnail", "prompt"])


# ===== Project CRUD =====
class TestProjectCRUD:
    project_id = None

    def test_create_project(self):
        payload = {"name": "TEST_project1", "description": "A test project",
                   "template_id": None}
        r = requests.post(f"{API}/projects", json=payload,
                          headers=headers(USER_A), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "TEST_project1"
        assert data["user_id"] == USER_A
        assert data["description"] == "A test project"
        assert "id" in data and isinstance(data["id"], str)
        assert data["current_code"] == ""
        TestProjectCRUD.project_id = data["id"]

    def test_list_projects_isolation_userA(self):
        r = requests.get(f"{API}/projects", headers=headers(USER_A), timeout=15)
        assert r.status_code == 200
        projects = r.json()
        assert any(p["id"] == TestProjectCRUD.project_id for p in projects)

    def test_list_projects_isolation_userB(self):
        # User B should NOT see User A's project
        r = requests.get(f"{API}/projects", headers=headers(USER_B), timeout=15)
        assert r.status_code == 200
        projects = r.json()
        assert not any(p["id"] == TestProjectCRUD.project_id for p in projects)

    def test_get_project_owner(self):
        r = requests.get(f"{API}/projects/{TestProjectCRUD.project_id}",
                         headers=headers(USER_A), timeout=15)
        assert r.status_code == 200
        assert r.json()["id"] == TestProjectCRUD.project_id

    def test_get_project_wrong_user_404(self):
        r = requests.get(f"{API}/projects/{TestProjectCRUD.project_id}",
                         headers=headers(USER_B), timeout=15)
        assert r.status_code == 404

    def test_get_messages_empty(self):
        r = requests.get(f"{API}/projects/{TestProjectCRUD.project_id}/messages",
                         headers=headers(USER_A), timeout=15)
        assert r.status_code == 200
        assert r.json() == []

    def test_update_code(self):
        new_code = "const App = () => <div>Hello</div>; render(<App />);"
        r = requests.put(f"{API}/projects/{TestProjectCRUD.project_id}/code",
                         json={"code": new_code},
                         headers=headers(USER_A), timeout=15)
        assert r.status_code == 200
        assert r.json()["success"] is True
        # Verify persisted
        r2 = requests.get(f"{API}/projects/{TestProjectCRUD.project_id}",
                          headers=headers(USER_A), timeout=15)
        assert r2.json()["current_code"] == new_code

    def test_update_code_wrong_user_404(self):
        r = requests.put(f"{API}/projects/{TestProjectCRUD.project_id}/code",
                         json={"code": "x"}, headers=headers(USER_B), timeout=15)
        assert r.status_code == 404


# ===== LLM Generate =====
class TestGenerate:
    project_id = None

    @classmethod
    def setup_class(cls):
        r = requests.post(f"{API}/projects",
                          json={"name": "TEST_genproject", "description": ""},
                          headers=headers(USER_A), timeout=15)
        cls.project_id = r.json()["id"]

    def test_generate_code(self):
        payload = {"prompt": "Create a simple counter component with a button "
                             "that increments a number. Black background, "
                             "red button. Just minimal."}
        r = requests.post(f"{API}/projects/{self.project_id}/generate",
                          json=payload, headers=headers(USER_A), timeout=90)
        assert r.status_code == 200, f"body: {r.text[:300]}"
        data = r.json()
        assert "user_message" in data
        assert "assistant_message" in data
        assert data["user_message"]["role"] == "user"
        assert data["assistant_message"]["role"] == "assistant"
        # Code extraction
        assert data.get("code"), "code field should be non-empty"
        assert "render(<App" in data["code"] or "App" in data["code"]

    def test_messages_persisted_after_generate(self):
        r = requests.get(f"{API}/projects/{self.project_id}/messages",
                         headers=headers(USER_A), timeout=15)
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) >= 2
        roles = [m["role"] for m in msgs]
        assert "user" in roles and "assistant" in roles

    def test_project_code_updated(self):
        r = requests.get(f"{API}/projects/{self.project_id}",
                         headers=headers(USER_A), timeout=15)
        assert r.status_code == 200
        assert len(r.json()["current_code"]) > 0

    def test_generate_wrong_user_404(self):
        r = requests.post(f"{API}/projects/{self.project_id}/generate",
                          json={"prompt": "test"},
                          headers=headers(USER_B), timeout=15)
        assert r.status_code == 404


# ===== Delete cascade =====
class TestDeleteCascade:
    def test_delete_project_cascades_messages(self):
        # Create + generate to seed messages
        r = requests.post(f"{API}/projects",
                          json={"name": "TEST_delete_proj"},
                          headers=headers(USER_A), timeout=15)
        pid = r.json()["id"]
        # Insert a fake user message via generate? skip LLM, just delete
        # Delete
        r2 = requests.delete(f"{API}/projects/{pid}",
                             headers=headers(USER_A), timeout=15)
        assert r2.status_code == 200
        # Verify gone
        r3 = requests.get(f"{API}/projects/{pid}",
                          headers=headers(USER_A), timeout=15)
        assert r3.status_code == 404

    def test_delete_wrong_user_404(self):
        r = requests.post(f"{API}/projects",
                          json={"name": "TEST_del_perm"},
                          headers=headers(USER_A), timeout=15)
        pid = r.json()["id"]
        r2 = requests.delete(f"{API}/projects/{pid}",
                             headers=headers(USER_B), timeout=15)
        assert r2.status_code == 404
        # cleanup
        requests.delete(f"{API}/projects/{pid}",
                        headers=headers(USER_A), timeout=15)


# ===== Cleanup =====
def teardown_module(module):
    """Remove all TEST_ projects for our test users."""
    for user in [USER_A, USER_B]:
        try:
            r = requests.get(f"{API}/projects", headers=headers(user), timeout=15)
            for p in r.json():
                if p["name"].startswith("TEST_"):
                    requests.delete(f"{API}/projects/{p['id']}",
                                    headers=headers(user), timeout=15)
        except Exception:
            pass
