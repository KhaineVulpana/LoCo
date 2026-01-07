import numpy as np

from app.core import embedding_manager as em


class DummyModel:
    def __init__(self, model_name, cache_folder=None):
        self.model_name = model_name

    def get_sentence_embedding_dimension(self):
        return 4

    def encode(self, texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True):
        return np.array([[1.0, 0.0, 0.0, 0.0] for _ in texts])


def test_embedding_manager_empty_batch(monkeypatch):
    monkeypatch.setattr(em, 'SentenceTransformer', DummyModel)

    manager = em.EmbeddingManager(model_name='dummy')
    embeddings = manager.embed([])

    assert embeddings.shape == (0, 4)


def test_embedding_manager_embed_single_empty(monkeypatch):
    monkeypatch.setattr(em, 'SentenceTransformer', DummyModel)

    manager = em.EmbeddingManager(model_name='dummy')
    vector = manager.embed_single('')

    assert vector.shape == (4,)
    assert vector.tolist() == [0.0, 0.0, 0.0, 0.0]


def test_embedding_manager_embed_query_alias(monkeypatch):
    monkeypatch.setattr(em, 'SentenceTransformer', DummyModel)

    manager = em.EmbeddingManager(model_name='dummy')
    vector = manager.embed_query('test')

    assert vector.tolist() == [1.0, 0.0, 0.0, 0.0]
