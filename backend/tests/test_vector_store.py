from types import SimpleNamespace

from qdrant_client.models import Distance, PointStruct

from app.core import vector_store as vector_store_module
from app.core.vector_store import VectorStore


class FakeQdrantClient:
    def __init__(self, host=None, port=None):
        self.collections = {}

    def get_collections(self):
        return SimpleNamespace(collections=[
            SimpleNamespace(name=name) for name in self.collections.keys()
        ])

    def create_collection(self, collection_name, vectors_config):
        self.collections[collection_name] = {
            'vectors_config': vectors_config,
            'points': {}
        }

    def delete_collection(self, collection_name):
        self.collections.pop(collection_name, None)

    def upsert(self, collection_name, points):
        collection = self.collections.setdefault(collection_name, {
            'vectors_config': SimpleNamespace(size=0, distance=Distance.COSINE),
            'points': {}
        })
        for point in points:
            collection['points'][str(point.id)] = point

    def search(self, collection_name, query_vector, limit=10, score_threshold=None, query_filter=None):
        collection = self.collections.get(collection_name, {'points': {}})
        results = []
        for point in collection['points'].values():
            score = sum(a * b for a, b in zip(point.vector, query_vector))
            if score_threshold is not None and score < score_threshold:
                continue
            if query_filter:
                for condition in query_filter.must:
                    if point.payload.get(condition.key) != condition.match.value:
                        break
                else:
                    results.append(SimpleNamespace(id=point.id, score=score, payload=point.payload))
                continue
            results.append(SimpleNamespace(id=point.id, score=score, payload=point.payload))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:limit]

    def scroll(self, collection_name, limit=100, offset=None):
        collection = self.collections.get(collection_name, {'points': {}})
        points = list(collection['points'].values())
        start = int(offset or 0)
        end = start + limit
        page = points[start:end]
        next_offset = end if end < len(points) else None
        return page, next_offset

    def delete(self, collection_name, points_selector):
        collection = self.collections.get(collection_name, {'points': {}})
        for point_id in points_selector.points:
            collection['points'].pop(str(point_id), None)

    def get_collection(self, collection_name):
        collection = self.collections[collection_name]
        vectors_config = collection['vectors_config']
        config = SimpleNamespace(params=SimpleNamespace(vectors=vectors_config))
        return SimpleNamespace(
            config=config,
            points_count=len(collection['points']),
            status='green'
        )


def _install_fakes(monkeypatch):
    fake_client = FakeQdrantClient()
    monkeypatch.setattr(vector_store_module, 'QdrantClient', lambda host, port: fake_client)
    return fake_client


def test_create_collection_and_info(monkeypatch):
    _install_fakes(monkeypatch)
    store = VectorStore(host='localhost', port=6333)

    created = store.create_collection('test', vector_size=3)
    assert created is True

    info = store.get_collection_info('test')
    assert info['vector_size'] == 3
    assert info['status'] == 'green'

    created_again = store.create_collection('test', vector_size=3)
    assert created_again is False


def test_upsert_search_and_scroll(monkeypatch):
    _install_fakes(monkeypatch)
    store = VectorStore(host='localhost', port=6333)
    store.create_collection('test', vector_size=3)

    points = [
        PointStruct(id='p1', vector=[1.0, 0.0, 0.0], payload={'tag': 'a'}),
        PointStruct(id='p2', vector=[0.0, 1.0, 0.0], payload={'tag': 'b'})
    ]
    store.upsert_vectors('test', points)

    results = store.search('test', query_vector=[1.0, 0.0, 0.0], limit=1)
    assert results[0]['id'] == 'p1'

    page = store.scroll('test', limit=1)
    assert len(page['points']) == 1


def test_delete_points(monkeypatch):
    _install_fakes(monkeypatch)
    store = VectorStore(host='localhost', port=6333)
    store.create_collection('test', vector_size=3)

    store.upsert_vectors('test', [
        PointStruct(id='p1', vector=[1.0, 0.0, 0.0], payload={})
    ])

    assert store.get_collection_info('test')['points_count'] == 1
    store.delete_points('test', ['p1'])
    assert store.get_collection_info('test')['points_count'] == 0
