from types import SimpleNamespace

import pytest

from app.retrieval.retriever import Retriever


def _point(point_id, vector, payload):
    return SimpleNamespace(id=point_id, vector=vector, payload=payload)


@pytest.mark.asyncio
async def test_retrieve_knowledge(fake_vector_store, fake_embedding_manager):
    collection = "loco_rag_3d-gen"
    fake_vector_store.create_collection(collection, vector_size=fake_embedding_manager.get_dimensions())

    fake_vector_store.upsert_vectors(
        collection,
        [_point("p1", [0.1] * fake_embedding_manager.get_dimensions(), {
            "content": "Prompt: Build a tower",
            "source": "tower.jsonl"
        })]
    )

    retriever = Retriever(
        frontend_id="3d-gen",
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store
    )

    results = await retriever.retrieve("Build a tower", limit=1, score_threshold=0.0)
    assert results
    assert results[0].source == "tower.jsonl"


@pytest.mark.asyncio
async def test_retrieve_ace_bullets(fake_vector_store, fake_embedding_manager):
    collection = "loco_ace_3d-gen"
    fake_vector_store.create_collection(collection, vector_size=fake_embedding_manager.get_dimensions())

    fake_vector_store.upsert_vectors(
        collection,
        [_point("bullet-1", [0.2] * fake_embedding_manager.get_dimensions(), {
            "content": "Low-poly mesh means fewer than 500 triangles.",
            "section": "strategies_and_hard_rules",
            "bullet_id": "bullet-1"
        })]
    )

    retriever = Retriever(
        frontend_id="3d-gen",
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store
    )

    results = await retriever.retrieve_ace_bullets("low poly", limit=1, score_threshold=0.0)
    assert results
    assert "low-poly" in results[0].content.lower()
