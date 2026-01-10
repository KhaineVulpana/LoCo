from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import ace
from app.core.runtime import get_embedding_manager, get_vector_store


def create_app(fake_embedding_manager, fake_vector_store) -> FastAPI:
    app = FastAPI()
    app.include_router(ace.router, prefix="/v1/ace")
    app.dependency_overrides[get_embedding_manager] = lambda: fake_embedding_manager
    app.dependency_overrides[get_vector_store] = lambda: fake_vector_store
    return app


def test_ace_bullet_lifecycle(fake_embedding_manager, fake_vector_store):
    app = create_app(fake_embedding_manager, fake_vector_store)
    client = TestClient(app)

    create_resp = client.post("/v1/ace/3d-gen/bullets", json={
        "section": "strategies_and_hard_rules",
        "content": "Keep meshes under 500 triangles.",
        "metadata": {"source": "test"}
    })
    assert create_resp.status_code == 200
    bullet = create_resp.json()["bullet"]
    bullet_id = bullet["id"]

    list_resp = client.get("/v1/ace/3d-gen/bullets")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["bullets"]) == 1

    retrieve_resp = client.post("/v1/ace/3d-gen/retrieve", json={
        "query": "triangles",
        "limit": 1,
        "score_threshold": 0.0
    })
    assert retrieve_resp.status_code == 200
    assert retrieve_resp.json()["results"]

    feedback_resp = client.post("/v1/ace/3d-gen/feedback", json={
        "feedback": [{"bullet_id": bullet_id, "tag": "helpful"}]
    })
    assert feedback_resp.status_code == 200

    list_resp = client.get("/v1/ace/3d-gen/bullets")
    updated = list_resp.json()["bullets"][0]
    assert updated["helpful_count"] == 1

    delete_resp = client.delete(f"/v1/ace/3d-gen/bullets/{bullet_id}")
    assert delete_resp.status_code == 200

    list_resp = client.get("/v1/ace/3d-gen/bullets")
    assert list_resp.json()["bullets"] == []


def test_ace_metrics(fake_embedding_manager, fake_vector_store):
    app = create_app(fake_embedding_manager, fake_vector_store)
    client = TestClient(app)

    create_resp = client.post("/v1/ace/3d-gen/bullets", json={
        "section": "strategies_and_hard_rules",
        "content": "Keep meshes under 500 triangles."
    })
    assert create_resp.status_code == 200

    metrics_resp = client.get("/v1/ace/3d-gen/metrics")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()

    assert metrics["total_bullets"] == 1
    assert metrics["sections"]["strategies_and_hard_rules"] == 1
    assert metrics["helpful_total"] == 0
    assert metrics["harmful_total"] == 0
    assert metrics["average_score"] == 0.5
    assert metrics["collection"]["points_count"] == 1
