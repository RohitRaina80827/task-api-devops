from fastapi.testclient import TestClient

from app.main import app, tasks

client = TestClient(app)

def setup_function(): tasks.clear()

def test_health_and_version():
    assert client.get("/health/live").json() == {"status": "BROKEN"}
    assert client.get("/health/ready").status_code == 200
    assert "git_commit" in client.get("/version").json()

def test_task_lifecycle():
    created = client.post("/tasks", json={"title":"Check backup","priority":"high"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert client.get(f"/tasks/{task_id}").json()["title"] == "Check backup"
    updated = client.patch(f"/tasks/{task_id}", json={"completed":True})
    assert updated.json()["completed"] is True
    assert client.delete(f"/tasks/{task_id}").status_code == 204
    assert client.get(f"/tasks/{task_id}").status_code == 404

def test_validation_rejects_blank_title():
    assert client.post("/tasks", json={"title":""}).status_code == 422

def test_metrics_available():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
