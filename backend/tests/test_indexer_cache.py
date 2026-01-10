from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import text

from app.indexing.indexer import FileIndexer


class CountingEmbeddingManager:
    def __init__(self, dimensions: int = 4):
        self.calls = 0
        self._dimensions = dimensions

    def get_dimensions(self) -> int:
        return self._dimensions

    def get_model_name(self) -> str:
        return "counting-embed"

    def embed(self, texts):
        self.calls += 1
        return [np.full(self._dimensions, idx + 1, dtype=np.float32) for idx, _ in enumerate(texts)]

    def embed_query(self, text):
        return np.ones(self._dimensions, dtype=np.float32)


@pytest.mark.asyncio
async def test_embedding_cache_reuses_embeddings(tmp_path, fake_vector_store, async_session_maker):
    content = 'print("hi")\n'
    (tmp_path / 'a.py').write_text(content, encoding='utf-8')
    (tmp_path / 'b.py').write_text(content, encoding='utf-8')

    embedding_manager = CountingEmbeddingManager()

    async with async_session_maker() as session:
        indexer = FileIndexer(
            workspace_id='ws-cache',
            frontend_id='vscode',
            workspace_path=str(tmp_path),
            embedding_manager=embedding_manager,
            vector_store=fake_vector_store,
            db_session=session
        )

        await indexer.index_file(Path('a.py'))
        await indexer.index_file(Path('b.py'))

        assert embedding_manager.calls == 1

        result = await session.execute(text("SELECT use_count FROM embedding_cache"))
        rows = result.fetchall()
        total_uses = sum(row[0] for row in rows if row and row[0] is not None)
        assert total_uses == 2


@pytest.mark.asyncio
async def test_index_file_skips_unchanged(tmp_path, fake_vector_store, async_session_maker):
    (tmp_path / 'main.py').write_text('print("hi")\n', encoding='utf-8')

    embedding_manager = CountingEmbeddingManager()

    async with async_session_maker() as session:
        indexer = FileIndexer(
            workspace_id='ws-skip',
            frontend_id='vscode',
            workspace_path=str(tmp_path),
            embedding_manager=embedding_manager,
            vector_store=fake_vector_store,
            db_session=session
        )

        result1 = await indexer.index_file(Path('main.py'))
        assert result1["success"] is True

        result2 = await indexer.index_file(Path('main.py'))
        assert result2["success"] is True
        assert result2.get("skipped") is True
        assert embedding_manager.calls == 1
