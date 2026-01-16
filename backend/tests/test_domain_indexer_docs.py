import pytest

from app.indexing.domain_indexer import KnowledgeIndexer


@pytest.mark.asyncio
async def test_index_documentation_indexes_markdown(tmp_path, fake_embedding_manager, fake_vector_store):
    docs_path = tmp_path / 'docs'
    docs_path.mkdir()
    (docs_path / 'readme.md').write_text('Hello\nWorld\n', encoding='utf-8')
    (docs_path / 'data.jsonl').write_text('{"prompt": "skip"}\n', encoding='utf-8')

    indexer = KnowledgeIndexer(
        module_id='3d-gen',
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store
    )

    stats = await indexer.index_documentation(str(docs_path))

    assert stats['indexed'] == 1

    collection = 'loco_rag_3d-gen'
    info = fake_vector_store.get_collection_info(collection)
    assert info['points_count'] == 1

    stored = next(iter(fake_vector_store.collections[collection].values()))
    assert stored.payload['source'] == 'readme.md'
    assert stored.payload['type'] == 'documentation'
