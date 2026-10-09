def new_task(client, **overrides):
    payload = {"title": "Deploy application", "priority": "HIGH", "assignee": "Student"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload)


def test_health(client):
    assert client.get("/health").json() == {"status": "UP"}


def test_ready(client):
    assert client.get("/ready").json() == {"status": "READY"}


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "TaskBoard API"


def test_create_task_validation(client):
    response = new_task(client)
    assert response.status_code == 201
    assert response.json()["title"] == "Deploy application"


def test_create_task_rejects_empty_title(client):
    assert new_task(client, title="").status_code == 422


def test_create_task_rejects_unknown_priority(client):
    assert new_task(client, priority="URGENT").status_code == 422


def test_list_and_get_task(client):
    created = new_task(client).json()
    tasks = client.get("/api/tasks").json()
    assert [t["id"] for t in tasks] == [created["id"]]
    assert client.get(f"/api/tasks/{created['id']}").json()["assignee"] == "Student"


def test_get_missing_task_returns_404(client):
    response = client.get("/api/tasks/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_update_task_status(client):
    created = new_task(client).json()
    response = client.put(f"/api/tasks/{created['id']}", json={"status": "DONE"})
    assert response.status_code == 200
    assert response.json()["status"] == "DONE"
    assert response.json()["title"] == "Deploy application"


def test_delete_task(client):
    created = new_task(client).json()
    assert client.delete(f"/api/tasks/{created['id']}").status_code == 204
    assert client.get(f"/api/tasks/{created['id']}").status_code == 404


def test_stats_counts_by_status(client):
    new_task(client, status="TODO")
    new_task(client, status="IN_PROGRESS")
    new_task(client, status="DONE")
    new_task(client, status="DONE")
    assert client.get("/api/tasks/stats").json() == {"total": 4, "todo": 1, "inProgress": 1, "done": 2}


def test_metrics_endpoint(client):
    client.get("/health")
    body = client.get("/metrics").text
    assert "http_requests_total" in body
