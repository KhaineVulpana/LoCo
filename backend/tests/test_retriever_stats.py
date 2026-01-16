from types import SimpleNamespace

from app.retrieval.retriever import Retriever


def test_retriever_stats_include_ace(fake_vector_store, fake_embedding_manager):
    rag = 'loco_rag_vscode'
    ace = 'loco_ace_vscode'

    fake_vector_store.create_collection(rag, vector_size=fake_embedding_manager.get_dimensions())
    fake_vector_store.create_collection(ace, vector_size=fake_embedding_manager.get_dimensions())

    fake_vector_store.upsert_vectors(
        rag,
        [SimpleNamespace(id='p1', vector=[0.1] * fake_embedding_manager.get_dimensions(), payload={})]
    )
    fake_vector_store.upsert_vectors(
        ace,
        [SimpleNamespace(id='b1', vector=[0.2] * fake_embedding_manager.get_dimensions(), payload={})]
    )

    retriever = Retriever(
        module_id='vscode',
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store
    )

    stats = retriever.get_collection_stats()
    assert stats['rag_chunks'] == 1
    assert stats['ace_bullets'] == 1
    assert stats['rag_collection'] == rag
