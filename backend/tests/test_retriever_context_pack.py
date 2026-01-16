from app.retrieval.retriever import Retriever, RetrievalResult


def test_context_pack_budget_truncates(fake_embedding_manager, fake_vector_store):
    retriever = Retriever(
        module_id="vscode",
        embedding_manager=fake_embedding_manager,
        vector_store=fake_vector_store
    )

    results = [
        RetrievalResult(score=0.9, content="alpha " * 200, source="a.py", metadata={"file_path": "a.py"}),
        RetrievalResult(score=0.8, content="beta " * 200, source="b.py", metadata={"file_path": "b.py"})
    ]

    pack = retriever.build_context_pack(
        title="Workspace Knowledge",
        results=results,
        token_budget=50
    )

    assert pack.items
    assert pack.truncated is True
    assert pack.token_count <= 50
