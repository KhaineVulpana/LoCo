from pathlib import Path

import pytest
from sqlalchemy import text

from app.indexing.chunker import ASTChunker, ChunkResult, Parser
from app.indexing.indexer import FileIndexer


@pytest.mark.asyncio
async def test_indexer_persists_symbols(tmp_path, fake_embedding_manager, fake_vector_store, async_session_maker):
    if Parser is None:
        pytest.skip("tree-sitter not available")

    sample = "def greet(name):\n    return name\n"
    chunk_result = ASTChunker().chunk_file(sample, language="python", file_path="sample.py")
    if not isinstance(chunk_result, ChunkResult) or not chunk_result.symbols:
        pytest.skip("tree-sitter parser inactive")

    (tmp_path / "sample.py").write_text(sample, encoding="utf-8")

    async with async_session_maker() as session:
        indexer = FileIndexer(
            workspace_id="ws-symbols",
            frontend_id="vscode",
            workspace_path=str(tmp_path),
            embedding_manager=fake_embedding_manager,
            vector_store=fake_vector_store,
            db_session=session
        )

        result = await indexer.index_file(Path("sample.py"))
        assert result["success"] is True

        symbol_row = await session.execute(text("""
            SELECT name, kind FROM symbols WHERE workspace_id = :workspace_id
        """), {"workspace_id": "ws-symbols"})
        row = symbol_row.fetchone()
        assert row is not None
        assert row[0] == "greet"
        assert row[1] == "function"
