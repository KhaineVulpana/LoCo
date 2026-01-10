from types import SimpleNamespace

import pytest
from sqlalchemy import text

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


@pytest.mark.asyncio
async def test_retrieve_workspace(fake_vector_store, fake_embedding_manager, async_session_maker):
    workspace_id = "ws-123"
    collection = f"loco_rag_workspace_{workspace_id}"
    fake_vector_store.create_collection(collection, vector_size=fake_embedding_manager.get_dimensions())

    async with async_session_maker() as session:
        await session.execute(text("""
            INSERT INTO files (
                workspace_id, path, content_hash, size_bytes, line_count,
                index_status, created_at, updated_at
            )
            VALUES (
                :workspace_id, :path, :content_hash, :size_bytes, :line_count,
                :index_status, :created_at, :updated_at
            )
        """), {
            "workspace_id": workspace_id,
            "path": "math.py",
            "content_hash": "hash",
            "size_bytes": 10,
            "line_count": 1,
            "index_status": "indexed",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        })
        result = await session.execute(text("""
            SELECT id FROM files WHERE workspace_id = :workspace_id AND path = :path
        """), {"workspace_id": workspace_id, "path": "math.py"})
        file_id = result.fetchone()[0]
        await session.execute(text("""
            INSERT INTO chunks (
                file_id, workspace_id, start_line, end_line, start_offset, end_offset,
                content, content_hash, chunk_type, vector_id, embedding_model, created_at, updated_at
            )
            VALUES (
                :file_id, :workspace_id, :start_line, :end_line, :start_offset, :end_offset,
                :content, :content_hash, :chunk_type, :vector_id, :embedding_model, :created_at, :updated_at
            )
        """), {
            "file_id": file_id,
            "workspace_id": workspace_id,
            "start_line": 0,
            "end_line": 1,
            "start_offset": 0,
            "end_offset": 10,
            "content": "def add(a, b): return a + b",
            "content_hash": "chunk-hash",
            "chunk_type": "heuristic",
            "vector_id": "w1",
            "embedding_model": "fake",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        })
        await session.commit()

    fake_vector_store.upsert_vectors(
        collection,
        [_point("w1", [0.4] * fake_embedding_manager.get_dimensions(), {
            "file_path": "math.py",
            "source": "math.py"
        })]
    )

    retriever = Retriever(
        frontend_id="vscode",
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store,
        db_session_maker=async_session_maker
    )

    results = await retriever.retrieve_workspace("add numbers", workspace_id, limit=1, score_threshold=0.0)
    assert results
    assert results[0].source == "math.py"
    assert "def add" in results[0].content


@pytest.mark.asyncio
async def test_retrieve_workspace_hybrid_uses_vector_results(
    fake_vector_store, fake_embedding_manager, async_session_maker
):
    workspace_id = "ws-hybrid"
    collection = f"loco_rag_workspace_{workspace_id}"
    fake_vector_store.create_collection(collection, vector_size=fake_embedding_manager.get_dimensions())

    async with async_session_maker() as session:
        await session.execute(text("""
            INSERT INTO files (
                workspace_id, path, content_hash, size_bytes, line_count,
                index_status, created_at, updated_at
            )
            VALUES (
                :workspace_id, :path, :content_hash, :size_bytes, :line_count,
                :index_status, :created_at, :updated_at
            )
        """), {
            "workspace_id": workspace_id,
            "path": "calc.py",
            "content_hash": "hash",
            "size_bytes": 10,
            "line_count": 1,
            "index_status": "indexed",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        })
        result = await session.execute(text("""
            SELECT id FROM files WHERE workspace_id = :workspace_id AND path = :path
        """), {"workspace_id": workspace_id, "path": "calc.py"})
        file_id = result.fetchone()[0]
        await session.execute(text("""
            INSERT INTO chunks (
                file_id, workspace_id, start_line, end_line, start_offset, end_offset,
                content, content_hash, chunk_type, vector_id, embedding_model, created_at, updated_at
            )
            VALUES (
                :file_id, :workspace_id, :start_line, :end_line, :start_offset, :end_offset,
                :content, :content_hash, :chunk_type, :vector_id, :embedding_model, :created_at, :updated_at
            )
        """), {
            "file_id": file_id,
            "workspace_id": workspace_id,
            "start_line": 0,
            "end_line": 1,
            "start_offset": 0,
            "end_offset": 10,
            "content": "def sub(a, b): return a - b",
            "content_hash": "chunk-hash",
            "chunk_type": "heuristic",
            "vector_id": "h1",
            "embedding_model": "fake",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        })
        await session.commit()

    fake_vector_store.upsert_vectors(
        collection,
        [_point("h1", [0.4] * fake_embedding_manager.get_dimensions(), {
            "file_path": "calc.py",
            "source": "calc.py"
        })]
    )

    retriever = Retriever(
        frontend_id="vscode",
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store,
        db_session_maker=async_session_maker
    )

    results = await retriever.retrieve_workspace_hybrid("subtract numbers", workspace_id, limit=1, score_threshold=0.0)
    assert results
    assert results[0].source == "calc.py"
