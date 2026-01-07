from pathlib import Path

import pytest

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
        domain_id='coding',
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
        domain_id='coding',
        workspace_path=str(tmp_path),
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store,
        db_session=None
    )

    success = await indexer.index_file(Path('keep.py'))
    assert success is True

    collection = 'loco_rag_coding'
    info = fake_vector_store.get_collection_info(collection)
    assert info['points_count'] > 0

    stored = next(iter(fake_vector_store.collections[collection].values()))
    assert stored.payload['file_path'] == 'keep.py'
    assert stored.payload['workspace_id'] == 'ws-2'
