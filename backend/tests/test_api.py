"""基础 API 测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data


def test_create_project():
    resp = client.post("/api/v1/projects/", json={
        "name": "测试招标项目",
        "project_code": "ZB-2026-001",
        "description": "自动化测试项目"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "测试招标项目"
    assert data["status"] == "created"
    return data["id"]


def test_list_projects():
    resp = client.get("/api/v1/projects/")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


def test_docs_endpoint():
    """先创建项目，再查看其文档列表"""
    resp = client.post("/api/v1/projects/", json={
        "name": "文档测试项目",
        "project_code": "ZB-2026-002",
    })
    assert resp.status_code == 200
    project_id = resp.json()["id"]

    resp = client.get(f"/api/v1/documents/project/{project_id}")
    assert resp.status_code == 200


def test_risk_dashboard():
    resp = client.get("/api/v1/risk/dashboard")
    assert resp.status_code in (200, 404)
