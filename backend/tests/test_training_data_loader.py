import json

import pytest

from app.indexing.training_data_loader import ensure_3d_gen_training_data


@pytest.mark.asyncio
async def test_training_data_loader_indexes_when_empty(
    tmp_path, fake_embedding_manager, fake_vector_store
):
    jsonl_path = tmp_path / "training.jsonl"
    jsonl_path.write_text(
        json.dumps({"prompt": "Generate a cube", "completion": "mesh data"}) + "\n",
        encoding="utf-8"
    )

    result = await ensure_3d_gen_training_data(
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store,
        path_override=str(jsonl_path)
    )

    assert result["status"] == "indexed"
    assert result["stats"]["indexed"] == 1


@pytest.mark.asyncio
async def test_training_data_loader_reports_missing(fake_embedding_manager, fake_vector_store, tmp_path):
    missing_path = tmp_path / "missing.jsonl"
    result = await ensure_3d_gen_training_data(
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store,
        path_override=str(missing_path)
    )

    assert result["status"] == "missing"
