import json

import pytest

from app.indexing.domain_indexer import KnowledgeIndexer


@pytest.mark.asyncio
async def test_index_training_data_accepts_instruction_format(
    tmp_path, fake_embedding_manager, fake_vector_store
):
    jsonl_path = tmp_path / "training.jsonl"
    jsonl_path.write_text(
        json.dumps({
            "instruction": "Write Unity C# code to Generate a cube",
            "input": "Requirements: Category=props, Complexity=easy",
            "output": "public class CubeMesh {}",
            "category": "props",
            "complexity": "easy",
            "asset_type": "cube",
            "metadata": {"mesh_approach": "box"}
        }) + "\n",
        encoding="utf-8"
    )

    indexer = KnowledgeIndexer(
        module_id="3d-gen",
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store
    )

    stats = await indexer.index_training_data(str(jsonl_path))
    assert stats["indexed"] == 1

    collection = "loco_rag_3d-gen"
    info = fake_vector_store.get_collection_info(collection)
    assert info["points_count"] == 1

    stored = next(iter(fake_vector_store.collections[collection].values()))
    assert stored.payload["instruction"].startswith("Write Unity C# code")
    assert stored.payload["input"].startswith("Requirements")
    assert stored.payload["output"] == "public class CubeMesh {}"
    assert stored.payload["asset_type"] == "cube"
