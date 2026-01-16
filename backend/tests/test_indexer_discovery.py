from pathlib import Path

import pytest
from sqlalchemy import text

from app.indexing.indexer import FileIndexer


@pytest.mark.asyncio
async def test_discover_files_respects_gitignore(tmp_path, fake_embedding_manager, fake_vector_store):
    (tmp_path / '.gitignore').write_text('ignored/\n*.log\n', encoding='utf-8')
    (tmp_path / 'keep.py').write_text('print("hi")\n', encoding='utf-8')
    (tmp_path / 'skip.log').write_text('log', encoding='utf-8')
    (tmp_path / 'ignored').mkdir()
    (tmp_path / 'ignored' / 'secret.py').write_text('pass', encoding='utf-8')

    indexer = FileIndexer(
        workspace_id='ws-1',
        module_id='vscode',
        workspace_path=str(tmp_path),
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store,
        db_session=None
    )

    files = indexer.discover_files()

    assert Path('keep.py') in files
    assert Path('skip.log') not in files
    assert Path('ignored/secret.py') not in files


@pytest.mark.asyncio
async def test_index_file_stores_vectors(tmp_path, fake_embedding_manager, fake_vector_store):
    (tmp_path / 'keep.py').write_text('print("hi")\n', encoding='utf-8')

    indexer = FileIndexer(
        workspace_id='ws-2',
        module_id='vscode',
        workspace_path=str(tmp_path),
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store,
        db_session=None
    )

    result = await indexer.index_file(Path('keep.py'))
    assert result["success"] is True

    collection = 'loco_rag_workspace_ws-2'
    info = fake_vector_store.get_collection_info(collection)
    assert info['points_count'] > 0

    stored = next(iter(fake_vector_store.collections[collection].values()))
    assert stored.payload['file_path'] == 'keep.py'
    assert stored.payload['workspace_id'] == 'ws-2'


@pytest.mark.asyncio
async def test_index_file_persists_chunks(tmp_path, fake_embedding_manager, fake_vector_store, async_session_maker):
    (tmp_path / 'main.py').write_text('print("hi")\n', encoding='utf-8')

    async with async_session_maker() as session:
        indexer = FileIndexer(
            workspace_id='ws-3',
            module_id='vscode',
            workspace_path=str(tmp_path),
            embedding_manager=fake_embedding_manager,
            vector_store=fake_vector_store,
            db_session=session
        )

        result = await indexer.index_file(Path('main.py'))
        assert result["success"] is True

        file_row = await session.execute(text("""
            SELECT id FROM files WHERE workspace_id = :workspace_id AND path = :path
        """), {"workspace_id": "ws-3", "path": "main.py"})
        file_id = file_row.fetchone()[0]

        chunk_row = await session.execute(text("""
            SELECT content FROM chunks WHERE file_id = :file_id
        """), {"file_id": file_id})
        chunk = chunk_row.fetchone()
        assert chunk is not None
        assert "print" in chunk[0]
