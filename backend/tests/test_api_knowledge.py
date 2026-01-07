import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import knowledge
from app.main import get_embedding_manager, get_vector_store


def create_app(fake_embedding_manager, fake_vector_store) -> FastAPI:
    app = FastAPI()
    app.include_router(knowledge.router, prefix="/v1/knowledge")
    app.dependency_overrides[get_embedding_manager] = lambda: fake_embedding_manager
    app.dependency_overrides[get_vector_store] = lambda: fake_vector_store
    return app


def test_index_training_and_retrieve(fake_embedding_manager, fake_vector_store, tmp_path):
    jsonl_path = tmp_path / "training.jsonl"
    jsonl_path.write_text(
        json.dumps({
            "instruction": "Write Unity C# code to generate a cube",
            "input": "Requirements: Category=props",
            "output": "public class CubeMesh {}"
        }) + "\n",
        encoding="utf-8"
    )

    app = create_app(fake_embedding_manager, fake_vector_store)
    client = TestClient(app)

    index_resp = client.post("/v1/knowledge/3d-gen/index-training", json={
        "jsonl_path": str(jsonl_path)
    })
    assert index_resp.status_code == 200
    assert index_resp.json()["stats"]["indexed"] == 1

    retrieve_resp = client.post("/v1/knowledge/3d-gen/retrieve", json={
        "query": "generate a cube",
        "limit": 3,
        "score_threshold": 0.0
    })
    assert retrieve_resp.status_code == 200
    results = retrieve_resp.json()["results"]
    assert results
    assert "cube" in results[0]["content"].lower()
